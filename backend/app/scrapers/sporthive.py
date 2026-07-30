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

from .base import ScrapedResult

logger = logging.getLogger(__name__)

_API_BASE = "https://eventresults-api.speedhive.com/sporthive"
# size=50 gets a 400 ("The size value cannot be greater than 10") server-side.
_PAGE_SIZE = 10
# Hard cap: the worst case measured on the panel needs 269 requests for one race.
_MAX_PAGES = 1000


def scrape_event_all(url: str) -> list[ScrapedResult]:
    raise NotImplementedError
