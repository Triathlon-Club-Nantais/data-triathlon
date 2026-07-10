"""
Scraper for sportinnovation.fr

Two URL formats:

1. www.sportinnovation.fr/Evenements/Resultats/{eventId}  (28/32 URLs)
   - Server-rendered HTML table with full splits
   - GET all rows, filter by name in Python
   - Name cell format: "LASTNAME FirstnameG-CatG" (G=H/F, Cat=category)
   - Columns: Place | Dossard | Nom | Place Cat. | Club | Temps | ... | Tps Nat | T1 | Tps Velo | T2 | Tps CAP
   - Nom d'événement et date : absents de la page liste (bandeau rempli en JS),
     lus sur la page du modal de détail `/Evenements/Resultats/Detail/{id}/1`.

2. results.sportinnovation.fr/race/{slug}  (format 2026)
   - JSON API : GET /api/races/{slug} → meta, /api/races/{slug}/results → athlètes
   - Splits via GET /api/results/{id_or_slug}?intermediates=1 par athlète
   - Récupérés en parallèle (ThreadPoolExecutor, max 20 workers)

3. results.sportinnovation.fr/detail/{id}  (lien individuel)
   - Résout le raceSlug via GET /api/results/{id}, puis même pipeline que /race/{slug}
"""
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from .base import STATUS_DNF, STATUS_DNS, STATUS_DSQ, ScrapedResult
from .utils import derive_status_from_label, normalize_rank, normalize_time

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json,*/*",
}
API_BASE = "https://sportinnovation.fr/api"


# ──────────────────────────────────────────────────────────────────────────────
# Helpers — HTML format (www.sportinnovation.fr)
# ──────────────────────────────────────────────────────────────────────────────

_NAME_RE = re.compile(
    r"^(?P<lastname>[A-ZÀ-Ÿ][A-ZÀ-Ÿ'\- ]+?)\s+(?P<firstname>[A-Za-zÀ-ÿ'\- ]+?)(?P<gender>[HF])-(?P<cat>[A-Z0-9]+)(?P<gender2>[HF])?$"
)


def _parse_name_cell(raw: str) -> tuple[str, str, str, str]:
    """
    Parse "GUEGANO JordanH-S3H" → (lastname, firstname, gender, category).
    Falls back gracefully when format doesn't match.
    """
    raw = raw.strip()
    m = _NAME_RE.match(raw)
    if m:
        return (
            m.group("lastname").strip(),
            m.group("firstname").strip(),
            m.group("gender"),
            m.group("cat"),
        )
    # Fallback: split on last uppercase run
    parts = raw.split()
    # Find where uppercase run ends
    i = 0
    while i < len(parts) and parts[i].replace("-", "").replace("'", "").isupper():
        i += 1
    lastname = " ".join(parts[:i]) if i > 0 else raw
    rest = " ".join(parts[i:]) if i < len(parts) else ""
    # Extract gender/cat suffix from rest
    gcat = re.search(r"([HF])-([A-Z0-9]+)", rest)
    if gcat:
        firstname = rest[: gcat.start()].strip()
        gender = gcat.group(1)
        cat = gcat.group(2)
    else:
        firstname = rest
        gender = ""
        cat = ""
    return lastname, firstname, gender, cat


def _detect_event_type(race_name: str) -> str:
    from app.scrapers.classify import classify_event_type
    return classify_event_type(race_name)


_H6_RE = re.compile(r"^(?P<race>.+?)\s*\((?P<date>\d{2}/\d{2}/\d{4})\)\s*$", re.S)
_SHARE_TITLE_RE = re.compile(r"sharer\.php\?u=[^&]*&t=(?P<title>[^\"']+)")


def _parse_race_meta(html: str) -> tuple[str, str, date | None]:
    """Extrait (nom de course, nom d'événement, date) d'une page de détail participant.

    Deux porteurs indépendants dans la page :
      - `<h6>Triathlon M (05/10/2025)</h6>` → course + date (la date est propre à
        la course : à Carnac les aquathlons ont lieu la veille des triathlons) ;
      - le lien de partage `…&t=Résultats - {course} - {événement}` → événement.

    Le nom de course peut contenir « - » (« Bike & Run - Kids ») : on retire le
    préfixe `Résultats - {course} - ` déjà connu plutôt que de couper au dernier
    tiret. Chaque champ manquant retombe sur une valeur vide.
    """
    soup = BeautifulSoup(html, "lxml")

    race_name = ""
    event_date = None
    h6 = soup.find("h6")
    if h6:
        m = _H6_RE.match(h6.get_text(strip=True))
        if m:
            race_name = m.group("race").strip()
            day, month, year = m.group("date").split("/")
            try:
                event_date = date(int(year), int(month), int(day))
            except ValueError:
                logger.warning("Date de course illisible : %s", m.group("date"))

    event_name = ""
    if race_name:
        # `href` est lu via bs4 (entités déjà décodées) : le HTML sérialisé ré-encode « & ».
        for a in soup.find_all("a", href=True):
            share = _SHARE_TITLE_RE.search(a["href"])
            if not share:
                continue
            title = share.group("title").strip()
            prefix = f"Résultats - {race_name} - "
            if title.startswith(prefix):
                event_name = title[len(prefix):].strip()
                break

    return race_name, event_name, event_date


def _compose_course_name(event_name: str, race_name: str) -> str:
    """Nom de Course « Événement - Course ».

    `uq_course_identity` porte sur (name, event_date, event_type, is_relay) : les
    quatre aquathlons de Carnac partagent date et `event_type`, seul le nom de
    course les distingue. On omet la moitié absente, et on ne duplique pas un
    événement mono-course dont le titre est déjà celui de la course.
    """
    event_name, race_name = event_name.strip(), race_name.strip()
    if not event_name:
        return race_name
    if not race_name or race_name.lower() == event_name.lower():
        return event_name
    return f"{event_name} - {race_name}"


def _col_indices(headers: list[str]) -> dict[str, int]:
    """Map column role → index from the <th> header row."""
    mapping = {}
    for i, h in enumerate(headers):
        hl = h.lower().strip()
        if "place" == hl or "rang" == hl:
            mapping.setdefault("rank_overall", i)
        elif "dossard" in hl or "bib" in hl:
            mapping.setdefault("bib", i)
        elif "nom" == hl or "athlete" in hl or "nom /" in hl:
            mapping.setdefault("name", i)
        elif "place cat" in hl or "cat." in hl:
            mapping.setdefault("rank_cat", i)
        elif "club" in hl or "équipe" in hl or "equipe" in hl:
            mapping.setdefault("club", i)
        elif "tps off" in hl or "temps off" in hl:
            mapping.setdefault("total_time", i)
        elif "nat" in hl or "swim" in hl or "nage" in hl:
            mapping.setdefault("swim_time", i)
        elif "transition 1" in hl or "t1" == hl:
            mapping.setdefault("t1_time", i)
        elif "velo" in hl or "vélo" in hl or "bike" in hl or "cycle" in hl:
            mapping.setdefault("bike_time", i)
        elif "transition 2" in hl or "t2" == hl:
            mapping.setdefault("t2_time", i)
        elif "cap" in hl or "run" in hl or "course" in hl or "corse" in hl:
            mapping.setdefault("run_time", i)
    # Fallback: use Temps Officiel if no Tps Off.
    if "total_time" not in mapping:
        for i, h in enumerate(headers):
            if "temps" in h.lower():
                mapping["total_time"] = i
                break
    return mapping


def _parse_html_row(
    tds: list[str],
    col: dict[str, int],
    url: str,
    race_name: str,
    course_name: str | None = None,
    event_date: date | None = None,
) -> ScrapedResult:
    """Construit un ScrapedResult depuis une ligne du tableau HTML.

    `race_name` sert à classifier le sport (« Triathlon M ») ; `course_name` est
    le nom stocké (« Triathlon de Carnac 2025 - Triathlon M ») et retombe sur
    `race_name` quand les métadonnées d'événement n'ont pas pu être lues.
    """
    result = ScrapedResult(source_url=url, provider="sportinnovation")
    result.event_name = course_name or race_name
    result.event_type = _detect_event_type(race_name)
    result.event_date = event_date

    def get(key: str) -> str:
        idx = col.get(key)
        return tds[idx].strip() if idx is not None and idx < len(tds) else ""

    raw_name = get("name")
    lastname, firstname, gender, cat = _parse_name_cell(raw_name)
    result.athlete_name = lastname
    result.athlete_firstname = firstname
    result.gender = gender
    result.category = cat

    result.bib_number = get("bib")
    result.club = get("club")
    result.rank_overall = normalize_rank(get("rank_overall"))
    result.rank_category = normalize_rank(get("rank_cat"))
    raw_total = get("total_time")
    status = derive_status_from_label(raw_total)
    if status:
        result.status = status
    else:
        result.total_time = normalize_time(raw_total)
    result.swim_time = normalize_time(get("swim_time"))
    result.t1_time = normalize_time(get("t1_time"))
    result.bike_time = normalize_time(get("bike_time"))
    result.t2_time = normalize_time(get("t2_time"))
    result.run_time = normalize_time(get("run_time"))
    if result.status in (STATUS_DNF, STATUS_DNS, STATUS_DSQ):
        result.rank_overall = None
        result.rank_category = None
        result.rank_gender = None
    result.raw_data = {"col_map": col}
    return result


def _fetch_html_results(
    event_id: str,
    client: httpx.Client,
    search: str = "",
    page: int = 1,
) -> tuple[str, list[list[str]], dict[str, int]]:
    """
    Fetch result rows from the HTML page.

    With search="": POST with empty search + numPage, returns rows for the race.
    With search=NAME: POST dossardSearch=NAME (server-side filter across all races).
    Returns (race_name, rows, col_indices).
    """
    url = f"https://sportinnovation.fr/Evenements/Resultats/{event_id}"

    resp = client.post(
        url,
        data={"dossardSearch": search, "numPage": str(page), "sexSearch": ""},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=20,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    # Race name from og:title "Résultats : Triathlon M"
    race_name = ""
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        race_name = og["content"].replace("Résultats :", "").replace("Résultats:", "").strip()
    if not race_name:
        h1 = soup.find("h1")
        race_name = h1.get_text(strip=True) if h1 else ""

    # Parse table headers
    th_row = soup.select_one("thead tr") or soup.select_one("tr")
    headers = [th.get_text(strip=True) for th in (th_row.select("th") if th_row else [])]
    col = _col_indices(headers)

    rows_data = []
    for tr in soup.select("tbody tr"):
        tds = [td.get_text(strip=True) for td in tr.select("td")]
        if tds:
            rows_data.append(tds)

    return race_name, rows_data, col


def _fetch_race_meta(race_id: str, client: httpx.Client) -> tuple[str, date | None]:
    """(nom d'événement, date) d'une course legacy, via la page de détail du 1er participant.

    Best-effort : une course vide ou une page inattendue renvoie ("", None), et
    l'appelant retombe alors sur le seul titre de course.
    """
    try:
        resp = client.get(
            f"https://sportinnovation.fr/Evenements/Resultats/Detail/{race_id}/1",
            timeout=15,
        )
        resp.raise_for_status()
        _, event_name, event_date = _parse_race_meta(resp.text)
        return event_name, event_date
    except Exception:
        logger.warning("Métadonnées introuvables pour la course %s", race_id, exc_info=True)
        return "", None


def _fetch_all_pages(event_id: str, client: httpx.Client) -> tuple[str, list[list[str]], dict[str, int]]:
    """Fetch all paginated rows for a race (250 rows per page)."""
    all_rows: list[list[str]] = []
    race_name = ""
    col: dict[str, int] = {}
    PAGE_SIZE = 250

    for page in range(1, 20):  # safety cap at 20 pages = 5000 participants
        rn, rows, c = _fetch_html_results(event_id, client, search="", page=page)
        if not race_name:
            race_name, col = rn, c
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < PAGE_SIZE:
            break  # last page

    return race_name, all_rows, col


def _classify_results_url(url: str) -> tuple[str, str]:
    """
    Classe une URL results.sportinnovation.fr :
      - /race/{slug}    → ("race", slug)    [affichage 2026, niveau course]
      - /detail/{id}    → ("detail", id)    [lien individuel → résout le raceSlug]
      - /{codeUrl}      → ("event", codeUrl) [niveau événement]
    """
    parts = [p for p in urlparse(url).path.strip("/").split("/") if p]
    if not parts:
        raise ValueError(f"URL results.sportinnovation.fr sans identifiant : {url}")
    if parts[0] == "race" and len(parts) >= 2:
        return "race", parts[1]
    if parts[0] == "detail" and len(parts) >= 2:
        return "detail", parts[1]
    return "event", parts[0]


def _first(a: dict, *keys: str):
    """Première clé présente et non vide parmi `keys` (schéma historique d'abord)."""
    for key in keys:
        value = a.get(key)
        if value not in (None, ""):
            return value
    return None


def _athlete_ref(a: dict) -> str | int | None:
    """Référence d'un athlète pour `/api/results/{ref}` : `id`, sinon `slug`.

    Le schéma FFA n'en expose aucune : renvoie None plutôt que de replier sur le
    dossard, car `/api/results/{bib}` interprète son argument comme un `id`
    global et renverrait l'athlète d'une autre course.
    """
    return _first(a, "id", "slug")


def _parse_api_athlete(
    a: dict,
    url: str,
    event_name: str,
    event_type: str,
    event_date,
    splits: dict[str, str] | None = None,
) -> ScrapedResult:
    """Construit un ScrapedResult depuis un athlète de l'API JSON sportinnovation.

    L'API sert deux schémas de résultats selon la course : l'historique
    (`generalRanking`, `officialTime`) et un schéma « FFA » (`generalRank`,
    `officialTimeFfa`), sans référence athlète. On lit les deux, l'historique
    primant quand les deux coexistent.
    """
    res = ScrapedResult(source_url=url, provider="sportinnovation")
    res.event_name = event_name
    res.event_type = event_type
    res.event_date = event_date
    res.athlete_name = (a.get("lastName") or "").strip().upper()
    res.athlete_firstname = (a.get("firstName") or "").strip()
    res.bib_number = str(a.get("bib") or "")
    res.club = (a.get("clubName") or "").strip()
    res.gender = a.get("sex") or ""
    res.category = a.get("category") or ""
    res.rank_overall = normalize_rank(str(_first(a, "generalRanking", "generalRank") or ""))
    res.rank_gender = normalize_rank(str(_first(a, "sexRanking", "sexRank") or ""))
    res.rank_category = normalize_rank(str(_first(a, "categoryRanking", "categoryRank") or ""))
    res.status = derive_status_from_label(str(a.get("status") or a.get("state") or ""))
    if res.status in (STATUS_DNF, STATUS_DNS, STATUS_DSQ):
        res.total_time = ""
        res.rank_overall = res.rank_gender = res.rank_category = None
    else:
        res.total_time = normalize_time(
            _first(a, "officialTime", "realTime", "officialTimeFfa", "realTimeFfa") or ""
        )
    if splits:
        res.swim_time = splits.get("swim", "")
        res.t1_time = splits.get("t1", "")
        res.bike_time = splits.get("bike", "")
        res.t2_time = splits.get("t2", "")
        res.run_time = splits.get("run", "")
    res.raw_data = a
    return res


def _fetch_event_meta_api(event_ref, client: httpx.Client) -> tuple[str, date | None]:
    """Récupère (nom, date) d'un événement via /api/events/{slug}."""
    ev = client.get(f"{API_BASE}/events/{event_ref}", timeout=15).json()
    event_date = None
    raw = ev.get("eventDate", "")
    if raw:
        try:
            event_date = date.fromisoformat(raw[:10])
        except ValueError:
            pass
    return ev.get("title", ""), event_date


def _location_to_slot(location: str) -> str | None:
    """
    Traduit un nom de point intermédiaire sportinnovation en slot triathlon.

    Triathlon (labels français, ex. BayMan) :
      "Temps Natation" → swim, "Transition 1" → t1, "Temps Vélo" → bike,
      "Transition 2" → t2, "Temps CaP" → run

    Duathlon (labels checkpoints) :
      IN1 → swim (course1), OUT1 → t1, VELO1 → bike, OUT2 → t2, IN2 → run (course2)
      CAP*/START/FINISH ignorés (sous-checkpoints, non porteurs du temps de segment)
      (build_splits ré-étiquette swim/run → course1/course2 selon event_type)
    """
    loc = location.lower().strip()
    # Triathlon — labels français (Temps Natation, Transition 1, Temps Vélo…)
    if any(k in loc for k in ("natation", "swim", "nage")):
        return "swim"
    if "transition 1" in loc or loc == "t1":
        return "t1"
    if "transition 2" in loc or loc == "t2":
        return "t2"
    if any(k in loc for k in ("vélo", "velo", "bike", "cycle")):
        return "bike"
    if any(k in loc for k in ("temps cap", "temps cour", "course à pied")):
        return "run"
    # Duathlon — checkpoint labels exacts (évite de matcher CAP1/CAP2)
    if loc == "in1":
        return "swim"
    if loc == "out1":
        return "t1"
    if loc in ("velo1", "velo"):
        return "bike"
    if loc == "out2":
        return "t2"
    if loc == "in2":
        return "run"
    return None


def _intermediates_to_splits(intermediates: list[dict]) -> dict[str, str]:
    """Construit un dict slot→temps depuis la liste d'intermédiaires triés par position."""
    splits: dict[str, str] = {}
    sorted_inter = sorted(intermediates, key=lambda x: x.get("position") or 99)
    for inter in sorted_inter:
        slot = _location_to_slot(inter.get("location") or "")
        if not slot:
            continue
        t = normalize_time(inter.get("officialTime") or "")
        if t and slot not in splits:
            splits[slot] = t
    return splits


