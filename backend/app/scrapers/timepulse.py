"""
Scraper for timepulse.fr results — pure XML parsing, no Playwright.

TimePulse exposes a data API that returns a wiclax-format XML:
  https://www.timepulse.fr/resultats/api/data.php?id_event={id}

The XML contains:
  <Epreuve>        event metadata
  <S id="N" nom="Natation|T1|Vélo|T2|Course à pied" />   series definitions
  <E d="{bib}" n="{NOM Prénom}" c="{club}" x="{M|F}" ca="{category}" p="{parcours}" />
  <R d="{bib}" t="{total}" s0="{split0}" … s4="{split4}" />

When a search name matches multiple athletes a ValueError is raised listing
all matches so the user can refine their query.
"""
import re
from datetime import date as date_t
from urllib.parse import parse_qs, urlparse

import httpx

from .base import STATUS_DNF, STATUS_DNS, STATUS_DSQ, ScrapedResult
from .utils import (
    derive_status_from_label,
    normalize_time,
    parse_fr_date,
    split_athlete_name,
)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

_DATA_API_URLS = [
    "https://www.timepulse.fr/resultats/api/data.php?id_event={id_event}",
    "https://www.timepulse.fr/epreuves/resultats/api/data.php?id_event={id_event}",
]

# Attributs susceptibles de porter un label de statut texte (DNF/DNS/DSQ) sur
# <E>/<R>. Conservé même si aucune épreuve réelle observée n'expose un tel label
# (le XML pose un flag binaire np, cf. _extract_status) : reste utile si un futur
# payload expose un libellé texte, et garde le test synthétique etat="Abandon"
# pertinent.
_STATUS_ATTRS = ("etat", "st", "status", "statut")


def _extract_status(ea: dict[str, str], ra: dict[str, str]) -> str:
    """Lit un statut explicite depuis les attributs E puis R ; "" sinon.

    Cherche d'abord un label texte (_STATUS_ATTRS) traduit via
    derive_status_from_label, puis le flag binaire np de TimePulse.
    """
    for attrs in (ea, ra):
        for name in _STATUS_ATTRS:
            val = attrs.get(name, "")
            if val:
                status = derive_status_from_label(val)
                if status:
                    return status

    # Flag non-partant TimePulse (np="1") → DNS. Découverte (épreuve réelle) : le
    # XML ne pose pas de libellé texte mais un flag binaire np sur le <E>.
    if (ea.get("np") or "").strip() not in ("", "0"):
        return STATUS_DNS
    return ""


# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------

def _fetch_xml(id_event: str) -> str:
    for tpl in _DATA_API_URLS:
        try:
            r = httpx.get(
                tpl.format(id_event=id_event),
                follow_redirects=True, timeout=20, headers=_HEADERS,
            )
            if r.status_code == 200 and "<Epreuve" in r.text:
                return r.text
        except httpx.HTTPError:
            continue
    return ""


def _fetch_event_page(id_event: str) -> str:
    """HTML de la page publique de l'épreuve (dernier recours pour la date)."""
    try:
        r = httpx.get(
            f"https://www.timepulse.fr/epreuves/resultats/{id_event}",
            follow_redirects=True, timeout=20, headers=_HEADERS,
        )
        return r.text if r.status_code == 200 else ""
    except httpx.HTTPError:
        return ""


def _parse_event_page_date(html: str) -> date_t | None:
    """Date affichée par la page de l'épreuve, à côté du pictogramme 📅.

    Source de dernier recours, mais la seule qui fasse autorité quand le XML ne
    porte aucune date lisible (cas 2679 « COUËRON DUATHLON »).
    """
    m = re.search(r"(?:\U0001F4C5|&#x1F4C5;)\s*(\d{4}-\d{2}-\d{2})", html)
    if not m:
        return None
    try:
        return date_t.fromisoformat(m.group(1))
    except ValueError:
        return None


def _attrs(tag: str) -> dict[str, str]:
    """Extract all key="value" attributes from an XML tag string."""
    return dict(re.findall(r'(\w+)="([^"]*)"', tag))


