"""
MYLAPS Sporthive scraper — public JSON API (issue #53).

The API lives on `eventresults-api.speedhive.com/sporthive`: MYLAPS folded
Sporthive into Speedhive, and the former host
`eventresults-api.sporthive.com` no longer answers (its TLS certificate stopped
covering the name). No API key, no cookie: plain `GET`, no Playwright.

Five structural traps of the source, never to reintroduce (cf.
docs/superpowers/specs/2026-07-29-sporthive-sondage.md, ground truth — it
outranks the design and the plan on any factual disagreement):

  1. `races/{n}` in the Sheet URL is a **local ordinal** (`activeRaceId`), not
     the `raceId`. `GET /races/1` answers **200** and returns an unrelated 2015
     event: the real `raceId` is the `id` field (19-digit snowflake) from
     `/events/{eventId}/races`.
  2. `size` is capped at 10 server-side (`size=50` → 400). `count` and
     `offset` are accepted but silently ignored: one could believe paginating
     by 50 while re-reading the same 10 rows forever.
  3. Status lives in `validity` (`DNF` / `DNS` / `DQ`); the `dns` and `dsq`
     booleans are `false` on 10,360 measured rows out of 10,360.
  4. `legs[].sportName` isn't normalized and is `null` on 23% of legs:
     `legs[].type` is the only reliable discriminant (`Swimming`, `Cycling`,
     `Running`, `Transition`).
  5. `tags` is a search index, not a name/first-name split.

Endpoints consumed (cf. specs/004-sporthive-scraper/contracts/provider-contract.md):

    GET /events/{eventId}
    GET /events/{eventId}/races
    GET /races/{raceId}/participants?page=N&size=10

Two failure scopes, and that is the structuring choice of the module. A race
whose ranking is incomplete is **dropped** (`_IncompleteRanking`, a private type
caught by the loop) so the event's other races still import; the **event** is
refused (`ValueError`, propagated) on an unreadable URL, an unknown event, a
pagination cap hit, or when no race could be read at all.
"""
import logging
import re
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime
from urllib.parse import urlparse

import httpx

from .base import STATUS_DNF, STATUS_FINISHER, ScrapedResult
from .classify import classify_event_type
from .utils import (
    derive_status_from_label,
    normalize_rank,
    normalize_time,
    qualify_event_name,
    split_athlete_name,
)

logger = logging.getLogger(__name__)

#: Must stay equal to `registry.SporthiveProvider.name`: it is what
#: `rescrape-db --provider sporthive` filters on, and a drift would make the
#: option select nothing without saying so. A test pins the two together.
_PROVIDER = "sporthive"

_API_BASE = "https://eventresults-api.speedhive.com/sporthive"
# The API is public: no key, no cookie, no `Origin` required. A browser
# User-Agent all the same, like every other scraper of the project.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
}
# size=50 gets a 400 ("The size value cannot be greater than 10") server-side.
_PAGE_SIZE = 10
# Hard cap: the worst case measured on the panel needs 269 requests for one race.
_MAX_PAGES = 1000

# The three façades measured, in one pattern (D3):
#   results.sporthive.com/events/{id}/…      the Sheet's form
#   sporthive.com/events/s/{id}/…            where the 307 redirect lands
#   results.sporthive.com/en/events/{id}/…   served 200, no redirect
# Everything after the id is absorbed and **dropped**: `/races/{n}` is a local
# ordinal, `/bib/{b}` and `/bib/{b}/split` name a single row. None of the three
# is an API identifier, so none has a way out of this function (trap n°1).
_PATH_RE = re.compile(
    r"^/(?:[a-z]{2}(?:-[a-zA-Z]{2})?/)?events/(?:s/)?(?P<event_id>\d+)(?:/.*)?$"
)

