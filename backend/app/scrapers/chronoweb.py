"""
chronoweb.com scraper — static HTML, one request per event.

Ground truth for every structural claim below:
`docs/superpowers/specs/2026-07-29-chronoweb-sondage.md` (real probe of
21 events / 89 races / 31 642 rows, 2026-07-29). It outranks this module's
comments: when they disagree, re-probe the site.

Page layout, in one glance:

  h2.date / h2.name                     06/10/2024 — « Triathlon d'Oléron 2024 »
  select.select_epreuve > option[value]  one option per race of the event
  div.results_epreuve.epreuve_<id>       one block per race, all of them served
    div.table-row.head                   9 headers, identical whatever the sport
    a.table-row.body[data-point]         **one row per timing point crossed**

The whole event — every race, every ranking — comes in that single response;
`epreuve`, `cat` and `point` are view parameters the browser uses to toggle a
CSS class. Hence no pagination, no JavaScript, no per-race request.

The difficulty is not the markup but its semantics: a row is a *passage* at a
timing point, not a participant. Rows are therefore grouped by (race, bib), the
total time and both ranks are read at the race's **final** point, and the split
of each point is the published interval — never the cumulative time.
"""
import logging
import re
from dataclasses import dataclass, field
from datetime import date as date_t
from datetime import datetime
from urllib.parse import parse_qs, urlparse

import httpx
from bs4 import BeautifulSoup

from app.scrapers.base import ScrapedResult
from app.scrapers.classify import classify_event_type
from app.scrapers.utils import (
    normalize_rank,
    normalize_time,
    qualify_event_name,
    split_athlete_name,
)

logger = logging.getLogger(__name__)

PROVIDER_NAME = "chronoweb"
BASE_URL = "https://chronoweb.com"
EVENT_PATH = "/resultats_evenement.php"
CATALOGUE_PATH = "/resultats.php"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
}


@dataclass
class EventMeta:
    """Event-level metadata. `city` only ever comes from the catalogue page."""

    name: str = ""
    event_date: date_t | None = None
    city: str = ""


@dataclass
class RaceMeta:
    """One race of the event — becomes one `Course`."""

    race_id: str
    label: str
    event_type: str = ""
    is_relay: bool = False


@dataclass
class Passage:
    """One crossing of one timing point by one competitor — one HTML row."""

    point_id: int
    point_name: str
    cumulative: str = ""
    segment: str = ""
    rank_overall: int | None = None
    rank_category: int | None = None
    speed: str = ""
    rank_gain: str = ""


@dataclass
class Row:
    """A parsed row: its passage plus the identity columns carried alongside."""

    bib: str
    name: str
    category: str
    passage: Passage


@dataclass
class Runner:
    """The union of one bib's passages within one race."""

    bib: str
    name: str
    category: str
    passages: list[Passage] = field(default_factory=list)


_DATE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")

# Un libellé d'épreuve annonce une épreuve par équipes. La catégorie, elle, ne le
# peut pas : `MASC`, `FEM` et `MIXT` servent aussi de catégories « toutes classes »
# sur des épreuves individuelles (research R6).
_RELAY_TOKENS = ("relais", "duo", "team")


def _soup(html: str) -> BeautifulSoup:
    """Parse once, read many: the heaviest page of the panel is 4.5 MB / 1.2 s."""
    return BeautifulSoup(html, "lxml")


def _parse_event_meta(soup: BeautifulSoup) -> EventMeta:
    """Read the event banner: `h2.name` and `h2.date` (dd/mm/yyyy).

    `h2.date` is the only carrier of the date on the whole page, and it is the
    same for every race of the event.
    """
    name = soup.select_one("h2.name")
    raw_date = soup.select_one("h2.date")
    event_date = None
    if raw_date and (m := _DATE.search(raw_date.get_text(strip=True))):
        try:
            event_date = datetime.strptime(m.group(0), "%d/%m/%Y").date()
        except ValueError:
            event_date = None
    return EventMeta(name=name.get_text(strip=True) if name else "", event_date=event_date)


