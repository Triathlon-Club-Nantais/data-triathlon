"""
runnerbreizh.fr scraper — static paginated HTML.

Ground truth for every structural claim below:
`docs/superpowers/specs/2026-07-27-runnerbreizh-sondage.md` (real probe of
7 events, 2026-07-27). It outranks this module's comments: when they disagree,
re-probe the site.

Page layout, in one glance:

  table#titre-courses     one row, the event banner (date in abbreviated English,
                          name, city, distances, optional timekeeper mention)
  table.tableau-courses   one header row, then up to 50 result rows of 8 cells

The 8 column labels are **identical whatever the sport** and are misleading:
in a duathlon "1ère épreuve" is a run, in an aquathlon the "Vélo" cell is empty
but still displayed. Columns are therefore read by position and re-labelled per
sport downstream by `services.mapping.build_splits` — never by header label.
"""
import logging
import re
from dataclasses import dataclass
from datetime import date
from urllib.parse import parse_qs, urlencode, urlparse

import httpx  # noqa: F401 — tests/test_runnerbreizh.py patche `runnerbreizh.httpx.Client`
from bs4 import BeautifulSoup

from app.core import http
from app.scrapers.base import ScrapedResult
from app.scrapers.classify import classify_event_type
from app.scrapers.utils import normalize_rank, normalize_time
from app.scrapers.utils import split_athlete_name as _split_name

logger = logging.getLogger(__name__)

PROVIDER_NAME = "runnerbreizh"
BASE_URL = "https://www.runnerbreizh.fr"
RESULTS_PATH = "/requetetriathlons.php"
EVENT_PARAM = "CourseFichierGpsNom"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
}

_TITLE_DATE = re.compile(r"du\s+(\d{1,2})/(\d{1,2})/(\d{4})")
_TITLE_KM = re.compile(r"([\d.,]+)\s*KM", re.I)
# Trailing per-segment distances: « … M (1.5/38/10) ». Digits, separators and
# spaces only — a parenthesis holding words is part of the event name.
_NAME_DISTANCES = re.compile(r"\s*\([\d.,/\s]+\)\s*$")

_SEGMENT_RANK = re.compile(r"P:\s*(\d+)")
_PERCENT = re.compile(r"(\d+[.,]?\d*\s*%)")
_SPEED = re.compile(r"(\d+[.,]?\d*\s*km/h)", re.I)
# `<b>1</b>/322` or `<b>1</b>/SEM`: whatever follows the first slash.
_RANK_QUALIFIER = re.compile(r"/\s*([^\n]+)")
# Team categories: « M+M », « M+F ».
_TEAM_CATEGORY = re.compile(r"[A-Z]\s*\+\s*[A-Z]", re.I)
# Rank trend: « \u2197 3 », « \u2198 56 », or a bare « = ».
_TREND = re.compile(r"[\u2197\u2198]\s*\d+|=")
_RUNNER_ID = re.compile(r"[?&]di=(\d+)")
#: Label of a row the site could not attach to a runner: « ?DOSSARD #9998 ».
_UNMATCHED_PREFIX = "?DOSSARD"
#: Event-name markers of a team event (the site still announces it as a triathlon).
_RELAY_NAME_HINTS = ("duo", "relais", "relay", "equipe", "équipe")

#: Every ranking row has 8 cells, whatever the sport (probed on 7 events).
_EXPECTED_CELLS = 8

#: Rows per page, fixed by the site. A page holding fewer is the last one.
_PAGE_SIZE = 50

#: 50 rows per page; the cap only guards against a site repeating its last page.
#: The largest event probed (2704 ranked) needs 55, hence the margin.
_MAX_PAGES = 200

#: Timekeepers we scrape natively, normalised for comparison with the credit line.
_SUPPORTED_TIMEKEEPERS = frozenset({
    "breizhchrono", "klikego", "timepulse", "wiclax", "prolivesport",
    "sportinnovation", "raceresult", "chronoplace", "chronosmetron",
    "chronowest",
})