_FORME_ATTENDUE = (
    "URL Sporthive illisible : aucun identifiant d'événement dans le chemin. "
    "Forme attendue : https://results.sporthive.com/events/<id>[/races/<n>] "
    "(ou https://sporthive.com/events/s/<id>), où <id> est numérique."
)


def _parse_url(url: str) -> str:
    """The event id, and nothing else (D1, D3, FR-002).

    Deliberately returns a bare `str` and not a `(event_id, race_ordinal)`
    pair: the whole event is imported anyway (FR-005), so resolving the URL's
    race would be dead code — and a dead guard eventually gets removed by
    mistake. `GET /races/1` answers **200** with an unrelated 2015 event, so
    the ordinal must have no channel to the API at all (FR-004).

    `urlparse` raises on a malformed IPv6 host: caught here so the caller
    always gets the message naming the expected form, never a stray
    `ValueError` from the stdlib.
    """
    try:
        path = urlparse(url).path or ""
    except ValueError:
        raise ValueError(_FORME_ATTENDUE) from None
    lu = _PATH_RE.match(path)
    if not lu:
        raise ValueError(_FORME_ATTENDUE)
    return lu.group("event_id")


def _fetch_json(
    client: httpx.Client, path: str, params: dict | None = None, *, introuvable: str = ""
):
    """A `GET` on the API. Only a 404 is translated, and only where asked.

    A 5xx is not a link problem: turning it into `ValueError` would make it read
    as one in the CLI failure detail, so it goes through untouched.

    `introuvable` is opt-in per route on purpose. A 404 does not mean the same
    thing everywhere: on `/events/{id}` it says "this link points at nothing",
    which the operator can act on; on a ranking page it would be an anomaly of
    the source, not of the link.
    """
    response = client.get(f"{_API_BASE}{path}", params=params)
    if introuvable and response.status_code == 404:
        raise ValueError(introuvable)
    response.raise_for_status()
    return response.json()


def _fetch_event(client: httpx.Client, event_id: str) -> dict:
    """Event metadata: name, ISO date, type, location, country code.

    The message is in French: it travels through `ScraperError` and the front
    shows it verbatim (mixed `DomainError` case of principle I).
    """
    return _fetch_json(
        client,
        f"/events/{event_id}",
        introuvable=(
            f"Événement Sporthive introuvable (id {event_id}) : la source ne "
            "connaît pas cet identifiant. Vérifier le lien — un identifiant "
            "d'événement est attendu, pas un identifiant de course."
        ),
    )


def _fetch_races(client: httpx.Client, event_id: str) -> list[dict]:
    """The event's races — a **bare array**, the only unpaginated route.

    `id` (a 19-digit snowflake) is the identifier the API expects; the
    `activeRaceId` alongside it is the ordinal the browser URL shows. Reading
    the list is the only way to go from one to the other.
    """
    charge = _fetch_json(client, f"/events/{event_id}/races")
    return charge if isinstance(charge, list) else []


def _iter_participants(client: httpx.Client, race_id: str) -> Iterator[dict]:
    """Every ranked participant of a race, page by page.

    Two stop criteria, one cap, and deliberately **no** use of the announced
    totals (D4, FR-007, FR-009):

      - `last: true` is the source's own criterion, and the nominal one;
      - an empty `content` covers a page served past the end;
      - `_MAX_PAGES` covers the case where both are wrong. Raising beats
        yielding rows that are probably duplicated — a refused import replays,
        a ranking silently truncated and marked reliable does not.

    `totalPages` / `totalElements` are never read: bounding the loop on a total
    announced by the source is the mistake runnerbreizh paid for. They serve to
    **check** afterwards, which the completeness guard does on
    `classificationsCount`.

    `size` is pinned to 10 because the server rejects more (`size=50` → 400).
    `count` / `offset` — the pair the issue announced — are accepted and
    silently ignored, so paginating with them re-reads the same ten rows.
    """
    for page in range(_MAX_PAGES):
        charge = _fetch_json(
            client,
            f"/races/{race_id}/participants",
            params={"page": page, "size": _PAGE_SIZE},
        )
        lignes = charge.get("content") or []
        if not lignes:
            return
        yield from lignes
        if charge.get("last"):
            return
    raise ValueError(
        f"Épreuve Sporthive {race_id} : la pagination n'a pas terminé en "
        f"{_MAX_PAGES} pages ({_MAX_PAGES * _PAGE_SIZE} participants). "
        "Import refusé plutôt que tronqué — il est rejouable."
    )


