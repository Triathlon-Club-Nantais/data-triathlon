# Team result search in Mon espace (#1773) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A claimed member finds a relay published under a team name by typing that name in a Mon espace card, and sends the #1757 relay claim in one click.

**Architecture:** Port only the search half of PR #1760 (branch `origin/worktree-1739-team-result-claim`) file by file onto main, where #1757 already ships relay claims (`result_claims.request_claim` / `approve` / `_join_relay`). New read route `GET /api/v1/auth/me/team-results?q=` (repository query, service-side opposition filter, dedicated rate-limit bucket) and a new card `ResultatEquipeManquant` that posts to the unchanged `POST /auth/me/result-claims`. Nothing in #1760's claim logic is ported.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, pytest; Next.js 16, React Query, vitest, `components/tcn`.

**Spec:** `docs/superpowers/specs/2026-10-20-team-result-claim-design.md` on `origin/worktree-1739-team-result-claim` (read with `git show`), narrowed by issue #1773. Where they differ, #1773 wins.

## Global Constraints

- No migration, no `kind` column, no `KIND_*` constant, no `ClaimKind` change, no change to `request_claim`. One Alembic head. `approve` and `ResultClaimsTable` change only as Task 4 says (decided with the user on 2026-10-21, beyond #1773's scope line).
- API is additive under `/api/v1` (Principe IV): `POST /auth/me/result-claims` body stays `{participation_id}`.
- Port from #1760 with `git show origin/worktree-1739-team-result-claim:<path>`, never by cherry-picking.
- Search: word by word, case and accent insensitive, on `Participation.team_name` or the carrier's `Athlete.nom` when the carrier is a team record (`prenom` blank, `nom` not blank); relay only (`Participation.is_relay` or `Course.is_relay`); `validated_clause` (#1615); carrier and teammates not the member; carrier is a team record or the relay is composed; 10 results, most recent first; `q` 3 to 80 chars; 120 calls per 3600 s per client, bucket `team_search`.
- Card copy (French, vouvoiement, « épreuve »): title « Un résultat d'équipe manque ? », button « Chercher », row button « C'était mon équipe », pending line « Demande envoyée, le club va vérifier. », rejected line « Demande refusée par le club. ».
- The card lives in `frontend/components/mon-espace/`; do not touch `frontend/app/(public_restricted)/mon-espace/`.
- Tests in English, user-visible text in French; TDD each task.

## Review Focus

1. Anonymised carriers (`prenom` empty, `nom` starting with `Anonyme `, see `result_claims._is_anonymous`) look like team records: searching « anonyme » must return none of them, since `request_claim` refuses them anyway. Test in Task 1.
2. An opposed identity (#1506/#1514) as carrier or as a composed teammate hides the whole hit. Test in Task 2.
3. LIKE wildcards typed by the member (`%`, `_`) match literally, they do not list every relay. Test in Task 1.
4. A query of only spaces or punctuation (`"   "`) passes `min_length=3` but must return `[]`, not every relay. Test in Task 2.
5. After « C'était mon équipe », the row flips to the pending line from `GET /auth/me/result-claims` (the mutation already invalidates it); a 409 from the server (five pending claims) shows in an alert. Test in Task 3.

---

### Task 1: Repository query `search_team_results`

**Files:**
- Modify: `backend/app/repositories/participation_repository.py` (add after `_relay_name_matches`)
- Create: `backend/tests/test_repositories/test_team_result_search.py` (port from #1760)

**Interfaces:**
- Produces: `participation_repository.search_team_results(db: Session, *, term: str, exclude_athlete_id: int, limit: int = 10) -> list[Participation]`, with `course` and `athlete` eagerly loaded.

- [ ] **Step 1: Port the test file from #1760 and add the Review Focus tests**

Copy `backend/tests/test_repositories/test_team_result_search.py` from #1760 as is, then append:

```python
def test_anonymised_carriers_are_not_team_records(db_session, member):
    _relay(db_session, _athlete(db_session, "Anonyme 12-34"))

    assert _search(db_session, member, "anonyme") == []


def test_like_wildcards_match_literally(db_session, member):
    _relay(db_session, _athlete(db_session, "LES MOLLETS"))
    row = _relay(db_session, _athlete(db_session, "100% FUN"))

    assert _search(db_session, member, "100%") == [row.id]
    assert _search(db_session, member, "_") == []
```

- [ ] **Step 2: Run, expect FAIL** (`AttributeError: ... search_team_results`)

Run: `cd backend && uv run pytest tests/test_repositories/test_team_result_search.py -n 0 -q`

- [ ] **Step 3: Implement** by porting #1760's `search_team_results` (and its `deaccent` / `escape_like` imports), with one change: the team-record clause also requires `~Athlete.nom.startswith("Anonyme ")`, with a one-line comment pointing at `result_claims._is_anonymous`.

- [ ] **Step 4: Run, expect PASS**, then `uv run ruff check app tests`.

- [ ] **Step 5: Commit** `feat(claims): search relay results by team name (#1773)`

### Task 2: Service, route and rate limit

**Files:**
- Modify: `backend/app/services/result_claims.py` (add `TeamResultHit`, `search_team_results`; module docstring gains one sentence on the search)
- Modify: `backend/app/schemas/athlete_claim.py` (add `TeamResultRead`, port as is)
- Modify: `backend/app/api/deps.py` (port `TEAM_SEARCH_RATE_LIMIT_*` and `team_search_rate_limit`)
- Modify: `backend/app/api/v1/auth.py` (port `search_team_results` route, placed after `request_result_claim`)
- Modify: `backend/app/api/AGENTS.md` (one line for the route next to the `teammate_rows` row and the rate-limit list, whichever already lists per-route buckets)
- Modify: `backend/tests/test_api/test_result_claims_api.py` (service and route are tested through HTTP, as #1760 did)

**Interfaces:**
- Consumes: Task 1's `participation_repository.search_team_results`.
- Produces: `GET /api/v1/auth/me/team-results?q=` → `list[TeamResultRead]` with fields `participation_id, team_name, course_id, course_name, event_date (ISO or null), rank_overall, total_time, teammates: list[str]`. `team_name` is `participation.team_name or participation.athlete.nom`; `teammates` are `"prenom nom".strip()` of composed teammates.
- `result_claims.search_team_results(db, user, term) -> list[TeamResultHit]`, `[]` when `user.athlete_id is None`; drops a hit when `identity_hash(nom, prenom)` of the carrier or any teammate is in `opposition_repository.all_hashes(db)`.

- [ ] **Step 1: Port the API tests from #1760** (`TEAM_SEARCH`, `_team_relay`, `_athlete`, `test_search_team_results_returns_hits`, `test_search_needs_three_characters`, `test_search_without_claimed_athlete_returns_empty`, `test_search_hides_opposed_identities`), dropping `test_post_team_claim` and `test_queue_shows_team_claims_with_their_composition` (they test `kind`). Add:

```python
def test_a_found_team_result_is_claimed_through_the_relay_claim(client, db_session, setup):
    _team_relay(db_session)
    (hit,) = client.get(TEAM_SEARCH, params={"q": "mollets"}).json()

    # #1757's POST, unchanged body: the hit's id is all it needs.
    created = client.post(MINE, json={"participation_id": hit["participation_id"]})
    assert created.status_code == 201
    assert created.json()["status"] == "pending"


def test_search_of_blanks_returns_nothing(client, setup):
    assert client.get(TEAM_SEARCH, params={"q": "   "}).json() == []


def test_search_is_rate_limited(client, setup, monkeypatch):
    monkeypatch.setattr(deps, "TEAM_SEARCH_RATE_LIMIT_MAX_PER_WINDOW", 1)
    assert client.get(TEAM_SEARCH, params={"q": "abc"}).status_code == 200
    assert client.get(TEAM_SEARCH, params={"q": "abc"}).status_code == 429
```

Same ceiling-lowering pattern as `backend/tests/test_api/test_rate_limit.py` (`from app.api import deps`).

- [ ] **Step 2: Run, expect FAIL** (404 on the route)

Run: `cd backend && uv run pytest tests/test_api/test_result_claims_api.py -n 0 -q`

- [ ] **Step 3: Implement** by porting from #1760 the schema, the deps bucket, the route and the service's `TeamResultHit` / `search_team_results` only. Do not port `_claimable`, `is_team_record`, `team_composition_with`, `_approve_team`, `CompositionToDecideError`, the review hints, `kind` anywhere.

- [ ] **Step 4: Run, expect PASS**, then the whole unit suite and lint:

Run: `cd backend && uv run pytest -m "not integration" -q && uv run ruff check .`
Also: `uv run alembic heads` prints exactly one head.

- [ ] **Step 5: Commit** `feat(api): find a team result by its name from Mon espace (#1773)`

### Task 3: Card `ResultatEquipeManquant`, wiring and member guide line

**Files:**
- Modify: `frontend/lib/types.ts` (port `TeamResult`; no `kind` on `ResultClaim`)
- Modify: `frontend/lib/api/client.ts` (port `searchMyTeamResults`; `requestResultClaim` unchanged)
- Modify: `frontend/lib/queries/keys.ts` (`myTeamResults(q)`), `frontend/lib/queries/auth.ts` (port `useMyTeamResults`; `useRequestResultClaim` unchanged)
- Create: `frontend/components/mon-espace/ResultatEquipeManquant.tsx`, `.test.tsx` (port from #1760)
- Modify: `frontend/components/mon-espace/ColonneDroite.tsx` (render `<ResultatEquipeManquant />` right after `<RappelObjectifMajeur />`), `ColonneDroite.test.tsx` (port the #1760 test and the `getMyResultClaims` mock)
- Modify: `frontend/components/guide/guide-content.membre.ts` (one step in `reclamer-resultat`), `guide-content.membre.test.ts`

**Interfaces:**
- Consumes: Task 2's route and `TeamResult` shape; existing `useMyResultClaims(enabled)`, `useRequestResultClaim()` whose `mutateAsync` takes a `participationId: number`.

- [ ] **Step 1: Port the tests.** `ResultatEquipeManquant.test.tsx` from #1760, adapted: the click test expects `requestResultClaim` called with `(participation_id)` only; claims in mocks carry no `kind`, and the pending/rejected lookup matches on `participation_id`. Keep all ten cases (search lines, inert under 3 chars, empty state quotes the input, truncated at 10, short list not flagged, one click sends, rejected can be resent, search error with and without message, server refusal shown). `ColonneDroite.test.tsx`: the #1760 case, plus assert the card comes after the major goal reminder in document order. Guide test: add to `reclamer-resultat` an expectation that its steps contain `« C'était mon équipe »` and `« Un résultat d'équipe manque ? »`.

- [ ] **Step 2: Run, expect FAIL**

Run: `cd frontend && npx vitest run components/mon-espace components/guide`

- [ ] **Step 3: Implement** by porting the #1760 files listed above, with these changes only: `envoyer` calls `demander.mutateAsync(equipe.participation_id)`; the claim lookup is `demandes.data?.find((d) => d.participation_id === equipe.participation_id)`. Guide, section `reclamer-resultat`: insert, before the refusal step, « Un relais, un swimrun ou un raid publié sous le seul nom d'équipe : dans « Mon espace », carte « Un résultat d'équipe manque ? », chercher le nom de l'équipe puis cliquer sur « C'était mon équipe ». »; and fix the stale relay wording: on a relay the button reads « Je faisais partie de cette équipe » (`ResultClaimAction`), and the club adds your fiche to the team. Drop « ni sur un relais » from the last step. The guide test also asserts the steps contain `« Je faisais partie de cette équipe »` and no longer contain `ni sur un relais`.

- [ ] **Step 4: Run, expect PASS**, then `npm test`, `npm run lint`, `npm run build` in `frontend/`.

- [ ] **Step 5: Commit** `feat(mon-espace): find a missing team result by its name (#1773)`

### Task 4: Validating a claim on a composed relay adds the member in one click

**Why:** after teammate A's claim replaces the team label, the relay's composition is `[A]`; partner B's claim then hits `TeamToCompleteError` and needs the « Attribuer aux équipiers » dialog and `participations:reassign`. Decided with the user: validation appends the member.

**Files:**
- Modify: `backend/app/services/result_claims.py` (`_join_relay`; delete `TeamToCompleteError`; module docstring: « Avec une composition, la fiche s'y ajoute en dernier. »)
- Modify: `backend/tests/test_services/test_result_claims.py`, `backend/tests/test_api/test_result_claims_api.py`
- Modify: `frontend/components/admin/ResultClaimsTable.tsx` (+ `.test.tsx`), `frontend/components/athletes/TeammatesDialog.tsx` (+ its test)

**Interfaces:**
- Backend: in `_join_relay`, when `team` is non-empty and `target not in team`, call `admin_actions.set_teammates(db, participation_id=participation.id, teammates=[*team, target], user_id=actor_id)` and return `{"mode": "joined_team"}`; `target in team` keeps `{"mode": "team_completed"}`. `set_teammates` already keeps `team[0]` as carrier, leaves `team_name` alone when a composition exists, raises `DuplicateError` (409) when the member has a result on the épreuve and `DomainError` beyond 8.
- Frontend: a relay claim whose member is not yet in the team shows the same « Ajouter à l'équipe » button (`aria-label` « Ajouter à l'équipe la fiche de {qui} ») whether or not the relay has teammates, calling `decide(r, "approve")`, without `participations:reassign`. Delete `aCompleter`, `completer`, `peutAttribuer`, the `TeammatesDialog` mount and the « Demandez à un administrateur… » line from `ResultClaimsTable`; then delete `TeammatesDialog`'s now unused `reclamation` prop and its branches.

- [ ] **Step 1: Rewrite the tests**
  - Service: replace `test_approve_a_relay_with_a_team_waits_for_the_admin_to_complete_it` with `test_approve_a_relay_with_a_team_appends_the_member` (composition `[homonym, partner]` → `[homonym, partner, lea.athlete_id]`, carrier still `homonym`, claim deleted, `_approve_log(...)["mode"] == "joined_team"`). Add `test_the_partner_joins_after_the_first_member_replaced_the_label`: team label carrier, approve lea's claim, then a second claimed member's claim; composition ends `[lea.athlete_id, second.athlete_id]`, `team_name` still the label's `nom`. Add `test_approve_refuses_a_member_already_on_the_course` on a composed relay (`DuplicateError`, claim still pending, composition unchanged).
  - API: the composed-relay test now expects `approve` → 204 and the member last in `teammates`.
  - `ResultClaimsTable.test.tsx`: replace the four dialog tests (« completes an existing team… », « cannot assign the team once… », « says the team is saved… », « says who can complete… ») by one: a composed relay shows « Ajouter à l'équipe la fiche de Léa M. » to a reviewer without `participations:reassign`, and a click calls `approveResultClaim(4)`.
  - `TeammatesDialog` test: drop the cases that pass `reclamation`.

- [ ] **Step 2: Run, expect FAIL**

Run: `cd backend && uv run pytest tests/test_services/test_result_claims.py tests/test_api/test_result_claims_api.py -n 0 -q` and `cd frontend && npx vitest run components/admin/ResultClaimsTable components/athletes/TeammatesDialog`

- [ ] **Step 3: Implement** as in Interfaces; the component docstring of `ResultClaimsTable` says the composed case is one click too.

- [ ] **Step 4: Run, expect PASS**, then the backend unit suite, `ruff`, and `npm test`, `npm run lint` in `frontend/`.

- [ ] **Step 5: Commit** `feat(claims): add the member to a composed relay when validating (#1773)`