def canonical_url(url: str) -> str:
    """Reduce any runnerbreizh results URL to its canonical, page-1 form.

    Rebuilt from the single `CourseFichierGpsNom` parameter rather than stripping
    the known view parameters one by one: an allowlist still holds if the site adds
    a fourth of them tomorrow. It matters because 8 of the 10 links really present
    in the Sheet carry `&page=2` or `&page=3`, some with `&tricourse=` (sort order)
    and `&Sexe=` (gender filter) — and `Sexe=F` returns a **subset**, so keeping it
    would silently truncate the import.

    Side effect worth keeping: `Course.source_url` becomes identical for the two
    Sheet spellings of one event, hence a single TTL cache key.

    Raises ValueError when the URL carries no event id — a runner profile page
    (`triathlons.php?CoureurNom=…`) or any other page of the site lands here,
    since detection is host-based.
    """
    query = parse_qs(urlparse(url).query)
    event_id = (query.get(EVENT_PARAM) or [""])[0].strip()
    if not event_id:
        raise ValueError(
            "URL runnerbreizh.fr non supportée : elle ne désigne pas une épreuve. "
            f"Forme attendue : {BASE_URL}{RESULTS_PATH}?{EVENT_PARAM}=<identifiant> "
            "(une page de résultats, pas une fiche coureur)."
        )
    return f"{BASE_URL}{RESULTS_PATH}?{urlencode({EVENT_PARAM: event_id})}"


def _page_url(url: str, page: int) -> str:
    return f"{url}&page={page}"


@dataclass(frozen=True)
class EventMeta:
    """Event-level facts, identical for every row of a page."""

    name: str
    event_date: date | None
    city: str
    distance_km: float | None
    event_type: str


@dataclass(frozen=True)
class SegmentCell:
    """One segment cell: split time, plus runnerbreizh's own analysis of it."""

    time: str
    rank: int | None
    gap: str
    speed: str


def _parse_segment_cell(cell) -> SegmentCell:
    """Split a segment cell into its four published values.

    Shape: `<b>00:23:14</b><br/>P:2<br/><span>0.62%</span><br/><span>3.87 km/h</span>`.
    Only the `<b>` is a split time; rank, gap to the segment winner and average
    speed have no column in our model and travel in `raw_data`.

    An empty cell (aquathlon keeps its bike column displayed) yields empty values,
    never an exception.
    """
    time = ""
    if bold := cell.find("b"):
        time = normalize_time(bold.get_text(strip=True))

    text = cell.get_text(" ", strip=True)
    rank = None
    if m := _SEGMENT_RANK.search(text):
        rank = normalize_rank(m.group(1))
    gap = m.group(1) if (m := _PERCENT.search(text)) else ""
    speed = m.group(1) if (m := _SPEED.search(text)) else ""
    return SegmentCell(time=time, rank=rank, gap=gap, speed=speed)


def _parse_rank_pair(cell) -> tuple[int | None, str]:
    """Read a `<b>rank</b>/qualifier` cell → (rank, qualifier).

    Serves both the overall ranking cell (`1/322`, qualifier = field size) and the
    category one (`1/SEM`, qualifier = category label). The qualifier is whatever
    follows the first slash, up to the end of the line.

    The `<b>` is not guaranteed: on a female row the site wraps the whole category
    cell in a colour `<span>` and drops the bold tag (`<span>29/SEF</span>`). Both
    values are therefore read from the text, the bold tag being only a shortcut —
    reading the rank from the first child alone lost it for every female row while
    the qualifier of the same cell came through.
    """
    text = cell.get_text("\n", strip=True)
    if bold := cell.find("b"):
        rank = normalize_rank(bold.get_text(strip=True))
    else:
        rank = normalize_rank(text.split("/", 1)[0])
    qualifier = ""
    if m := _RANK_QUALIFIER.search(text):
        qualifier = m.group(1).strip()
    return rank, qualifier


def _trend(cell) -> str:
    """Rank trend mark of a cell: `↗ 3`, `↘ 56`, or `=` when the rank held.

    Encoded `&#8599;` / `&#8600;` in the source. Kept verbatim in `raw_data`:
    re-encoding it as a signed integer would invent a convention the site never
    published (does `=` mean 0, or "not comparable"?).
    """
    if m := _TREND.search(cell.get_text(" ", strip=True)):
        return " ".join(m.group(0).split())
    return ""


def _percent(cell) -> str:
    return m.group(1) if (m := _PERCENT.search(cell.get_text(" ", strip=True))) else ""