def _fetch_athlete_splits(athlete_ref: str | int) -> dict[str, str]:
    """Récupère les splits d'un athlète via /api/results/{ref}?intermediates=1.
    Crée son propre client httpx (thread-safe, pas de partage de connexion).
    """
    try:
        with httpx.Client(follow_redirects=True, timeout=15, headers=HEADERS) as c:
            r = c.get(
                f"{API_BASE}/results/{athlete_ref}",
                params={"intermediates": "1"},
            )
            r.raise_for_status()
            data = r.json()
            return _intermediates_to_splits(data.get("intermediates") or [])
    except Exception:
        logger.warning("Échec récupération splits pour l'athlète %s", athlete_ref, exc_info=True)
        return {}


def _fetch_splits_parallel(
    athletes: list[dict],
    max_workers: int = 20,
) -> dict[str, dict[str, str]]:
    """
    Récupère les splits de tous les athlètes en parallèle.
    Clé du dict retourné : bib → splits dict.
    Chaque worker crée son propre httpx.Client pour éviter les conflits de pool.

    La référence est lue athlète par athlète : le schéma FFA n'en fournit aucune,
    et l'ensemble est alors vide (pas de splits pour ces courses).
    """
    tasks: dict[str, str | int] = {}
    for a in athletes:
        ref = _athlete_ref(a)
        if ref is not None and a.get("bib"):
            tasks[a["bib"]] = ref
    if not tasks:
        return {}

    results: dict[str, dict[str, str]] = {}

    def fetch(bib: str, ref: str | int) -> tuple[str, dict[str, str]]:
        return bib, _fetch_athlete_splits(ref)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(fetch, bib, ref): bib for bib, ref in tasks.items()}
        for future in as_completed(futures):
            bib, splits = future.result()
            results[bib] = splits

    return results