class _IncompleteRanking(Exception):
    """A race whose ranking could not be read in full — **race** scope.

    A private type, not a `ValueError` filtered on its message: sorting
    failures by text breaks at the first rephrasing, and the infrastructure
    already wraps the scraper's `ValueError`s (`import_service._scrape_all`).
    The triage in `scrape_event_all` is therefore on the **type**.

    Carries the numbers the log line needs rather than a formatted message: the
    decision to drop the race belongs to the loop, so the wording does too.
    """

    def __init__(self, race_name: str, active_race_id, lus: int, annonces: int):
        super().__init__(f"{race_name}: read {lus} of {annonces}")
        self.race_name = race_name
        self.active_race_id = active_race_id
        self.lus = lus
        self.annonces = annonces


# ---------------------------------------------------------------------------
# Scalars
# ---------------------------------------------------------------------------


def _time(raw) -> str:
    """A duration, fraction truncated, `00:00:00` read as absent (D6).

    The truncation must happen **before** `normalize_time`, whose `HH:MM:SS`
    pattern is anchored on the end of the string: `00:57:33.2510000` would come
    back verbatim, fraction included, and land in the database. The source
    publishes `HH:MM:SS`, `HH:MM:SS.fffffff` (totals) and `HH:MM:SS.fff`
    (`legDuration`) depending on the race.

    `00:00:00` is what non-finishers carry — same convention as T2Area. Reading
    it as empty is what keeps `mapping.derive_status` from calling an abandon a
    finisher.
    """
    if not raw:
        return ""
    normalise = normalize_time(str(raw).strip().split(".")[0])
    return "" if normalise == "00:00:00" else normalise


def _rank(raw) -> int | None:
    """A rank, `0` read as absent (D12).

    `overallPosition == 0` means "not ranked" — 172 rows of the panel, all
    non-finishers. `normalize_rank` alone returns `0`, which the front displays
    as a place.
    """
    return normalize_rank(raw) or None


def _status(participant: dict, total_time: str, rank_overall: int | None) -> str:
    """The sporting status, from `validity` alone (D5, trap n°3).

    `dns` and `dsq` are `false` on 10 360 rows out of 10 360, including the 35
    whose `validity` is `"DNS"`: they are dead fields, and trusting them misses
    every status. `derive_status_from_label` already translates the three real
    tokens, `DQ` included.

    When the source says nothing **and** no time could be kept, the scraper
    takes a side rather than leaving it to `mapping.derive_status`, whose
    fallback ("finisher if a total time, else DNF") would show the 73 timeless
    but **ranked** rows of the panel as abandons (FR-014a). `""` remains the
    answer whenever a time exists: the scraper only speaks when it knows more
    than the heuristic.
    """
    status = derive_status_from_label(participant.get("validity") or "")
    if not status and not total_time:
        status = STATUS_FINISHER if rank_overall is not None else STATUS_DNF
    return status


# ---------------------------------------------------------------------------
# Segments
# ---------------------------------------------------------------------------

#: `legs[].type` → label stored, a closed vocabulary (D7). `sportName` is
#: **never** read: entered by the timekeeper, unnormalised (`SWIM` / `Swim` /
#: `T1`), and `null` on 5 635 of the 24 042 legs of the panel. `type` is present
#: 24 042 times out of 24 042.
#: Labels in French because they become column headers in the front
#: (`lib/utils/splits.ts`, generic path) and the source vocabulary is closed, so
#: the translation is safe — unlike a free-form label, which ok-time renders
#: verbatim.
_LEG_LABELS = {
    "swimming": "natation",
    "transition": "transition",
    "cycling": "vélo",
    "running": "course à pied",
}