def canonical_url(url: str) -> str:
    """Reduce any chronoweb results URL to the canonical URL of its event.

    Rebuilt from the single `event` parameter rather than stripping the known
    view parameters one by one: an allowlist still holds if the site adds a
    fifth of them tomorrow. Both published forms land here — the event page and
    the individual sheet (`resultats_participant.php`), which is truncated to
    its event since that is precisely the import unit.

    Side effect worth keeping: the four Sheet spellings of Oléron 2024 collapse
    into one `source_url`. Like runnerbreizh, this fixes the `ScrapedResult`
    URL, **not** `Course.source_url` — `import_service` writes the submitted URL
    there, so two spellings still re-scrape.

    Raises ValueError when the URL carries no `event`: a PDF/ZIP archive link
    (one is in the Sheet) or any other page of the site lands here, detection
    being host-based.
    """
    event_id = (parse_qs(urlparse(url).query).get("event") or [""])[0].strip()
    if not event_id:
        raise ValueError(
            "URL chronoweb non exploitable : aucun identifiant d'événement. "
            f"Forme attendue : {BASE_URL}{EVENT_PATH}?event=<id>"
        )
    return f"{BASE_URL}{EVENT_PATH}?event={event_id}"


def _is_relay(label: str) -> bool:
    normalized = label.lower()
    return any(token in normalized for token in _RELAY_TOKENS)


#: Colonnes du tableau, identiques sur les 89 épreuves du panel quelle que soit
#: la discipline. Lues par position : les libellés d'en-tête ne varient pas, mais
#: rien n'oblige la source à les garder — la position, elle, est mesurée.
_CELL_COUNT = 9
_CELL_CUMULATIVE = 1
_CELL_SEGMENT = 5


def _parse_passages(soup: BeautifulSoup, race_id: str) -> list[Row]:
    """Read every row of one race block — one row per timing point crossed.

    The rank is **never** read from the text of the first cell: it stacks the
    overall rank over a hidden category rank, so `get_text()` returns "11" for a
    competitor first overall and first in category, and "11837" for 118th/37th.

    The race is matched on its `data-race` attribute rather than interpolated
    into a CSS selector: `race_id` comes from the page, and a value carrying a
    quote or a space would raise a selector syntax error instead of returning no
    row — the same totality the registry buys with `_url_host`.
    """
    block = next((b for b in soup.select("div.results_epreuve[data-race]")
                  if b.get("data-race") == race_id), None)
    if block is None:
        return []

    rows: list[Row] = []
    for element in block.select("a.table-row.body"):
        cells = element.select("div.table-cell")
        if len(cells) != _CELL_COUNT:
            logger.warning(
                "chronoweb: skipping row with %d cells instead of %d in race %s",
                len(cells), _CELL_COUNT, race_id,
            )
            continue
        name = element.select_one("div.lineinfo_name")
        bib = element.select_one("div.lineinfo_bib")
        overall = element.select_one("div.display_rank_global")
        category_rank = element.select_one("div.display_rank_cat")
        speed = element.select_one("div.table-cell.vmoyenne")
        gain = element.select_one("div.table-cell.gain")
        rows.append(Row(
            bib=bib.get_text(strip=True) if bib else "",
            name=name.get_text(strip=True) if name else "",
            category=(element.get("data-cat") or "").strip(),
            passage=Passage(
                point_id=normalize_rank(element.get("data-point")) or 0,
                point_name=(element.get("data-pointname") or "").strip(),
                cumulative=normalize_time(cells[_CELL_CUMULATIVE].get_text(strip=True)),
                segment=normalize_time(cells[_CELL_SEGMENT].get_text(strip=True)),
                rank_overall=normalize_rank(overall.get_text(strip=True)) if overall else None,
                rank_category=(normalize_rank(category_rank.get_text(strip=True))
                               if category_rank else None),
                speed=speed.get_text(strip=True) if speed else "",
                rank_gain=gain.get_text(strip=True) if gain else "",
            ),
        ))
    return rows