def _find_tag(xml: str, tag: str, attr: str, value: str) -> str | None:
    """Return the first <tag …attr="value"…/> or None."""
    m = re.search(
        r"<" + tag + r"\s[^>]*\b" + attr + r'="' + re.escape(value) + r'"[^>]*/?>',
        xml,
    )
    return m.group() if m else None


# ---------------------------------------------------------------------------
# Series → split field mapping
# ---------------------------------------------------------------------------

_SERIES_SPLIT_MAP = [
    ("natation", "swim"), ("swim", "swim"),
    ("t1", "t1"), ("transition 1", "t1"), ("chg nat", "t1"),
    ("vélo", "bike"), ("velo", "bike"), ("bike", "bike"), ("cyclisme", "bike"),
    ("t2", "t2"), ("transition 2", "t2"), ("chg v", "t2"),
    ("course", "run"), ("cap", "run"), ("run", "run"), ("à pied", "run"),
]


# Catégories d'équipe TimePulse : EQX (mixte), EQM (hommes), EQF (femmes).
_RELAY_CATEGORIES = frozenset({"EQX", "EQM", "EQF"})


def _is_relay(parcours: str, category: str) -> bool:
    """Vrai si la participation est un relais d'équipe.

    Deux marqueurs concordants sur TimePulse : le parcours `p` contient
    « RELAIS » (vs « SOLO »), et/ou la catégorie `ca` est une catégorie d'équipe.
    """
    return "relais" in (parcours or "").lower() or (category or "").upper() in _RELAY_CATEGORIES


def _series_field(nom: str) -> str | None:
    n = nom.lower().strip()
    for key, field in _SERIES_SPLIT_MAP:
        if key in n:
            return field
    return None


def _parse_series(xml: str) -> dict[str, str]:
    """Return {s-index: field} e.g. {"s0": "swim", "s1": "t1", ...}

    Special case — duathlon: both stages are "Course à pied" (no swim).
    The first run is mapped to the "swim" slot so both runs have distinct slots.
    """
    entries: list[tuple[str, str]] = []
    for m in re.finditer(r"<S\s[^>]+/>", xml):
        a = _attrs(m.group())
        idx = a.get("id", "")
        nom = a.get("nom", a.get("lb", ""))
        field = _series_field(nom)
        if idx and field:
            entries.append((idx, field))

    run_count  = sum(1 for _, f in entries if f == "run")
    swim_count = sum(1 for _, f in entries if f == "swim")
    is_duathlon_layout = (run_count == 2 and swim_count == 0)

    mapping: dict[str, str] = {}
    first_run_seen = False
    for idx, field in entries:
        if field == "run" and is_duathlon_layout:
            if not first_run_seen:
                mapping[f"s{idx}"] = "swim"   # run1 → swim slot (no swimming in duathlon)
                first_run_seen = True
            else:
                mapping[f"s{idx}"] = "run"
        else:
            mapping[f"s{idx}"] = field
    return mapping


# ---------------------------------------------------------------------------
# Rankings computation
# ---------------------------------------------------------------------------

def _secs(t: str) -> int:
    if not t:
        return 0
    p = t.split(":")
    try:
        return int(p[0]) * 3600 + int(p[1]) * 60 + int(p[2])
    except (IndexError, ValueError):
        return 0


def _fmt_secs(s: int) -> str:
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def _derive_late_splits(result: ScrapedResult, ra: dict[str, str]) -> None:
    """Reconstitue T2 + course depuis les points de passage cumulés (`pN`).

    Quand TimePulse ne publie pas de segment T2/course (séries `np="1"`, pas de
    `s3`/`s4`), les temps n'existent que sous forme de passages cumulés. La fin
    du vélo est le passage cumulé le plus proche du cumul natation+T1+vélo (on
    s'ancre sur le passage réel, pas sur la somme des segments arrondis, qui
    dérive de quelques secondes) ; le passage suivant est la sortie T2 :
      T2     = (passage de sortie T2) − (passage fin vélo)
      course = total − (passage de sortie T2)
    Sans aucun passage après le vélo, tout le reliquat est rangé en course.
    """
    approx_bike_end = (
        _secs(result.swim_time) + _secs(result.t1_time) + _secs(result.bike_time)
    )
    total = _secs(result.total_time)
    if not approx_bike_end or total <= approx_bike_end:
        return

    points = sorted(
        c
        for k, v in ra.items()
        if re.fullmatch(r"p\d+", k) and (c := _secs(normalize_time(v))) > 0
    )
    if not points:
        result.run_time = _fmt_secs(total - approx_bike_end)
        return

    bike_pt = min(points, key=lambda p: abs(p - approx_bike_end))
    after = [p for p in points if p > bike_pt]
    if after:
        t2_out = min(after)
        if not result.t2_time:
            result.t2_time = _fmt_secs(t2_out - bike_pt)
        result.run_time = _fmt_secs(total - t2_out)
    else:
        result.run_time = _fmt_secs(total - bike_pt)