def _race_results_api(
    race_slug: str,
    race_title: str,
    event_name: str,
    event_date: date | None,
    url: str,
    client: httpx.Client,
) -> list[ScrapedResult]:
    """Athlètes d'une course de l'API, nommée « Événement - Course » comme le legacy.

    Le sport est classifié sur le titre de course seul : le nom composé porte le
    nom de l'événement, qui peut mentionner un autre sport (« Triathlon de
    Carnac 2025 - Aquathlon Pupilles » est un aquathlon).
    """
    course_name = _compose_course_name(event_name, race_title)
    event_type = _detect_event_type(race_title)
    athletes = client.get(f"{API_BASE}/races/{race_slug}/results", timeout=20).json()
    if not isinstance(athletes, list):
        # L'API répond 500 avec un objet d'erreur sur certaines courses.
        raise ValueError(f"Résultats indisponibles pour la course {race_slug} : {athletes}")
    splits_by_bib = _fetch_splits_parallel(athletes)
    return [
        _parse_api_athlete(
            a, url, course_name, event_type, event_date,
            splits_by_bib.get(a.get("bib", ""), {}),
        )
        for a in athletes
    ]


def _scrape_results_race(slug: str, url: str, client: httpx.Client) -> list[ScrapedResult]:
    """
    Forme 2026 `results.sportinnovation.fr/race/{slug}` (niveau course) :
    GET /api/races/{slug} → meta (title, eventSlug)
    GET /api/events/{eventSlug} → nom et date de l'événement
    GET /api/races/{slug}/results → liste des athlètes
    """
    meta = client.get(f"{API_BASE}/races/{slug}", timeout=15).json()
    if "error" in meta or not meta.get("slug"):
        raise ValueError(f"Course Sportinnovation introuvable : {slug}")
    event_name = ""
    event_date = None
    event_slug = meta.get("eventSlug", "")
    if event_slug:
        event_name, event_date = _fetch_event_meta_api(event_slug, client)
    return _race_results_api(slug, meta.get("title", ""), event_name, event_date, url, client)


