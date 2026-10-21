# Réglages de la fiche publique (#1692) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a claimed member hide three analysis blocks of their public athlete page and add up to 3 sports-profile links, one public goal and one pinned result, enforced server-side.

**Architecture:** One new table owned by the account (`public_page_settings`) plus a `public` flag on `season_goals`. A service `public_page` validates links and assembles what the public page shows; `GET /athletes/{id}` gains a neutral `public_page` field; the server-rendered athlete page omits hidden blocks. Mon espace gets a « Ma fiche publique » card, the goal form a « visible sur ma fiche » checkbox.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2, Alembic, pytest; Next.js 16 App Router, TypeScript, TanStack Query, vitest.

**Spec:** `docs/superpowers/specs/2026-10-21-fiche-publique-reglages-design.md` (read it first).

## Global Constraints

- Layers: `api → services → repositories → DB`; only repositories query the Session. A service never imports another service's `_private` symbol (`tests/test_service_boundaries.py`).
- Language: user-visible text and `DomainError` messages in French; identifiers, tests, technical docstrings in English. No dash used as sentence punctuation in French copy.
- `/api/v1` contract: only **add** fields, never change existing ones (`GET /athletes/{id}` keeps every current field).
- Links: `https` only, ≤ 200 characters, ≤ 3, no duplicates, host in `strava.com`, `garmin.com`, `polar.com`, `suunto.com` or one of their subdomains, compared on the parsed host; no userinfo, no port. Labels: `Strava`, `Garmin Connect`, `Polar Flow`, `Suunto`. Rendered `target="_blank" rel="noopener nofollow ugc"`.
- Hideable block keys (API and front): `best_times`, `progression`, `comparison`. Default: nothing hidden.
- Several accounts linked to one fiche: a block is hidden if **any** linked account hides it; links, goal and pin are shown only when **exactly one** account is linked.
- Migration `down_revision = "a1745e7c0b2d"` (rebase on `origin/main` before writing it; repoint if the orchestrator reports a newer head).
- Commits: Conventional Commits, scope `athletes`, suffix `(#1692)`, **no** `Co-Authored-By` trailer. Tests: `uv run pytest <file> -n 0` while iterating (from `backend/`), `npx vitest run <file>` (from `frontend/`).

## Review Focus