def _runner_id(cell) -> str:
    """Site-internal runner id (`di=709927`), only present for registered runners."""
    link = cell.find("a", href=True)
    if link and (m := _RUNNER_ID.search(link["href"])):
        return m.group(1)
    return ""


def _is_relay(event_name: str, category: str) -> bool:
    """True when the row belongs to a team rather than a lone athlete.

    Two independent signals, either one is enough: the event name qualifies the
    whole event (« TriBreizh en Duo », « … en Relais »), the category confirms it
    row by row (« M+M », « M+F »). The site itself announces such events as plain
    triathlons, so neither signal can be skipped.
    """
    name = (event_name or "").lower()
    if any(hint in name for hint in _RELAY_NAME_HINTS):
        return True
    return bool(_TEAM_CATEGORY.search(category or ""))


def _split_identity(label: str) -> tuple[str, str]:
    """Split a name cell into (last name, first name).

    « ?DOSSARD #9998 » marks a row the site could not match to a runner: the whole
    label becomes the last name, with no first name. Running it through
    `split_athlete_name` would yield (« ?DOSSARD », « #9998 »), and the UI would
    render an internal id as somebody's first name.
    """
    if label.startswith(_UNMATCHED_PREFIX):
        return label, ""
    return _split_name(label)


def _gender_from_category(category: str) -> str:
    """Trailing letter of an individual category: `S3M` → M, `SEF` → F.

    Team categories (`M+M`, `M+F`) are deliberately left out: their trailing
    letter describes the **team** composition, not the person on the row — a
    mixed duo would otherwise label both members with the same gender, and one
    of the two wrongly.
    """
    if not category or _TEAM_CATEGORY.search(category):
        return ""
    last = category.strip()[-1:].upper()
    return last if last in ("M", "F") else ""


def _parse_row(row, meta: EventMeta, source_url: str, page: int) -> "ScrapedResult | None":
    """One ranking row → one `ScrapedResult`, or None if the row is off-format.

    Columns are positional (see module docstring): 0 name, 1 total time,
    2/3/5 segments, 4 rank before the closing run, 6 overall ranking,
    7 category. A row whose cell count differs is skipped and logged rather than
    read blind — a shifted column would silently store a speed as a split.
    """
    cells = row.find_all("td")
    if len(cells) != _EXPECTED_CELLS:
        logger.warning(
            "runnerbreizh: skipping off-format row (%d cells, expected %d) on %s",
            len(cells), _EXPECTED_CELLS, source_url,
        )
        return None

    name, firstname = _split_identity(cells[0].get_text(" ", strip=True))

    first, bike, run = (_parse_segment_cell(cells[i]) for i in (2, 3, 5))
    before_run_rank, _ = _parse_rank_pair(cells[4])
    rank_overall, field_size = _parse_rank_pair(cells[6])
    rank_category, category = _parse_rank_pair(cells[7])

    result = ScrapedResult(
        source_url=source_url,
        provider=PROVIDER_NAME,
        athlete_name=name,
        athlete_firstname=firstname,
        category=category,
        gender=_gender_from_category(category),
        is_relay=_is_relay(meta.name, category),
        event_name=meta.name,
        event_date=meta.event_date,
        event_type=meta.event_type,
        distance_km=meta.distance_km,
        rank_overall=rank_overall,
        rank_category=rank_category,
        total_time=normalize_time(cells[1].get_text(" ", strip=True)),
        # Positional slots, re-labelled per sport by `services.mapping.build_splits`.
        # Transitions are not published, so T1/T2 stay empty.
        swim_time=first.time,
        bike_time=bike.time,
        run_time=run.time,
    )
    result.raw_data = {
        "page": page,
        # La commune du titre, faute de champ ville dans `ScrapedResult` : elle est
        # plus juste que celle que la carte déduit du nom d'épreuve
        # (« Pléneuf-Val-André » contre « Val-André »), et la jeter serait perdre
        # la meilleure valeur disponible.
        "city": meta.city,
        "runner_id": _runner_id(cells[0]),
        "field_size": normalize_rank(field_size),
        "rank_trend": _trend(cells[6]),
        "percentile": _percent(cells[6]),
        "rank_before_run": before_run_rank,
        "rank_before_run_trend": _trend(cells[4]),
        "segment_details": [
            {
                "position": position,
                "time": segment.time,
                "rank": segment.rank,
                "gap": segment.gap,
                "speed": segment.speed,
            }
            for position, segment in enumerate((first, bike, run), start=1)
        ],
    }
    return result