def _group_runners(rows: list[Row]) -> list[Runner]:
    """Fold the rows of one race into one `Runner` per bib.

    Insertion order is kept, so a runner appears where the site first listed it.
    Passages are sorted by `point_id`: the site orders its rows by point, and the
    crossing order is the increasing id order (8 930 participants, no
    counter-example).
    """
    runners: dict[str, Runner] = {}
    for row in rows:
        runner = runners.get(row.bib)
        if runner is None:
            runner = runners[row.bib] = Runner(bib=row.bib, name=row.name,
                                               category=row.category)
        runner.passages.append(row.passage)
    for runner in runners.values():
        runner.passages.sort(key=lambda p: p.point_id)
    return list(runners.values())


def _final_point(rows: list[Row]) -> int:
    """The race's last timing point: the largest `point_id` it published.

    Computed per race, never per runner — the last point *a given runner* reached
    is exactly what a non-finisher lacks, and reading it there would hand an
    abandon the total time and ranks of an intermediate point.
    """
    return max((row.passage.point_id for row in rows), default=0)


def _final_passage(runner: Runner, final_point: int) -> Passage | None:
    """The runner's passage at the race's final point, `None` if it never came.

    Everything the ranking is made of — total time, overall rank, category rank —
    is read there and nowhere else.
    """
    return next((p for p in runner.passages if p.point_id == final_point), None)


#: Suite ordonnée des libellés de points → slots positionnels à remplir, segments
#: et transitions **intercalés** : index 2i = segment du point i, index 2i−1 =
#: transition qui le précède. Les 5 motifs couvrent 88 des 89 épreuves du panel
#: (research R2). C'est le **motif** qui décide du remplissage, jamais le type
#: d'épreuve : le motif est mesuré, le classifieur se trompe (3 épreuves du panel).
_POINT_PATTERNS: dict[tuple[str, ...], tuple[str, ...]] = {
    ("Natation", "Vélo", "Course"): ("swim_time", "t1_time", "bike_time", "t2_time", "run_time"),
    # Duathlon : `build_splits` ré-étiquette ces slots en course1 / bike / course2.
    ("Course", "Vélo", "Course"): ("swim_time", "t1_time", "bike_time", "t2_time", "run_time"),
    ("Natation", "Course"): ("swim_time", "t1_time", "run_time"),
    ("Course",): ("run_time",),
    ("Vélo",): ("bike_time",),
}

#: Libellé publié par la fiche individuelle du site pour un temps mort. Utilisé
#: sur le chemin générique, où la transition s'intercale sous son propre nom.
_TRANSITION_LABEL = "Changement"


def _seconds(time: str) -> int:
    """`"01:31:34"` → 5494. Returns 0 on anything unreadable."""
    parts = time.split(":")
    if len(parts) != 3:
        return 0
    try:
        hours, minutes, secs = (int(p) for p in parts)
    except ValueError:
        return 0
    return hours * 3600 + minutes * 60 + secs


def _format(total: int) -> str:
    return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"


def _race_points(rows: list[Row]) -> list[tuple[int, str]]:
    """Ordered timing points of one race: `[(1, "Natation"), (8, "Vélo"), …]`."""
    points = {row.passage.point_id: row.passage.point_name for row in rows}
    return sorted(points.items())


def _transition(previous: Passage | None, current: Passage | None) -> str:
    """Dead time between two consecutive points: `cumul − intervalle − cumul−1`.

    Empty when either bracketing point is missing — a transition is not invented —
    and when the result is zero, which the site publishes as no transition at all.
    Never negative: verified on the panel's 17 497 gaps.
    """
    if previous is None or current is None:
        return ""
    gap = _seconds(current.cumulative) - _seconds(current.segment) - _seconds(previous.cumulative)
    return _format(gap) if gap > 0 else ""


