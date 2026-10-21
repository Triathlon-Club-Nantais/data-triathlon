# Natation discipline (#1743) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a `natation` event type, produced by the classifier and excluded from the club counters by default.

**Architecture:** one more bare sport in `backend/app/scrapers/classify.py`, one more default in `backend/app/core/counter_scope.py` mirrored by a data migration, one more label in the frontend tables.

**Tech Stack:** Python 3.13, pytest, Alembic, SQLAlchemy 2; Next.js + vitest.

**Spec:** `docs/superpowers/specs/2026-10-21-classification-design.md` (section « #1743, discipline natation »).

## Global Constraints

- Branch `feat/1743-natation`, based on `origin/main` (Alembic head `a1745e7c0b2d`).
- Migration revision id `b1743c5d9e2f`, `down_revision = "a1745e7c0b2d"`.
- No sizes for natation (`natation-5k` is out of scope). No FFN scraper.
- New test identifiers in English; user-visible copy in French (« Natation »).
- Commits: Conventional Commits in English, **no `Co-Authored-By` trailer, no AI attribution**. Plain, separate git commands.
- Tests from `backend/`: `uv run pytest <target> -q -n 0`; frontend from `frontend/`: `npx vitest run <file>`.

## Review Focus

- `Swimrun eau libre de X` and `Aquathlon à la nage` must stay `swimrun` / `aquathlon` (multisports first). Test in Task 1.
- `Championnat natation eau libre 5 km` must not fall into `_running_slug` through « 5 km ». Test in Task 1.
- `nage` only as a whole word: `Nageurs du Cher triathlon` stays `triathlon` (triathlon is earlier anyway), `Course des nageurs` must not become `natation`. Test in Task 1.
- An apostrophe-elided name (`Traversée de l'Erdre à la nage`) must not pick up a size. Covered by « no sizes for natation » (`_SIZES_BY_SPORT` has no entry), test in Task 1.
- Migration downgrade removes only the `natation` row it added. Test in Task 2.

---

### Task 1: Classifier produces `natation`

**Files:**
- Modify: `backend/app/scrapers/classify.py` (`BARE_TYPES`, `CANONICAL_TYPES`, `_sport_base`)
- Test: `backend/tests/test_classify.py`

**Interfaces:**
- Produces: slug `"natation"` in `BARE_TYPES` and `CANONICAL_TYPES`; `classify_event_type` returns it.

- [ ] **Step 1: Write the failing tests**, as a new parametrized test next to `test_classify_mono_sport`:

```python
@pytest.mark.parametrize("text,expected", [
    ("Traversée de l'Erdre à la nage", "natation"),
    ("Championnat natation eau libre 5 km", "natation"),
    ("Coupe de natation", "natation"),
    ("Swimrun eau libre de Belle-Île", "swimrun"),
    ("Aquathlon à la nage", "aquathlon"),
    ("Course des nageurs", "course-a-pied"),
])
def test_classify_swimming(text, expected):
    assert classify_event_type(text) == expected
```

and `assert normalize_event_type("natation") == "natation"` in the same test module (idempotence through `CANONICAL_TYPES`).

Check `Course des nageurs` against the current code first: if it does not already give `course-a-pied`, replace it by a name that does and that contains `nageur` (the point is that `nageur` is not `nage`).

- [ ] **Step 2: Run** `uv run pytest tests/test_classify.py -q -n 0`. Expected: the natation cases FAIL (`triathlon`, `course-a-pied-5k`).

- [ ] **Step 3: Implement.** Add `"natation"` to `BARE_TYPES` and `CANONICAL_TYPES`. In `_sport_base`, right after the `if "triathlon" in t` block and before `if "trail" in t`:

```python
    if "natation" in t or "eau libre" in t or re.search(r"\bnage\b", t):
        return "natation"
```

No entry in `_SIZES_BY_SPORT`.

- [ ] **Step 4: Run** `uv run pytest tests/test_classify.py -q -n 0`. Expected: all PASS.

- [ ] **Step 5: Commit** `feat(classify): classify natation, nage and eau libre names as natation`.

### Task 2: `natation` excluded from counters by default

**Files:**
- Modify: `backend/app/core/counter_scope.py` (`DEFAULT_NON_FEDERAL_DISCIPLINES`)
- Create: `backend/alembic/versions/b1743c5d9e2f_natation_non_federal_discipline.py`
- Test: `backend/tests/test_migrations.py` (existing defaults/seed comparison ~line 700, plus one downgrade test), `backend/tests/test_core/test_discipline.py`

**Interfaces:**
- Consumes: slug `"natation"` (Task 1).

- [ ] **Step 1: Write the failing tests.**
  - In `tests/test_core/test_discipline.py`, a test that `"natation"` is in `NON_FEDERAL_TYPES` (the alias of `DEFAULT_NON_FEDERAL_DISCIPLINES` imported at the top of that file), following the file's existing style.
  - In `tests/test_migrations.py`, `test_natation_seed_downgrade_removes_only_its_row`: upgrade to head, downgrade to `a1745e7c0b2d`, assert no `counter_scope_entries` row with `value = 'natation'` remains and the other seeded discipline rows are still there; upgrade back to head. Reuse the file's helpers (`_alembic_config`, `_lignes`, the `sqlite_url` fixture), mirroring `test_downgrade_puis_upgrade_de_la_portee_des_compteurs`.

- [ ] **Step 2: Run** `uv run pytest tests/test_core/test_discipline.py tests/test_migrations.py -q -n 0 --migrations`. Expected: FAIL (natation not in defaults; revision missing).

- [ ] **Step 3: Implement.**
  - Add `"natation"` to `DEFAULT_NON_FEDERAL_DISCIPLINES`.
  - Migration `b1743c5d9e2f`, `down_revision = "a1745e7c0b2d"`. `upgrade`: one `op.bulk_insert` of `{"kind": "non_federal_discipline", "value": "natation", "created_by_user_id": None}` into a lightweight `sa.table("counter_scope_entries", ...)`, columns exactly as `35c74bb2c7b4_counter_scope_entries.py` declares them (copy its `created_at` handling if the column is NOT NULL without server default). `downgrade`: `DELETE FROM counter_scope_entries WHERE kind = 'non_federal_discipline' AND value = 'natation'`. Do not import app code in this migration: the literal kind string, as `35c74bb2c7b4` does.

- [ ] **Step 4: Run** the same command plus `uv run alembic heads` (expected: single head `b1743c5d9e2f`). Expected: PASS.

- [ ] **Step 5: Commit** `feat(counter-scope): exclude natation from the club counters by default`.

### Task 3: Frontend label

**Files:**
- Modify: `frontend/lib/constants.ts` (`EVENT_TYPE_LABELS`), `frontend/lib/utils/format.ts` (`formatToken`, `DISCIPLINES`)
- Test: `frontend/lib/utils/format.test.ts`

**Interfaces:**
- Consumes: slug `"natation"`.

Colour: none to add. `frontend/lib/sport-colors.ts` deliberately maps every mono-sport to « Autres » (#480); natation follows that rule.

- [ ] **Step 1: Write the failing tests** in `format.test.ts`, next to the existing `disciplineOf` / `formatToken` cases: `disciplineOf("natation") === "natation"`, `formatToken("natation") === "NAT"`, and `eventTypeLabel("natation") === "Natation"` (import from `@/lib/constants`).

- [ ] **Step 2: Run** `npx vitest run lib/utils/format.test.ts`. Expected: FAIL.

- [ ] **Step 3: Implement.** `natation: "Natation"` in `EVENT_TYPE_LABELS` after `cyclisme-clm` (this also adds it to `EVENT_TYPE_OPTIONS`, so the admin can pick it in `EditCourseDialog`); `"natation"` at the end of `DISCIPLINES`; `if (t.startsWith("natation")) return "NAT";` in `formatToken` next to the other fallbacks.

- [ ] **Step 4: Run** `npx vitest run lib/utils/format.test.ts` then `npm run lint`. Expected: PASS, no lint error.

- [ ] **Step 5: Commit** `feat(front): label the natation discipline`.

### Task 4: Branch verification

- [ ] From `backend/`: `uv run pytest -m "not integration"` and `uv run ruff check .`. From `frontend/`: `npm test` and `npm run build`. Expected: all green.