def _result_rows(html: str) -> list:
    """Data rows of the ranking table, header excluded.

    An empty list is the pagination stop signal: past the last page the site still
    answers 200, with `table.tableau-courses` reduced to its single header row.
    A missing table yields the same empty list rather than raising — an unexpected
    page must not crash a batch mid-flight.
    """
    soup = BeautifulSoup(html, "lxml")
    table = soup.select_one("table.tableau-courses")
    if table is None:
        return []
    return table.find_all("tr")[1:]


def _parse_title(html: str) -> EventMeta:
    """Read event metadata from the document `<title>`.

    The title is the only French-formatted carrier (`07/09/2025`); the banner
    renders the date in abbreviated English (`07 Sep 2025`), unusable as-is.

    Shape: `Résultats de la course du <date> - <name> - <city> - <km>KM - Type : <sport>`.
    Split from the right: the last three fields are single-token, whereas an event
    name may itself contain " - ".
    """
    soup = BeautifulSoup(html, "lxml")
    raw = (soup.title.get_text() if soup.title else "").strip()
    raw = " ".join(raw.split())
    if not raw:
        return EventMeta("", None, "", None, "")

    head, city, km_part, type_part = (raw.rsplit(" - ", 3) + ["", "", ""])[:4]
    name = head.split(" - ", 1)[1] if " - " in head else ""
    name = _NAME_DISTANCES.sub("", name).strip()

    event_date = None
    if m := _TITLE_DATE.search(head):
        day, month, year = (int(g) for g in m.groups())
        try:
            event_date = date(year, month, day)
        except ValueError:
            logger.warning("runnerbreizh: unparsable date in title %r", raw)

    distance_km = None
    if m := _TITLE_KM.search(km_part):
        distance_km = float(m.group(1).replace(",", "."))

    announced = type_part.split(":", 1)[1].strip() if ":" in type_part else ""

    return EventMeta(
        name=name,
        event_date=event_date,
        city=city.strip(),
        distance_km=distance_km,
        # The announced sport prefixes the name rather than replacing the
        # classifier: `classify_event_type` tests composite sports first, so a
        # name carrying its own discipline still wins, and the size (S/M/L) —
        # which the announced type never carries — is kept.
        event_type=classify_event_type(f"{announced} {name}".strip()),
    )


def _fetch(client, url: str) -> str:
    response = client.get(url)
    response.raise_for_status()
    return response.text


def _warn_if_republished(html: str, url: str) -> str:
    """Log the third-party timekeeper the page credits, when we support it.

    Like `fftri.t2area.com`, runnerbreizh republishes results produced elsewhere,
    and the original provider often has richer data — Breizh Chrono publishes bibs
    **and** clubs, both missing here. The mention only links the timekeeper's home
    page, never the event, so no source URL is reconstructible: only the operator
    can supply the native link, hence a log rather than a fan-out.
    """
    soup = BeautifulSoup(html, "lxml")
    banner = soup.select_one("table#titre-courses")
    if banner is None or "chronométrée par" not in banner.get_text(" ", strip=True).lower():
        return ""
    known = {img.get("alt", "").strip() for img in banner.find_all("img") if img.get("alt")}
    for name in sorted(known):
        if name.lower().replace(" ", "") in _SUPPORTED_TIMEKEEPERS:
            logger.warning(
                "runnerbreizh: %s republishes results timed by %s, which we support "
                "natively (bibs and clubs included) — %s",
                url, name, "ask the operator for the timekeeper's own URL",
            )
            return name
    return ""