def _scrape_event_api(ident: str, url: str, client: httpx.Client) -> list[ScrapedResult]:
    """Toutes les courses d'un événement de l'API (forme `results…fr/{codeUrl}`).

    Événements et courses sont adressés par `slug` ; l'API n'expose pas d'`id`.
    Trois cas réels de données incomplètes, tous rencontrés en juillet 2026 :
    un événement sans `slug` (injoignable), une course sans `slug` (ignorée),
    et un `/races` en erreur quand deux événements partagent un slug.
    """
    events = client.get(f"{API_BASE}/events", timeout=15).json()
    event = next((e for e in events if ident in (e.get("customUrl"), e.get("slug"))), None)
    if not event:
        raise ValueError(f"Événement {ident} introuvable.")

    event_slug = event.get("slug")
    if not event_slug:
        raise ValueError(
            f"Événement {ident} non adressable : l'API ne lui donne pas de slug. "
            "Ses résultats ne sont probablement publiés que sur le site historique."
        )

    event_name, event_date = _fetch_event_meta_api(event_slug, client)
    races = client.get(f"{API_BASE}/events/{event_slug}/races", timeout=15).json()
    if not isinstance(races, list):
        raise ValueError(f"Liste des courses indisponible pour {ident} : {races}")

    results: list[ScrapedResult] = []
    for race in races:
        race_slug = race.get("slug")
        title = race.get("title", "?")
        if not race_slug:
            logger.warning("Course « %s » ignorée : aucun slug dans l'API.", title)
            continue
        try:
            results.extend(
                _race_results_api(race_slug, title, event_name, event_date, url, client)
            )
        except ValueError:
            # Une course cassée côté fournisseur ne doit pas emporter tout l'événement.
            logger.warning("Course « %s » ignorée : résultats indisponibles.", title)
    return results