def _compute_ranks(
    xml: str, bib: str, parcours: str, gender: str, category: str
) -> tuple[int | None, int | None, int | None]:
    """
    Compute (rank_overall, rank_gender, rank_category) within the athlete's
    parcours by sorting all R entries by total time.
    """
    # Gather bibs for the same parcours
    parcours_bibs: set[str] = set()
    for m in re.finditer(r"<E\s[^>]+/>", xml):
        a = _attrs(m.group())
        if a.get("p", "") == parcours:
            parcours_bibs.add(a.get("d", ""))

    # Gather E attrs indexed by bib for gender/category filtering
    e_by_bib: dict[str, dict] = {}
    for m in re.finditer(r"<E\s[^>]+/>", xml):
        a = _attrs(m.group())
        e_by_bib[a.get("d", "")] = a

    # Gather R entries for same parcours, keyed by bib with time in seconds
    results: list[tuple[int, str]] = []  # (secs, bib)
    for m in re.finditer(r"<R\s[^>]+/>", xml):
        a = _attrs(m.group())
        b = a.get("d", "")
        if b in parcours_bibs:
            t = normalize_time(a.get("t", ""))
            s = _secs(t)
            if s:
                results.append((s, b))

    results.sort(key=lambda x: x[0])

    rank_overall = rank_gender = rank_category = None

    overall_pos = gender_pos = category_pos = 0
    for _s, b in results:
        e = e_by_bib.get(b, {})
        overall_pos += 1
        if e.get("x", "") == gender:
            gender_pos += 1
        # Category rank: count same-gender + same-category (categories are gender-specific
        # in French triathlon, e.g. V1H vs V1F; counting across genders would inflate the rank)
        if e.get("ca", "") == category and e.get("x", "") == gender:
            category_pos += 1

        if b == bib:
            rank_overall = overall_pos
            rank_gender = gender_pos
            rank_category = category_pos
            break

    return rank_overall, rank_gender, rank_category