def _segments(legs) -> list[tuple[str, str]]:
    """One segment per leg, in published order, empty durations dropped.

    The generic `segments` path rather than the five positional slots: kids'
    races publish 4 legs (a single transition), and a positional mapping would
    land their run in the `t2` slot.

    A leg with an empty duration is dropped (D8): a non-finisher publishes a
    single `Running` leg at `00:00:00` whose only split is `Start`. Filtering on
    the duration rather than the status also covers an untimed leg on a
    finisher, with no special case. An unknown `type` — never observed — is
    rendered verbatim rather than losing the time.
    """
    segments: list[tuple[str, str]] = []
    for leg in legs or []:
        duree = _time(leg.get("legDuration"))
        if not duree:
            continue
        brut = (leg.get("type") or "").strip()
        segments.append((_LEG_LABELS.get(brut.lower(), brut), duree))
    return segments


# ---------------------------------------------------------------------------
# Event metadata
# ---------------------------------------------------------------------------

#: An event is a relay if its **race** name says so (D10). Decided per race and
#: not per participant, otherwise `Course.is_relay` and `Participation.is_relay`
#: diverge with the read order (ok-time precedent). Word-start match on the
#: accent-stripped name, so plurals follow (`Équipes`, `Relays`).
_RELAY_RE = re.compile(r"\b(relais|relay|equipe|team|duo)")


def _sans_accents(texte: str) -> str:
    decompose = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in decompose if not unicodedata.combining(c))


def _is_relay(race_name: str) -> bool:
    return bool(_RELAY_RE.search(_sans_accents(race_name).lower()))


def _event_date(raw) -> date | None:
    """The event date, from the ISO string — no French parsing (FR-020)."""
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw)).date()
    except ValueError:
        logger.warning("Sporthive: unreadable event date %r", raw)
        return None


@dataclass(frozen=True)
class _RaceContext:
    """The `ScrapedResult` fields shared by every participation of one race.

    Computed once per race rather than per participant: `classify_event_type`
    and the relay pattern would otherwise run on every one of the 955 rows for
    an answer that cannot vary within a race.
    """

    source_url: str
    event_name: str
    event_date: date | None
    event_type: str
    distance_km: float | None
    is_relay: bool
    city: str
    country: str


