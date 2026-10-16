# Club best times Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve and show the club's best time per sized format, gender and season (#1588).

**Architecture:** One repository query returns candidate rows (columns only); `club_service` parses times and keeps the fastest per (event_type, gender); `GET /api/v1/club/best-times` exposes it; `/club` fetches the current season and all seasons and renders `ClubBestTimesCard`.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, pytest; Next.js 16, Vitest + RTL.

**Spec:** `docs/superpowers/specs/2026-10-16-club-best-times-design.md`

## Global Constraints

- `/api/v1` additive only (Principle IV).
- Queries only in repositories, constant query count.
- UI copy French, vouvoiement, never « record », no dash as sentence punctuation.
- Tests unit only (no network); identifiers and test names English.

---

### Task 1: Repository + service + endpoint

**Files:**
- Modify: `backend/app/repositories/participation_repository.py` (add `SIZES`, `SIZED_EVENT_TYPES`, `club_best_time_rows`)
- Modify: `backend/app/schemas/club.py` (add `ClubBestTime`)
- Modify: `backend/app/services/club_service.py` (add `get_club_best_times`)
- Modify: `backend/app/api/v1/club.py` (add route)
- Modify: `backend/app/api/AGENTS.md` (inventory row)
- Test: `backend/tests/test_services/test_club_best_times.py`, `backend/tests/test_api/test_club_api.py`

**Interfaces:**
- Produces: `GET /api/v1/club/best-times?season=<int>&federal_only=<bool>` → `list[ClubBestTime]` with fields `participation_id, course_id, athlete_id, athlete_name, event_name, event_type, event_date (str|None), gender ("F"|"M"), total_time (str)`, sorted discipline, size XS→XL, gender F then M.

- [ ] Step 1: failing tests (service level through the real DB session): fastest kept per (event_type, gender); relay result and relay course excluded; pending excluded; unreliable course excluded (`reliability_override=False`), unknown reliability kept; DNF excluded; `00:00:00` and empty time excluded; non TCN club excluded; `triathlon` (bare) and `course-a-pied-10k` excluded; empty gender excluded; tie → earlier event date wins; `season` filter and empty season; `federal_only`; ordering; constant query count (one query for any number of rows). API test: shape, `season` passthrough, 422 on `season=1`.
- [ ] Step 2: run, expect FAIL (import error).
- [ ] Step 3: implement.

```python
# participation_repository.py
SIZES = ("xs", "s", "m", "l", "xl")
SIZED_EVENT_TYPES = sorted(t for t in CANONICAL_TYPES if t.rsplit("-", 1)[-1] in SIZES)

def club_best_time_rows(db, *, season=None, federal_only=False):
    q = (
        db.query(
            Participation.id.label("participation_id"), Participation.total_time,
            Athlete.id.label("athlete_id"), Athlete.prenom, Athlete.nom, Athlete.gender,
            Course.id.label("course_id"), Course.name.label("event_name"),
            Course.event_type, Course.event_date,
        )
        .join(Athlete, Participation.athlete_id == Athlete.id)
        .join(Course, Participation.course_id == Course.id)
        .filter(validated_clause(Participation.is_pending_validation))
        .filter(Participation.counts_for_tcn.is_(True))
        .filter(Participation.is_relay.is_(False), func.coalesce(Course.is_relay, False).is_(False))
        .filter(func.coalesce(Course.is_reliable, True).is_(True))
        .filter(func.upper(func.coalesce(Participation.status, "")).notin_(NON_FINISHER_STATUSES))
        .filter(Course.event_type.in_(SIZED_EVENT_TYPES))
        .filter(Athlete.gender.in_(GENDERS))
    )
    if season is not None:
        q = q.filter(Course.event_date.between(*season_bounds(season)))
    if federal_only:
        q = q.filter(federal_clause(Course.event_type))
    return q.all()
```

Service: loop rows, `seconds = to_seconds(total_time, strict=True)`, skip falsy, key `(event_type, gender)`, keep min of `(seconds, event_date or date.max, participation_id)`, sort by `(discipline, SIZES.index(size), gender order F, M)`.

Route: `season: int | None = Query(None, ge=SEASON_MIN, le=SEASON_MAX)`, `federal_only` as siblings.

- [ ] Step 4: `rtk uv run pytest tests/test_services/test_club_best_times.py tests/test_api/test_club_api.py`, expect PASS; `uv run ruff check .`.
- [ ] Step 5: commit `feat(club): serve the club's best time per sized format, gender and season`.

### Task 2: Card on /club

**Files:**
- Modify: `frontend/lib/types.ts` (`ClubBestTime`)
- Modify: `frontend/lib/api/server.ts` (`getClubBestTimes`)
- Create: `frontend/components/club/ClubBestTimesCard.tsx` + `.test.tsx`
- Modify: `frontend/app/(public_restricted)/club/page.tsx` (+ its test mock)

**Interfaces:**
- Consumes: Task 1 endpoint.
- Produces: `apiServer.getClubBestTimes(opts: { season?: number; federal_only?: boolean }, fetchOpts)`, `<ClubBestTimesCard season={number} seasonLines={ClubBestTime[]} allLines={ClubBestTime[]} />`.

- [ ] Step 1: failing tests: renders nothing when both lists empty; one link per line to `/courses/{course_id}/participations/{participation_id}` with discipline, « Femmes »/« Hommes », athlete, time and sr-only « meilleur temps sur M »; never « record »; season tab empty state « Aucun temps comparable cette saison » when only all-time has lines (all-time tab selected by default then); page test asserts both fetches with `revalidateSeconds: 30`.
- [ ] Step 2: run `npm test -- ClubBestTimesCard page`, expect FAIL.
- [ ] Step 3: implement (tcn `Card`, `LigneCarte`, `FormatChip`, shadcn `Tabs`), page fetches `[currentSeason()]` and all seasons in the existing `Promise.all`, renders the card after `ClubDashboard`.
- [ ] Step 4: `npm test`, `npm run lint`, `npm run build`.
- [ ] Step 5: commit `feat(club): show the club's best times card on /club`.