def _require_event_name(meta: EventMeta, rows: list, url: str) -> None:
    """Refuse une page 1 dont le `<title>` n'a livré aucun nom d'épreuve.

    Deux causes, deux messages, parce que l'opérateur n'y répond pas de la même
    façon :

    - **aucune ligne** : l'identifiant d'épreuve n'existe pas. Le site répond 200
      avec un titre vide, ce qui passerait sinon pour une épreuve sans classement
      publié — à lui de corriger l'URL ;
    - **des lignes** : le titre existe mais son format a changé. Il est lu par
      position depuis la droite, donc un champ manquant décale tout : le nom sort
      vide, la ville prend sa place et le type perd sa taille, la date restant
      juste. `import_service._require_event_name` rattrape bien le nom vide, mais
      en aval, sans pouvoir dire lequel des deux cas s'est produit — et le type
      dégradé, lui, ne serait rattrapé par personne.
    """
    if meta.name:
        return
    if rows:
        raise ValueError(
            f"Format de titre runnerbreizh.fr inattendu sur {url} : nom d'épreuve "
            "illisible alors que le classement est publié — les champs du titre ont "
            "changé de place."
        )
    raise ValueError(
        f"Épreuve runnerbreizh.fr introuvable : {url} — "
        "l'identifiant d'épreuve n'existe pas sur le site."
    )


def _require_complete_ranking(
    rows_seen: int, last_page_was_full: bool, results: list[ScrapedResult], url: str
) -> None:
    """Refuse un classement qui s'arrête avant le total annoncé par le site.

    La pagination s'arrête sur la première page sans ligne, ce qui confond deux
    situations : la fin du classement, et une page intermédiaire servie vide ou en
    200 sans table. Dans le second cas les rangs lus restent contigus (1..150), donc
    l'indice de fiabilité ne voit aucune anomalie et l'épreuve tronquée passe pour
    complète — un silence, pas une erreur.

    Deux précautions contre le faux positif :

    - on ne juge que si la dernière page lue était **pleine**. Une page incomplète
      est la fin publiée, quel que soit le total annoncé ;
    - on compare un **plancher**, pas une égalité : en relais le total compte des
      équipes (31) alors que les pages portent une ligne par équipier (62).

    On compte les lignes vues, pas les résultats retenus : une ligne hors format est
    déjà signalée par ailleurs, et la déduire ici ferait échouer l'épreuve pour une
    tout autre raison.
    """
    if not last_page_was_full:
        return
    announced = max((r.raw_data.get("field_size") or 0 for r in results), default=0)
    if rows_seen >= announced:
        return
    raise ValueError(
        f"Classement runnerbreizh.fr incomplet sur {url} : {rows_seen} lignes lues "
        f"pour {announced} classés annoncés, et la pagination s'est arrêtée sur une "
        "page pleine. Import refusé plutôt que tronqué — réessayez."
    )


def scrape_event_all(url: str) -> list[ScrapedResult]:
    """Scrape every ranked participant of one runnerbreizh event.

    Walks `&page=N` from 1 and stops at the first page whose ranking table holds
    no data row. The announced field size is **not** a usable bound: in a relay it
    counts teams (31) while the pages hold one row per team member (62).

    Raises ValueError when the URL is not an event results page, or when the event
    id is unknown to the site — the latter answers 200 with a blank `<title>`, which
    would otherwise pass for an event with no published ranking.
    """
    event_url = canonical_url(url)
    results: list[ScrapedResult] = []
    meta: EventMeta | None = None
    # Both are read from page 1 only, but they are bound here: a variable that
    # exists solely because the first iteration is guaranteed to assign it is one
    # loop reshuffle away from a NameError.
    timekeeper = ""
    rows_seen = 0
    last_page_was_full = False

    with http.client(timeout=30, headers=HEADERS) as client:
        for page in range(1, _MAX_PAGES + 1):
            html = _fetch(client, _page_url(event_url, page))
            if meta is None:
                meta = _parse_title(html)
                timekeeper = _warn_if_republished(html, event_url)

            rows = _result_rows(html)
            if page == 1:
                _require_event_name(meta, rows, event_url)
            if not rows:
                break

            rows_seen += len(rows)
            last_page_was_full = len(rows) == _PAGE_SIZE
            for row in rows:
                if result := _parse_row(row, meta, event_url, page):
                    if timekeeper:
                        result.raw_data["timekeeper"] = timekeeper
                    results.append(result)
        else:
            raise ValueError(
                f"Pagination runnerbreizh.fr au plafond de {_MAX_PAGES} pages sur "
                f"{event_url} : le site répète probablement sa dernière page. Import "
                "refusé — les lignes déjà lues sont vraisemblablement dupliquées."
            )

    _require_complete_ranking(rows_seen, last_page_was_full, results, event_url)
    return results
