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

This module only lays down its skeleton here (T001, Phase 1 of
specs/004-sporthive-scraper/tasks.md): `scrape_event_all` raises
`NotImplementedError`. The next batches implement it one brick at a time — URL
parsing, registry detection, paginated client, completeness guard, scalar
mapping, segments, metadata, then assembly.
"""
import logging
import re
from collections.abc import Iterator
from urllib.parse import urlparse

import httpx

from .base import ScrapedResult

logger = logging.getLogger(__name__)

_API_BASE = "https://eventresults-api.speedhive.com/sporthive"
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


def _fetch_json(client: httpx.Client, path: str, params: dict | None = None):
    """A `GET` on the API, HTTP errors left untranslated.

    A 5xx is not a link problem: turning it into `ValueError` would make it read
    as one in the CLI failure detail. Business refusals (a 404 on an unknown
    event) are translated by the caller that knows what the id meant.
    """
    response = client.get(f"{_API_BASE}{path}", params=params)
    response.raise_for_status()
    return response.json()


def _fetch_event(client: httpx.Client, event_id: str) -> dict:
    """Event metadata: name, ISO date, type, location, country code."""
    return _fetch_json(client, f"/events/{event_id}")


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


def scrape_event_all(url: str) -> list[ScrapedResult]:
    raise NotImplementedError