def scrape_event_all(url: str) -> list[ScrapedResult]:
    """Fetch all participants for a Sportinnovation event."""
    parsed = urlparse(url)

    with httpx.Client(follow_redirects=True, timeout=30, headers=HEADERS) as client:
        if "results.sportinnovation.fr" in parsed.netloc:
            kind, ident = _classify_results_url(url)
            if kind == "race":
                # Forme 2026 /race/{slug} : une seule course
                return _scrape_results_race(ident, url, client)

            if kind == "detail":
                # Lien individuel /detail/{id} → résout le raceSlug puis importe toute la course
                result_meta = client.get(f"{API_BASE}/results/{ident}", timeout=15).json()
                race_slug = result_meta.get("raceSlug")
                if not race_slug:
                    raise ValueError(f"Impossible de résoudre le raceSlug depuis le détail : {ident}")
                return _scrape_results_race(race_slug, url, client)

            # Forme /{codeUrl} : niveau événement (toutes ses courses).
            return _scrape_event_api(ident, url, client)

        m = re.search(r"/Resultats/(?:DetailMobile/)?(\d+)", parsed.path)
        if not m:
            raise ValueError(f"URL Sportinnovation non reconnue : {url}")
        event_id = m.group(1)

        # Discover all races in the event group via the <select name=raceSearch>
        first_url = f"https://sportinnovation.fr/Evenements/Resultats/{event_id}"
        resp = client.get(first_url, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        race_ids = [
            opt["value"]
            for sel in soup.select("select[name=raceSearch]")
            for opt in sel.find_all("option")
            if opt.get("value", "").isdigit()
        ]
        if not race_ids:
            race_ids = [event_id]

        all_results: list[ScrapedResult] = []
        seen_bibs: set[tuple[str, str]] = set()

        for rid in race_ids:
            race_name, rows, col = _fetch_all_pages(rid, client)
            event_name, event_date = _fetch_race_meta(rid, client)
            course_name = _compose_course_name(event_name, race_name)
            race_url = f"https://sportinnovation.fr/Evenements/Resultats/{rid}"
            for tds in rows:
                bib_idx = col.get("bib", 1)
                bib_val = tds[bib_idx].strip() if bib_idx < len(tds) else ""
                key = (rid, bib_val)
                if key in seen_bibs:
                    continue
                seen_bibs.add(key)
                all_results.append(
                    _parse_html_row(tds, col, race_url, race_name, course_name, event_date)
                )

        return all_results