def _split_times(
    runner: Runner, points: list[tuple[int, str]]
) -> tuple[dict[str, str], list[tuple[str, str]] | None]:
    """Split a runner's passages into either the 5 positional slots or `segments`.

    A recognised point pattern feeds the slots, which `services.mapping.build_splits`
    re-labels per sport — same rendering as every other provider. Anything else
    (the panel's 8-point relay aquathlon) falls back to the generic path: the
    site's own labels, no cap of five, transitions inserted under "Changement".
    Computed transitions apply to **both** paths: a relay dead time is real race
    time, and nothing downstream would recover it.
    """
    by_point = {p.point_id: p for p in runner.passages}
    ordered = [by_point.get(point_id) for point_id, _ in points]
    slots = _POINT_PATTERNS.get(tuple(name for _, name in points))

    if slots is None:
        segments: list[tuple[str, str]] = []
        for index, (_, name) in enumerate(points):
            if index and (dead_time := _transition(ordered[index - 1], ordered[index])):
                segments.append((_TRANSITION_LABEL, dead_time))
            if (passage := ordered[index]) and passage.segment:
                segments.append((name, passage.segment))
        return {}, segments

    times: dict[str, str] = {}
    for index, passage in enumerate(ordered):
        if passage and passage.segment:
            times[slots[2 * index]] = passage.segment
        if index and (dead_time := _transition(ordered[index - 1], passage)):
            times[slots[2 * index - 1]] = dead_time
    return times, None


#: Codes décrivant une **équipe** : ils ne disent rien du genre d'une personne.
#: `MASC` et `FEM`, eux, sont des catégories « toutes classes » et restent lisibles.
_TEAM_CATEGORIES = ("MIXT", "DUOX", "DUOM", "DUOF")


def _gender_from_category(category: str) -> str:
    """Read the gender off the category code, both published conventions.

    FFTRI prefixes it (`MSE`, `FV1`), FFA suffixes it (`SEM`, `V1F`) — and FFA
    masters do both at once: `M0F` is a woman despite its leading `M`. Hence the
    "letter in second position" test before trusting the prefix; without it the
    panel's 36 female masters codes would all come out male.
    """
    code = (category or "").strip().upper()
    if not code or code in _TEAM_CATEGORIES:
        return ""
    if code == "MASC":
        return "M"
    if code == "FEM":
        return "F"
    if code[0] in "MF" and len(code) > 1 and code[1].isalpha():
        return code[0]
    if code[-1] in "MF":
        return code[-1]
    return ""


def _build_result(
    runner: Runner,
    race: RaceMeta,
    meta: EventMeta,
    points: list[tuple[int, str]],
    final_point: int,
    event_url: str,
    event_id: str,
) -> ScrapedResult:
    """Turn one runner into one `ScrapedResult` — one participation of one race.

    Total time and both ranks come from the final point and nowhere else; a
    runner who never reached it keeps neither. Its intermediate ranks stay in
    `raw_data["points"]`, along with the speeds and place gains the model has no
    column for: kept rather than thrown away.

    On a relay the Name column holds a team name, kept whole: the individual
    name/firstname split mangles 52 of the panel's 707 teams (« LIMOGES
    METROPOLE 2 » → firstname « 2 ») and would merge two teams of one club under
    a single identity.
    """
    final = _final_passage(runner, final_point)
    slots, segments = _split_times(runner, points)
    name, firstname = (runner.name, "") if race.is_relay else split_athlete_name(runner.name)

    raw_data: dict = {
        "event_id": event_id,
        "race_id": race.race_id,
        "race_label": race.label,
        "points": [
            {
                "point_id": p.point_id, "name": p.point_name,
                "cumulative": p.cumulative, "segment": p.segment,
                "rank_overall": p.rank_overall, "rank_category": p.rank_category,
                "speed": p.speed, "rank_gain": p.rank_gain,
            }
            for p in runner.passages
        ],
    }
    if meta.city:
        raw_data["city"] = meta.city

    return ScrapedResult(
        source_url=event_url,
        provider=PROVIDER_NAME,
        athlete_name=name,
        athlete_firstname=firstname,
        category=runner.category,
        gender=_gender_from_category(runner.category),
        bib_number=runner.bib,
        event_name=qualify_event_name(meta.name, race.label),
        event_date=meta.event_date,
        event_type=race.event_type,
        rank_overall=final.rank_overall if final else None,
        rank_category=final.rank_category if final else None,
        total_time=final.cumulative if final else "",
        is_relay=race.is_relay,
        segments=segments,
        raw_data=raw_data,
        **slots,
    )