def _race_context(url: str, event: dict, race: dict) -> _RaceContext:
    """Qualify one race of `event` into the fields its participations share.

    `qualify_event_name` is what makes each race a distinct `Course` (FR-006):
    without it the six races of an event merge into one and their bibs collide
    (#21).

    `eventType` goes into the classifier's **context**, and this is the
    counter-intuitive part of the design (D9). The classifier only consults its
    context when the race name names no sport — which foreign names often do
    not: `Senior Men` alone falls back on `triathlon`, so the 2 852 rows of the
    UK cross would enter as triathlons, display as such and **survive**
    `federal_only=true`, the filter that exists to exclude them. Never
    concatenate the two titles instead: that classified the "Trail 12 km" of a
    "Triathlon de X" as a triathlon.
    """
    event_name = (event.get("eventName") or "").strip()
    race_name = (race.get("raceName") or "").strip()
    event_type = (event.get("eventType") or "").strip()
    distance = race.get("distanceInMeter") or 0
    return _RaceContext(
        # The **requested** URL, never rebuilt: it is the TTL cache key.
        source_url=url,
        event_name=qualify_event_name(event_name, race_name),
        event_date=_event_date(event.get("date")),
        event_type=classify_event_type(
            race_name, contexte=f"{event_name} {event_type}".strip()
        ),
        # `0` left as absent so `mapping.get_or_create_course` can still fall
        # back on extracting the distance from the name.
        distance_km=distance / 1000 if distance else None,
        is_relay=_is_relay(race_name),
        city=event.get("location") or "",
        country=event.get("countryCode") or "",
    )


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def _to_result(participant: dict, ctx: _RaceContext) -> ScrapedResult:
    """One row of the ranking → one `ScrapedResult`.

    On a relay the whole name goes to `athlete_name` and the first name stays
    empty (D11): the source publishes one row per **team**, with a free-form
    name (`LA COUSINADE`) and no teammate separator, so splitting it would
    fabricate an athlete "COUSINADE, LA". The `tags` array, which looks like a
    ready-made split, is a tokenised search index (trap n°4) and yields the same
    shape for a team as for a person.

    The club is `teamName` read as-is — `core/club.py` stays the only judge of
    TCN membership (#76). Unlike t2area, this scraper has no reason to know the
    club at all.
    """
    nom = (participant.get("name") or "").strip()
    athlete_name, athlete_firstname = (nom, "") if ctx.is_relay else split_athlete_name(nom)
    # Chip first, gun as fallback: the athlete's real time (D6). Reversing the
    # priority changes 7 435 rows of the panel, and neither column is usable
    # alone — 2 925 rows have no chip, 2 092 no gun.
    total_time = _time(participant.get("chipTimeOfParticipant")) or _time(
        participant.get("gunTimeOfParticipant")
    )
    rank_overall = _rank(participant.get("overallPosition"))
    genre = (participant.get("gender") or "").strip().upper()
    return ScrapedResult(
        source_url=ctx.source_url,
        provider=_PROVIDER,
        athlete_name=athlete_name,
        athlete_firstname=athlete_firstname,
        club=participant.get("teamName") or "",
        category=participant.get("raceCategory") or "",
        # `U` covers 4 243 rows (41 %) and the front doesn't render it: better
        # empty than a value it cannot display (D12).
        gender=genre if genre in ("M", "F") else "",
        bib_number=str(participant.get("bib") or "").strip(),
        event_name=ctx.event_name,
        event_date=ctx.event_date,
        event_type=ctx.event_type,
        rank_overall=rank_overall,
        rank_category=_rank(participant.get("categoryPosition")),
        rank_gender=_rank(participant.get("genderPosition")),
        total_time=total_time,
        segments=_segments(participant.get("legs")),
        distance_km=ctx.distance_km,
        is_relay=ctx.is_relay,
        status=_status(participant, total_time, rank_overall),
        raw_data=_raw_data(participant, ctx),
    )


def _raw_data(participant: dict, ctx: _RaceContext) -> dict:
    """The participant payload plus the race context, diagnosable without a
    re-scrape.

    `city` and `country` come from the **event** (D15, FR-022a): `location`
    beats what the map deduces from the event name (`geocode_service` renders
    "Sud Vendee Dimanche" where the source publishes "L'Aiguillon sur Mer
    (85)"), and the country code is the only datum that lets one **know** a
    British or Algerian event is not geocodable, rather than watch a silent
    failure. Neither is wired to the geocoder: `ScrapedResult` has no city
    field, and adding one would touch a contract shared by twelve providers.
    `city` is the key runnerbreizh already uses, for exactly this reason.

    The participant carries a `country` of its own — the athlete's, present on
    3 639 rows of the panel — which the event's would overwrite. It is moved to
    `athlete_country` rather than lost: two different facts, two keys.
    """
    brut = dict(participant)
    athlete_country = brut.pop("country", None)
    return {
        **brut,
        "athlete_country": athlete_country,
        "city": ctx.city,
        "country": ctx.country,
    }


