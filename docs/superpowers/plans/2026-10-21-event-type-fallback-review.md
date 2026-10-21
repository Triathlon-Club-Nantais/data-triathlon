# Event type fallback review (#1744) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a course whose `event_type` comes from the classifier's triathlon fallback is flagged « Type à vérifier » and listable from `/admin/courses`, until an admin saves its type.

**Architecture:** a third value `'fallback'` of the existing `Course.event_type_origin` column. A pure predicate in `classify.py` decides; the import sets the origin in a batch step after persistence; a data migration backfills existing rows; `GET /courses` gains a filter and exposes the origin; the admin table gets a checkbox and a badge.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2, Alembic, pytest; Next.js, TanStack Query, vitest.

**Spec:** `docs/superpowers/specs/2026-10-21-classification-design.md` (section « #1744, repli à vérifier »).

## Global Constraints

- Branch `feat/1744-fallback-review`, stacked on `feat/1743-natation` (the PR targets that branch until #1743 merges).
- Migration revision id `c1744a8f3b6d`, `down_revision = "b1743c5d9e2f"`.
- Existing constants in `backend/app/models/course.py`: `EVENT_TYPE_ORIGIN_CLASSIFIED = "classified"`, `EVENT_TYPE_ORIGIN_MANUAL = "manual"`. Add `EVENT_TYPE_ORIGIN_FALLBACK = "fallback"` next to them.
- A `manual` origin is never rewritten by an import or the migration.
- Layering `api → services → repositories → DB`: only repositories touch the Session.
- Out of scope: changing the fallback value, excluding flagged courses from counters.
- New test identifiers in English; UI copy in French, exactly « Type à vérifier ».
- Commits: Conventional Commits in English, **no `Co-Authored-By`, no AI attribution**. Plain, separate git commands.

## Review Focus

- A re-import after a classifier fix (name now names a sport, type no longer `triathlon*`) must clear the flag back to `classified`. Test in Task 2.
- A relay twin (same name/date/type, `is_relay` differs) is flagged independently of its solo sibling. Test in Task 2.
- The migration must not touch `manual` rows nor non-triathlon rows, and its downgrade only resets `fallback` rows. Test in Task 4.
- `GET /courses` without the new parameter returns exactly what it returned before (Principe IV, additive only). Test in Task 5.
- Saving an unchanged type on a course that is not `fallback` must not mark it `manual`. Test in Task 3.

---

### Task 1: The predicate

**Files:**
- Modify: `backend/app/scrapers/classify.py`
- Test: `backend/tests/test_classify.py`

**Interfaces:**
- Produces:
  - `names_a_sport(text: str) -> bool`: `_sport_base(_norm(text)) is not None`, or the normalized text matches `\btri\b`, `ironman`, `embrunman`, `triman` or `70.3` (tokens that mean triathlon without saying it; they do **not** change `classify_event_type`).
  - `is_fallback_type(event_type: str, name: str, *, has_swim_and_bike: bool) -> bool`: `True` iff `event_type` is `"triathlon"` or starts with `"triathlon-"`, `not names_a_sport(name)`, and `not has_swim_and_bike`.

- [ ] **Step 1: Write the failing tests.**

```python
@pytest.mark.parametrize("event_type,name,has_swim_and_bike,expected", [
    ("triathlon-s", "La Chaussaire - Solo", False, True),
    ("triathlon-m", "Armorun 2026 - M - Solo", False, True),
    ("triathlon-m", "Triathlon M de Vertou", False, False),
    ("triathlon-s", "Triathlon L de Mimizan - Format S", False, False),
    ("triathlon-s", "La Chaussaire - Solo", True, False),
    ("triathlon-l", "2026 IRONMAN 70.3 Vichy", False, False),
    ("triathlon-m", "Embrunman - Quart", False, False),
    ("triathlon-l", "Chtriman 2025 - Gravelines - CHTRIMAN 113", False, False),
    ("triathlon-s", "TRI AT BAIN 2026 - TRI-AT-BAIN-S", False, False),
    ("duathlon-s", "La Chaussaire - Solo", False, False),
    ("cross-triathlon", "La Chaussaire - Solo", False, False),
])
def test_is_fallback_type(event_type, name, has_swim_and_bike, expected):
    assert is_fallback_type(event_type, name, has_swim_and_bike=has_swim_and_bike) is expected
```

- [ ] **Step 2: Run** `uv run pytest tests/test_classify.py -q -n 0`. Expected: FAIL (ImportError).
- [ ] **Step 3: Implement** both functions in `classify.py`, after `classify_event_type`. One docstring line each on why the tokens live here and not in `_sport_base` (they would change classification, out of scope).
- [ ] **Step 4: Run** the same command. Expected: PASS.
- [ ] **Step 5: Commit** `feat(classify): tell a triathlon fallback from a named sport`.

### Task 2: Import sets the origin

**Files:**
- Modify: `backend/app/models/course.py` (constant), `backend/app/repositories/course_repository.py`, `backend/app/services/import_persistence.py` (`persist_steps`)
- Test: `backend/tests/test_services/test_reclassification_on_import.py` (reuse its `patch_scraper` / `db_session` fixtures and result builders)

**Interfaces:**
- Consumes: `is_fallback_type` (Task 1).
- Produces:
  - `EVENT_TYPE_ORIGIN_FALLBACK = "fallback"` in `app/models/course.py`.
  - `course_repository.set_event_type_origin(db: Session, course: Course, origin: str) -> None` (assign + flush; no-op when equal).
  - private `import_persistence._flag_fallback_heats(db: Session, results: list[ScrapedResult]) -> None`.

- [ ] **Step 1: Write the failing tests** (English names):
  - `test_import_flags_a_course_typed_by_the_fallback`: import one result named `La Chaussaire - Solo`, `event_type="triathlon-s"`, no swim/bike times → the course has `event_type_origin == "fallback"`.
  - `test_import_does_not_flag_a_fallback_corroborated_by_splits`: same, with `swim_time` and `bike_time` set → `"classified"`.
  - `test_import_does_not_flag_a_named_triathlon`: `Triathlon M de Vertou`, `triathlon-m` → `"classified"`.
  - `test_reimport_clears_the_flag_once_the_type_is_recognised`: import as above (fallback), then re-import the same URL with `event_type="duathlon-s"` → the same course (one course in base) is `duathlon-s` and `"classified"`.
  - `test_import_never_flags_a_manual_course`: import the neutral `triathlon-s` course, correct it with `admin_actions.update_course(fields={"event_type": "duathlon-s"})`, re-import the same `triathlon-s` scrape → the course stays `duathlon-s` and `"manual"`.
  - `test_relay_twin_is_flagged_on_its_own`: solo and relay results under the same neutral name → both courses `"fallback"`.
- [ ] **Step 2: Run** `uv run pytest tests/test_services/test_reclassification_on_import.py -q -n 0`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement.** `_flag_fallback_heats` groups `results` by `(event_name, event_date, event_type, bool(is_relay))`; `has_swim_and_bike` is `any(r.swim_time and r.bike_time for r in group)` (check `mapping.build_splits` stores these as the `swim` / `bike` split keys, the shape Task 4 reads); finds the course with `course_repository.get_by_identity`; skips a missing course or a `manual` one; otherwise sets `fallback` or `classified`. Call it in `persist_steps` after `persisted.finalize()`, on `results` (and on `leftovers` after their own finalize). The results' `event_type` is already the final one there (`_reclassify_heats` relabels rows of manual courses before persistence).
- [ ] **Step 4: Run** the test file, then `uv run pytest tests/test_services -q`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(import): flag courses typed by the triathlon fallback`.

### Task 3: Saving the type confirms it

**Files:**
- Modify: `backend/app/services/admin_actions.py` (`update_course`, the `if requested.get("event_type", course.event_type) != course.event_type:` block)
- Test: `backend/tests/test_services/test_admin_actions.py`

**Interfaces:**
- Consumes: `EVENT_TYPE_ORIGIN_FALLBACK` (Task 2).

- [ ] **Step 1: Write the failing tests:** `test_saving_an_unchanged_type_confirms_a_fallback_course` (course with origin `fallback`, `update_course(fields={"event_type": course.event_type})` → origin `"manual"`); `test_saving_an_unchanged_type_leaves_a_classified_course_alone` (origin stays `"classified"`).
- [ ] **Step 2: Run** them. Expected: the first FAILS.
- [ ] **Step 3: Implement:** also set `requested["event_type_origin"] = EVENT_TYPE_ORIGIN_MANUAL` when `"event_type" in requested` and `course.event_type_origin == EVENT_TYPE_ORIGIN_FALLBACK`. No journal entry for a pure confirmation (`after == before` still returns early): add a `shortcut:` comment saying so (upgrade if confirmations must be audited). `EditCourseDialog` always sends `event_type`, so the front needs nothing.
- [ ] **Step 4: Run** `uv run pytest tests/test_services/test_admin_actions.py -q -n 0`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(admin): saving a fallback course's type confirms it`.

### Task 4: Backfill migration

**Files:**
- Create: `backend/alembic/versions/c1744a8f3b6d_flag_fallback_event_types.py`
- Test: `backend/tests/test_migrations.py`

**Interfaces:**
- Consumes: `is_fallback_type` (Task 1); split keys `swim` / `bike` in `participations.splits` (JSON).

- [ ] **Step 1: Write the failing test** `test_fallback_backfill_flags_only_uncorroborated_fallbacks`: on a base at `b1743c5d9e2f`, insert four courses: neutral name `triathlon-s` no participation (→ `fallback`); neutral name `triathlon-s` with one participation whose `splits` has `swim` and `bike` (→ `classified`); `Triathlon M de X` (→ `classified`); neutral name `triathlon-s` already `manual` (→ `manual`); plus one `duathlon-s` neutral (→ `classified`). Upgrade to `c1744a8f3b6d`, assert each origin. Downgrade to `b1743c5d9e2f`, assert no `fallback` row left and the `manual` one is still `manual`. Use the file's helpers and the raw-SQL insert style of its other data-migration tests; fill every NOT NULL column the tables require.
- [ ] **Step 2: Run** `uv run pytest tests/test_migrations.py -q -n 0 --migrations -k fallback`. Expected: FAIL.
- [ ] **Step 3: Implement.** `upgrade`: select `id, name, event_type` of courses with `event_type_origin = 'classified'` and `event_type = 'triathlon' OR event_type LIKE 'triathlon-%'`; keep those whose name fails `names_a_sport` (Python, from `app.scrapers.classify`; other migrations import app code); for those ids only, read `participations.splits` and compute `has_swim_and_bike` in Python (JSON parsed portably, SQLite and PostgreSQL); `UPDATE ... SET event_type_origin = 'fallback'` for the ids where `is_fallback_type` holds. `downgrade`: `UPDATE courses SET event_type_origin = 'classified' WHERE event_type_origin = 'fallback'`.
- [ ] **Step 4: Run** the same command, then `uv run pytest tests/test_migrations.py -q -n 0 --migrations` and `uv run alembic heads` (single head `c1744a8f3b6d`). Expected: PASS.
- [ ] **Step 5: Commit** `feat(migrations): flag existing courses typed by the triathlon fallback`.

### Task 5: API filter and field

**Files:**
- Modify: `backend/app/repositories/course_repository.py` (`_filtered`, `list_all`, `count_all`), `backend/app/api/v1/courses.py` (`list_courses`, `count_courses`), `backend/app/schemas/course.py` (`CourseBrief`)
- Test: the existing test module of `GET /courses` filters (find it with `grep -rln "awaiting_review" backend/tests`)

**Interfaces:**
- Produces: query param `event_type_to_review: bool = False` on `GET /courses` and `GET /courses/count` (description « Ne garde que les épreuves dont le type vient du repli triathlon, à vérifier (#1744). »); `CourseBrief.event_type_origin: str = "classified"`.

- [ ] **Step 1: Write the failing tests:** `?event_type_to_review=true` returns only the `fallback` course among a fallback, a classified and a manual one; `/courses/count` with the same param returns 1; without the param, all three are listed and each item carries `event_type_origin`.
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement** the filter in `_filtered` as `Course.event_type_origin == EVENT_TYPE_ORIGIN_FALLBACK`, threaded through `list_all` / `count_all` and both routes exactly like `awaiting_review`.
- [ ] **Step 4: Run** the module and `uv run pytest tests/test_api -q`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(api): filter courses whose type is to be reviewed`.

### Task 6: Admin screen

**Files:**
- Modify: `frontend/lib/types.ts` (course brief type), `frontend/lib/queries/admin.ts` (`FiltresCourses`), `frontend/lib/api/client.ts` (`listCourses`, count call: pass `event_type_to_review` only when `true`, like `awaiting_review`), `frontend/app/admin/courses/page.tsx` (read `sp.type_a_verifier === "1"`), `frontend/components/admin/CoursesAdminTable.tsx` (`CatalogueFilters` + row badge + URL writing)
- Test: `frontend/components/admin/CoursesAdminTable.test.tsx`

**Interfaces:**
- Consumes: `event_type_to_review` param, `event_type_origin` field (Task 5).
- Produces: URL param `type_a_verifier=1`; `FiltresCourses.event_type_to_review?: true`.

- [ ] **Step 1: Write the failing tests:** checking « Type à vérifier » then « Filtrer » pushes a URL with `type_a_verifier=1` and the query is called with `event_type_to_review: true`; « Réinitialiser » clears it; a row whose course has `event_type_origin: "fallback"` shows the text « Type à vérifier », a `classified` one does not.
- [ ] **Step 2: Run** `npx vitest run components/admin/CoursesAdminTable.test.tsx`. Expected: FAIL.
- [ ] **Step 3: Implement.** Native `<input type="checkbox">` with its `<label>` inside a `Champ` (no Checkbox component in `components/ui`); the badge with `components/ui/badge.tsx` next to the course name. Follow how the table maps filters to and from the URL today.
- [ ] **Step 4: Run** the test file, `npm run lint`, `npm run build`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(admin): list and badge courses whose type is to be reviewed`.

### Task 7: Branch verification

- [ ] From `backend/`: `uv run pytest -m "not integration"`, `uv run pytest tests/test_migrations.py --migrations -q`, `uv run ruff check .`. From `frontend/`: `npm test`, `npm run build`. Expected: all green.