def _parse_event_date(date_str: str) -> date_t | None:
    """Parse TimePulse XML date string into a date object.

    Handles:
      YYYY-MM-DD           → ISO format
      DD/MM/YYYY           → French numeric
      'dimanche 19 octobre 2025' → French with day-of-week prefix
    """
    if not date_str:
        return None
    # ISO format YYYY-MM-DD
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", date_str)
    if m:
        try:
            return date_t(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    # French numeric DD/MM/YYYY
    m = re.match(r"^(\d{1,2})/(\d{2})/(\d{4})", date_str)
    if m:
        try:
            return date_t(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    # French textual: 'dimanche 19 octobre 2025' or '19 octobre 2025'
    return parse_fr_date(date_str)


# ---------------------------------------------------------------------------
# Bulk event scraping
# ---------------------------------------------------------------------------

def scrape_event_all(url: str) -> list[ScrapedResult]:
    """
    Fetch ALL participants for a TimePulse event.
    Uses a single XML request (same as scrape()), then iterates all <E>/<R> pairs.
    Rankings are computed in-memory from the same XML — no extra HTTP requests.
    """
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    id_event = params.get("id_event", [""])[0]
    if not id_event:
        path_parts = [p for p in parsed.path.strip("/").split("/") if p]
        for part in reversed(path_parts):
            if re.match(r"^\d+$", part):
                id_event = part
                break
    if not id_event:
        raise ValueError("Paramètre id_event manquant dans l'URL TimePulse.")

    xml = _fetch_xml(id_event)
    if not xml:
        raise ValueError(f"Impossible de récupérer les données de l'événement {id_event}.")

    series_map = _parse_series(xml)

    # Event metadata
    event_name = ""
    event_date_val = None
    epreuve_m = re.search(r"<Epreuve\s[^>]+>", xml)
    if epreuve_m:
        ea = _attrs(epreuve_m.group())
        event_name = ea.get("nom", "")
        # `dates` (libellé libre) est parfois vide ; on replie alors sur les
        # dates ISO de début/fin `dt1`/`dt2` (cas réel 3232 « LE NORTH MAY »).
        date_str = ea.get("dates", "") or ea.get("dt1", "") or ea.get("dt2", "")
        if date_str:
            event_date_val = _parse_event_date(date_str)
    # XML muet sur la date (cas réel 2679 « COUËRON DUATHLON ») : la page
    # publique l'affiche. Le seul attribut restant du XML est un numéro de série
    # peu fiable — on ne s'en sert pas (cf. wiclax._clax_event_date).
    if event_date_val is None:
        event_date_val = _parse_event_page_date(_fetch_event_page(id_event))
    # Repli si un participant n'a pas de parcours (`p` vide).
    event_type_fallback = _detect_event_type(event_name)

    results: list[ScrapedResult] = []

    for e_m in re.finditer(r"<E\s[^>]+/>", xml):
        ea = _attrs(e_m.group())
        bib = ea.get("d", "")
        if not bib:
            continue

        result = ScrapedResult(source_url=url, provider="timepulse", bib_number=bib)
        result.event_name = event_name
        result.event_date = event_date_val
        # Le format (S/M/L) est porté par le parcours `p` de chaque <E>, pas par
        # le nom global de l'épreuve (ex. « LE NORTH MAY » → Triathlon S/M/L SOLO).
        parcours = ea.get("p", "")
        result.event_type = (
            _detect_event_type(parcours) if parcours else event_type_fallback
        )

        full_name = ea.get("n", "")
        surname, firstname = split_athlete_name(full_name)
        result.athlete_name = surname
        result.athlete_firstname = firstname
        result.club = ea.get("c", "")
        result.gender = ea.get("x", "")
        result.category = ea.get("ca", "")
        result.is_relay = _is_relay(parcours, result.category)

        r_tag = _find_tag(xml, "R", "d", bib)
        ra = _attrs(r_tag) if r_tag else {}

        # Statut explicite éventuel (E puis R) ; "" → heuristique de l'infra.
        result.status = _extract_status(ea, ra)
        is_non_finisher = result.status in (STATUS_DNF, STATUS_DNS, STATUS_DSQ)

        # Sans <R> (non-partant/abandon) OU statut non-finisher explicite : on
        # conserve l'athlète mais on laisse total_time="", splits vides, rangs None.
        if r_tag and not is_non_finisher:
            result.total_time = normalize_time(ra.get("t", ""))
            for key, field in series_map.items():
                t = normalize_time(ra.get(key, ""))
                if not t:
                    continue
                if field == "swim" and not result.swim_time:
                    result.swim_time = t
                elif field == "t1" and not result.t1_time:
                    result.t1_time = t
                elif field == "bike" and not result.bike_time:
                    result.bike_time = t
                elif field == "t2" and not result.t2_time:
                    result.t2_time = t
                elif field == "run" and not result.run_time:
                    result.run_time = t

            # T2 + course à pied : TimePulse marque parfois ces séries np="1" et
            # ne fournit aucun segment (s3/s4). Le temps n'existe alors que sous
            # forme de points de passage cumulés → on le reconstitue.
            if not result.run_time:
                _derive_late_splits(result, ra)

            if parcours and result.gender and result.category:
                ro, rg, rc = _compute_ranks(xml, bib, parcours, result.gender, result.category)
                result.rank_overall = ro
                result.rank_gender = rg
                result.rank_category = rc

        results.append(result)

    return results


# ---------------------------------------------------------------------------
# Event type detection
# ---------------------------------------------------------------------------

def _detect_event_type(name: str) -> str:
    from app.scrapers.classify import classify_event_type
    return classify_event_type(name)