def _scrape_race(
    client: httpx.Client, url: str, event: dict, race: dict
) -> list[ScrapedResult]:
    """One race's whole ranking, or `_IncompleteRanking`.

    The completeness check is a **floor** (`read < announced`), never an
    equality: a live race can gain ranked entrants between `/races` and the end
    of pagination, and the surplus is logged rather than refused (D4). On 32
    races out of 32 of the panel, the equality held.

    Without this check, an intermediate page served empty would stop the loop
    cleanly, the ranks read would stay contiguous, `quality.analyze` would see
    **no** anomaly, and the event would come out `is_reliable=true` missing half
    its ranking.
    """
    race_id = str(race.get("id") or "")
    annonces = race.get("classificationsCount") or 0
    participants = list(_iter_participants(client, race_id))
    if len(participants) < annonces:
        raise _IncompleteRanking(
            race.get("raceName") or "", race.get("activeRaceId"), len(participants), annonces
        )
    if len(participants) > annonces:
        logger.info(
            "Sporthive race %r (ordinal %s): read %d participants for %d announced — "
            "surplus accepted, the race is likely live.",
            race.get("raceName"), race.get("activeRaceId"), len(participants), annonces,
        )
    ctx = _race_context(url, event, race)
    return [_to_result(participant, ctx) for participant in participants]


def scrape_event_all(url: str) -> list[ScrapedResult]:
    """Every race of the event the URL points into (FR-005).

    A URL designates a race, the import goes up to the event: the Sheet carries
    one link per event, and a TCN member entered in another format would
    otherwise be invisible. Cost accepted at framing: ≈ 100 requests for the
    Sheet's event.

    Two failure scopes, and that is the structuring choice of this module. A
    truncated race is **dropped** (`_IncompleteRanking`, caught here) — refusing
    the whole event made it permanently unimportable, the five healthy races
    included. The event is **refused** (`ValueError`, propagated) when the URL
    is unreadable, when the event is unknown, when the stop invariant is false,
    or when **no** race could be read at all.

    That last guard is what closes the hole the per-race drop opens:
    `import_service._require_event_name` does not raise on an empty list, and
    `batch` counts "no result" as a legitimate short-circuit — so without it a
    wholly truncated event would be indistinguishable, in the report, from a
    successful import.
    """
    event_id = _parse_url(url)
    resultats: list[ScrapedResult] = []
    courses = 0
    with httpx.Client(follow_redirects=True, timeout=20, headers=_HEADERS) as client:
        event = _fetch_event(client, event_id)
        for race in _fetch_races(client, event_id):
            courses += 1
            # Skipped **before** any request (FR-008b, D14). Not cosmetic: an
            # empty `Course` has no participation without `total_time`, so
            # `cache.is_in_progress` calls it finished and — the six races of an
            # event sharing one `source_url` — it can become the course that
            # answers for the whole event, freezing its re-scrape for 30 days.
            if not (race.get("classificationsCount") or 0) > 0:
                logger.info(
                    "Sporthive race %r (ordinal %s): no ranked entrant announced, "
                    "skipped without a request.",
                    race.get("raceName"), race.get("activeRaceId"),
                )
                continue
            try:
                resultats.extend(_scrape_race(client, url, event, race))
            except _IncompleteRanking as ecart:
                # The only trace of this race: the CLI report counts events, so
                # the event comes back a success with 5 races out of 6. Hence
                # the line must be usable on its own (FR-008a).
                logger.warning(
                    "Sporthive race %r (ordinal %s) dropped: %d participants read for "
                    "%d announced, ranking truncated at the source.",
                    ecart.race_name, ecart.active_race_id, ecart.lus, ecart.annonces,
                )
    if not resultats:
        raise ValueError(
            f"Événement Sporthive {event_id} : aucune course importable. "
            f"{courses} course(s) publiée(s), aucune n'a rendu de classement "
            "exploitable — classement absent ou tronqué à la source. L'import "
            "est refusé plutôt que compté comme un succès à zéro participant ; "
            "il est rejouable dès que la source publie."
        )
    return resultats