1. A link like `https://strava.com.evil.example/x`, `https://evil.example/?u=strava.com`, `https://user@strava.com/`, `http://strava.com/` or `javascript:` must be refused with 422; the API never stores it. (Task 2 tests.)
2. A pinned result that later leaves the fiche (reassigned, anonymised by an opposition, deleted, still pending) must silently disappear from the public page, never show another person's result. (Task 4 tests.)
3. A detached account, or a fiche with two linked accounts, must never leak one account's links on the fiche. (Task 4 tests.)
4. Account deletion (#1326) must still succeed with settings present, and the data export (#1674) must contain them. (Tasks 1 and 2 tests.)
5. A visitor's HTML must not contain a hidden block (server render), and an unconfigured fiche must render exactly as today. (Task 5 tests.)

---

### Task 1: Data model and migration

**Files:**
- Create: `backend/app/models/public_page_settings.py`
- Modify: `backend/app/models/__init__.py` (export), `backend/app/models/user.py` (relationship), `backend/app/models/season_goal.py` (`public` column), `backend/app/repositories/user_repository.py:143` (`_OWNED_TABLES`), `backend/app/models/AGENTS.md` (new section after « Objectifs de saison »)
- Create: `backend/alembic/versions/<rev>_public_page_settings.py`
- Test: `backend/tests/test_repositories/test_public_page_settings_model.py`

**Interfaces:**
- Produces: model `PublicPageSettings` (table `public_page_settings`): `user_id: int` (PK, FK `users.id`, no `ondelete`, ORM cascade like `season_goals`), `hide_best_times`, `hide_progression`, `hide_comparison: bool` (`server_default=false()`, not the string), `links: list[str]` (JSON, default `[]`), `pinned_participation_id: int | None` (FK `participations.id`, `ondelete="SET NULL"`), `updated_at: datetime` (`default=utcnow, onupdate=utcnow`). `User.public_page_settings` (`uselist=False`, `cascade="all, delete-orphan"`). `SeasonGoal.public: bool` (`server_default=false()`).

- [ ] **Step 1: Write the failing tests**: `test_settings_leave_with_the_account` (create user + settings, `user_repository` deletion path used by #1326 succeeds and the row is gone); `test_season_goal_public_defaults_to_false`.
- [ ] **Step 2: Run** `uv run pytest tests/test_repositories/test_public_page_settings_model.py -n 0`; expected FAIL (import error).
- [ ] **Step 3: Implement** the model, relationship, column, `_OWNED_TABLES` entry `"public_page_settings"`. Write the migration by `uv run alembic revision --autogenerate -m "public page settings"`, then check `down_revision = 'a1745e7c0b2d'` and that it creates the table and adds `season_goals.public` with `server_default=sa.false()`; downgrade drops both (batch mode for `season_goals`, like `a1745e7c0b2d`).
- [ ] **Step 4: Run** the new tests, then `uv run pytest tests/test_migrations.py tests/test_migrations_smoke.py --migrations -n 0` and `uv run alembic heads` (single head); expected PASS.
- [ ] **Step 5: Document** the table in `backend/app/models/AGENTS.md` (owned by the account, pin re-checked at read because `SET NULL` is inert in SQLite).
- [ ] **Step 6: Commit** `feat(athletes): store public page settings owned by the account (#1692)`.

### Task 2: Settings service, link validation and `/auth/me/public-page`

**Files:**
- Create: `backend/app/repositories/public_page_settings_repository.py`, `backend/app/services/public_page.py`, `backend/app/schemas/public_page.py`
- Modify: `backend/app/repositories/__init__.py` if it lists modules, `backend/app/api/v1/auth.py` (two routes next to `/auth/me/goals`), `backend/app/services/account_export.py` + `backend/app/schemas/account_export.py` (export)
- Test: `backend/tests/test_services/test_public_page_links.py`, `backend/tests/test_api/test_public_page_api.py`, `backend/tests/test_api/test_my_export_api.py`

**Interfaces:**
- Consumes: Task 1 model.
- Produces:
  - repository: `get(db, user_id) -> PublicPageSettings | None`, `list_for_users(db, user_ids: Iterable[int]) -> list[PublicPageSettings]`, `upsert(db, user_id: int, **fields) -> PublicPageSettings`.
  - service `public_page`: `normalize_link(url: str) -> str` (strips, validates, returns the URL unchanged otherwise; raises `InvalidLinkError`, 422, message « Lien refusé : seuls les profils Strava, Garmin Connect, Polar Flow et Suunto en https sont acceptés. »); `link_label(url: str) -> str`; `settings_of(db, user) -> MySettings`; `save(db, user, data: PublicPageSettingsWrite) -> MySettings` (409 `NoClaimedAthleteError`-style « Rattachez d'abord votre fiche athlète pour régler votre fiche publique. » without `athlete_id`; 422 `TooManyLinksError` above 3 or duplicates; 422 `InvalidPinError` « Ce résultat n'est pas sur votre fiche. » when the pin is not a validated result of `user.athlete_id`, checked with `participation_repository.list_for_athlete(db, athlete_id)`).
  - schemas: `PublicPageSettingsWrite {hide_best_times: bool = False, hide_progression: bool = False, hide_comparison: bool = False, links: list[str] = Field([], max_length=3), pinned_participation_id: DbId | None = None}`; `MySettings` / `PublicPageSettingsRead` = the same fields + `shared: bool` (more than one account linked to my fiche, `user_repository.ids_linked_to_athlete`).
  - routes: `GET /auth/me/public-page` → `PublicPageSettingsRead` (defaults when no row); `PUT /auth/me/public-page` → `PublicPageSettingsRead`, commits.
  - export: `AccountExport.public_page: ExportedPublicPage | None` (the five stored fields).

- [ ] **Step 1: Write failing link tests** (parametrized): accepted `https://www.strava.com/athletes/123`, `https://connect.garmin.com/modern/profile/x`, `https://flow.polar.com/training/profiles/1`, `https://www.suunto.com/x`, `https://strava.com/a` with labels `Strava`, `Garmin Connect`, `Polar Flow`, `Suunto`, `Strava`; refused `http://strava.com/a`, `https://strava.com.evil.example/a`, `https://evil.example/?u=strava.com`, `https://user@strava.com/a`, `https://strava.com:8443/a`, `javascript:alert(1)`, `https://evilstrava.com/a`, a 201-character https Strava URL, `""`, `"https://www.strava.com/a b"`.
- [ ] **Step 2: Run**, expect FAIL; **implement** with `urllib.parse.urlsplit` (`hostname` lowercased, `username`/`password`/`port` must be `None`, host equals a domain or ends with `"." + domain`, no whitespace in the URL).
- [ ] **Step 3: Write failing API tests** on the `lea` fixture pattern of `tests/test_api/test_season_goals_api.py`: GET defaults (all false, `[]`, `None`, `shared: False`); PUT round-trip; 4 links → 422; duplicate → 422; refused link → 422 and nothing stored; pin on another athlete's result → 422; pin on a pending result → 422; unlinked account → 409; anonymous → 401; `shared: True` when a second user has the same `athlete_id`.
- [ ] **Step 4: Implement** repository, schemas, service, routes; run; expect PASS.
- [ ] **Step 5: Export test** in `test_my_export_api.py`: saved settings appear under `public_page`; `None` without a row. Implement; run.
- [ ] **Step 6: Commit** `feat(athletes): let a claimed member save their public page settings (#1692)`.

### Task 3: Public goal

**Files:**
- Modify: `backend/app/schemas/season_goal.py`, `backend/app/services/season_goals.py`, `backend/app/repositories/season_goal_repository.py`, `backend/app/api/v1/auth.py` (`_goal_read`), `backend/app/schemas/account_export.py` (`ExportedSeasonGoal.public`)
- Test: `backend/tests/test_api/test_season_goals_api.py`

**Interfaces:**
- Produces: `SeasonGoalWrite.public: bool = False`, `SeasonGoalRead.public: bool`; `SeasonGoalRead.of(progress) -> SeasonGoalRead` classmethod replacing `auth._goal_read` (so `athletes.py` can reuse it); repository `clear_public(db, user_id, *, except_id: int) -> None` (all seasons); service `public_goal(db, user) -> GoalProgress | None` (the user's public goal of `current_season()`, else `None`).

- [ ] **Step 1: Write failing tests**: setting `public: true` on a second goal clears it on the first (any season); `public_goal` returns the current-season public goal with its progress; a public goal of last season returns `None`; update the exact dict of `test_create_list_update_delete` with `"public": False`.
- [ ] **Step 2: Run**, expect FAIL; **implement** (same pattern as `major` / `clear_major` in `create` and `update`).
- [ ] **Step 3: Run** `uv run pytest tests/test_api/test_season_goals_api.py tests/test_api/test_my_export_api.py -n 0`; expect PASS.
- [ ] **Step 4: Commit** `feat(athletes): let a member make one season goal public (#1692)`.

### Task 4: What the public athlete page shows

**Files:**
- Modify: `backend/app/services/public_page.py` (read side), `backend/app/schemas/public_page.py`, `backend/app/schemas/participation.py` (`AthleteDetail`), `backend/app/api/v1/athletes.py:126-169`, `backend/app/api/AGENTS.md` (one paragraph on `public_page`)
- Test: `backend/tests/test_api/test_athletes_api.py` (new block of tests)

**Interfaces:**
- Consumes: Task 2 repository and `link_label`; Task 3 `public_goal` and `SeasonGoalRead.of`.
- Produces: schema `PublicLink {url: str, label: str}`; `PublicPageRead {hidden: list[Literal["best_times", "progression", "comparison"]] = [], links: list[PublicLink] = [], goal: SeasonGoalRead | None = None, pinned_participation_id: int | None = None}`; `AthleteDetail.public_page: PublicPageRead = PublicPageRead()`; service `for_athlete(db, athlete_id: int, *, validated_ids: set[int]) -> PublicPageRead`.

- [ ] **Step 1: Write failing tests** on `GET /api/v1/athletes/{id}`: unclaimed fiche → `public_page == {"hidden": [], "links": [], "goal": None, "pinned_participation_id": None}`; claimed with settings → hidden keys in the order `best_times, progression, comparison`, links with labels, public goal, pin id; pin reassigned to another fiche (`participation.athlete_id` changed) → `None`; pin on a result now pending → `None`; detached account (`athlete_id = None`) → neutral; two accounts linked, one hiding `progression` and one with links → `hidden == ["progression"]`, `links == []`, `goal is None`, pin `None`; a volunteer call (pending included in `participations`) still checks the pin against validated results only.
- [ ] **Step 2: Run**, expect FAIL; **implement** `for_athlete` (linked ids by `user_repository.ids_linked_to_athlete`, settings by `list_for_users`, user for the goal by `user_repository.get`) and call it from `get_athlete` with `validated_ids={p.id for p in participations if not p.is_pending_validation}`.
- [ ] **Step 3: Run** `uv run pytest tests/test_api/test_athletes_api.py -n 0`; expect PASS.
- [ ] **Step 4: Commit** `feat(athletes): serve the member's public page settings on the athlete page (#1692)`.

### Task 5: Athlete page rendering (front)

**Files:**
- Modify: `frontend/lib/types.ts` (`AthleteDetail.public_page`, `PublicPage`, `PublicLink`, `SeasonGoal.public`, `SeasonGoalWrite.public`), `frontend/app/(public_restricted)/athletes/[id]/page.tsx`, `docs/frontend/athlete-retenu.md` (section « Réglages de la fiche publique (#1692) »)
- Create: `frontend/components/athletes/PublicPageExtras.tsx` (server components `PublicLinks`, `PublicGoal`, `PinnedResult`)
- Test: `frontend/app/(public_restricted)/athletes/[id]/page.test.tsx`, `frontend/components/athletes/PublicPageExtras.test.tsx`

**Interfaces:**
- Consumes: Task 4 response shape. Existing `libelle`, `progression`, `hms` from `components/dashboard/SeasonGoals.tsx` for the goal; the participation detail route `/courses/{course_id}/participations/{id}` for the pin.
- Produces: `PublicLinks({ links }: { links: PublicLink[] })`, `PublicGoal({ goal }: { goal: SeasonGoal })`, `PinnedResult({ participation }: { participation: Participation })`.

- [ ] **Step 1: Write failing tests**: neutral `public_page` renders exactly the current blocks; each hidden key removes its block (`BestTimesCard`, the « Progression » card, `AthleteComparisonChart`) and nothing else; links render as `<a>` with `target="_blank"` and `rel="noopener nofollow ugc"` and the label as text; public goal renders its label; pinned id found in `participations` renders a « Résultat épinglé » card linking to its detail page; pinned id missing from `participations` renders nothing. Existing page fixtures gain the neutral `public_page`.
- [ ] **Step 2: Run** `npx vitest run "app/(public_restricted)/athletes/[id]/page.test.tsx" components/athletes/PublicPageExtras.test.tsx`; expect FAIL.
- [ ] **Step 3: Implement**: links and goal under the header pills, pinned card first in the `space-y-6` stack; hidden blocks not rendered at all (no CSS hiding).
- [ ] **Step 4: Run** the tests, then `npm run lint` and `npx tsc --noEmit`; expect PASS.
- [ ] **Step 5: Document** in `docs/frontend/athlete-retenu.md` (rules, multi-account rule, the stated confidentiality limit).
- [ ] **Step 6: Commit** `feat(athletes): honour the member's public page settings on the athlete page (#1692)`.

### Task 6: Mon espace card and goal checkbox (front)

**Files:**
- Create: `frontend/components/mon-espace/MaFichePublique.tsx`, `frontend/components/mon-espace/MaFichePublique.test.tsx`
- Modify: `frontend/lib/api/client.ts` (`getPublicPageSettings`, `savePublicPageSettings`), `frontend/lib/types.ts` (`PublicPageSettings`, `PublicPageSettingsWrite`), `frontend/components/mon-espace/ColonneDroite.tsx` (mount the card), `frontend/components/dashboard/SeasonGoals.tsx` (checkbox « Afficher sur ma fiche publique » next to « majeur », pill « Public »), `frontend/components/dashboard/SeasonGoals.test.tsx`
- Consumes: Task 2 routes; Task 3 `public` field; Task 5 types.

**Interfaces:**
- Produces: `MaFichePublique({ athleteId }: { athleteId: number })`; `apiClient.getPublicPageSettings(): Promise<PublicPageSettings>`, `apiClient.savePublicPageSettings(body: PublicPageSettingsWrite): Promise<PublicPageSettings>`.

- [ ] **Step 1: Write failing tests**: card loads settings and shows three labelled checkboxes « Masquer mes records », « Masquer ma progression », « Masquer la comparaison »; up to 3 link inputs (`type="url"`); a select « Résultat épinglé » listing the member's validated results (from `apiClient.getAthlete(athleteId)` without filters) with « Aucun »; « Enregistrer » sends the PUT body and announces « Réglages enregistrés. » in an `AnnonceStatut` region mounted from the start; a 422 shows the server message (`messageDeRefus`); `shared: true` shows « Plusieurs comptes sont rattachés à votre fiche : vos liens, votre objectif et votre résultat épinglé n'y sont pas affichés. »; the card links to `/athletes/{athleteId}` (« Voir ma fiche ») and states « Masquer un bloc n'efface rien : vos résultats restent publics et permettent de le recalculer. ». Goal form: checking the box sends `public: true`.
- [ ] **Step 2: Run** `npx vitest run components/mon-espace/MaFichePublique.test.tsx components/dashboard/SeasonGoals.test.tsx`; expect FAIL.
- [ ] **Step 3: Implement**; invalidate the settings query after save.
- [ ] **Step 4: Run** the tests, `npm run lint`, `npx tsc --noEmit`; expect PASS.
- [ ] **Step 5: Commit** `feat(mon-espace): let the member set what their public page shows (#1692)`.

## Order and parallelism

Task 1 first. Tasks 2 and 3 are independent (different files except `auth.py`, which they touch in distinct places: dispatch them sequentially if one subagent per worktree). Task 4 needs 2 and 3. Tasks 5 and 6 need 4's shape and can run in parallel. Full suites (`uv run pytest -m "not integration"`, `npm test`, `npm run build`) once at the end.