def _fetch(client, url: str) -> str:
    response = client.get(url)
    response.raise_for_status()
    return response.text


def _fetch_city(client, event_id: str) -> str:
    """Read the event's town off the catalogue page, or return "" — never raise.

    The town exists nowhere on the results page. The catalogue weighs 170 kB
    against several MB for a big event's ranking, and the published town
    (« St Georges d'Oléron ») beats the one derived from the event name
    (« Oléron »). Any failure is logged and ignored: a missing town must not cost
    an import.

    Deliberately not memoised: `PROVIDERS` holds module-level singletons, so an
    instance cache would be a process cache — including between tests — for
    ~340 kB saved over the Sheet's two chronoweb events.
    """
    try:
        html = _fetch(client, f"{BASE_URL}{CATALOGUE_PATH}")
    except Exception as exc:
        logger.warning("chronoweb: catalogue unreachable (%s), importing without city", exc)
        return ""

    for row in _soup(html).select("div.table-row"):
        link = row.select_one("div.table-cell.live a[href]")
        if not link:
            continue
        # Le lien porte `event` **et** `epreuve` : on compare le paramètre, pas
        # la chaîne — `?event=323` n'apparaît jamais seul dans le href.
        if (parse_qs(urlparse(link["href"]).query).get("event") or [""])[0] == event_id:
            location = row.select_one("div.table-cell.location")
            return location.get_text(strip=True) if location else ""

    logger.warning("chronoweb: event %s absent from the catalogue, importing without city",
                   event_id)
    return ""


def scrape_event_all(url: str) -> list[ScrapedResult]:
    """Scrape every participant of every race of one chronoweb event.

    One request brings the whole event; a second, optional and non-blocking, goes
    for the town. Never a third, and never the participant page.

    Raises ValueError when the URL carries no event id, and when the id is
    unknown to the site — the latter answers 200 without `h2.name`, which would
    otherwise pass for an event whose ranking is not published yet. That second
    case is a legitimate, empty, error-free import (Chalain 2015).
    """
    event_url = canonical_url(url)
    event_id = (parse_qs(urlparse(event_url).query).get("event") or [""])[0]

    results: list[ScrapedResult] = []
    with httpx.Client(follow_redirects=True, timeout=60, headers=HEADERS) as client:
        soup = _soup(_fetch(client, event_url))
        meta = _parse_event_meta(soup)
        if not meta.name:
            raise ValueError(
                f"Événement chronoweb introuvable : {event_url} — "
                "aucun événement ne porte cet identifiant sur le site."
            )
        meta.city = _fetch_city(client, event_id)

        for race in _parse_races(soup, meta):
            rows = _parse_passages(soup, race.race_id)
            if not rows:
                continue
            points, final_point = _race_points(rows), _final_point(rows)
            results.extend(
                _build_result(runner, race, meta, points, final_point, event_url, event_id)
                for runner in _group_runners(rows)
            )
    return results


def _parse_races(soup: BeautifulSoup, meta: EventMeta) -> list[RaceMeta]:
    """Read one `RaceMeta` per option of the race selector.

    The selector is authoritative even when a race publishes no ranking at all
    (Chalain 2015): an event named but empty is a legitimate, error-free import.
    """
    races = []
    for option in soup.select("select.select_epreuve option[value]"):
        label = option.get_text(strip=True)
        races.append(RaceMeta(
            race_id=option["value"],
            label=label,
            event_type=classify_event_type(label, contexte=meta.name),
            is_relay=_is_relay(label),
        ))
    return races
