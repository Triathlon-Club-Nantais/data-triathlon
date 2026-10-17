# Tasks: Revendiquer sa fiche athlète

**Input**: `specs/20261017-133422-rattachement-fiche-athlete/` (spec, plan, research, data-model, contracts)

**Tests**: obligatoires (Principe III). Chaque test est écrit et vu échouer avant son implémentation.

## Phase 1: Fondations (bloquant)

- [ ] T001 [P] Test : `athlete_claims` existe après `alembic upgrade head`, disparaît au downgrade, colonnes et `UNIQUE(user_id)` conformes à data-model, dans `backend/tests/test_migrations.py`
- [ ] T002 Modèle `backend/app/models/athlete_claim.py` (+ import dans `app/models/__init__.py`), relation `User.athlete_claim` (`uselist=False`, `cascade="all, delete-orphan"`) dans `backend/app/models/user.py`, migration `backend/alembic/versions/<rev>_athlete_claims.py` chaînée sur `a7d3c91e4b20`
- [ ] T003 [P] Test : `athlete_claims` est une table possédée (suppression d'un compte avec demande réussie et emporte la demande) dans `backend/tests/test_auth/test_account_deletion.py`
- [ ] T004 Ajouter `athlete_claims` à `_OWNED_TABLES` de `backend/app/repositories/user_repository.py`
- [ ] T005 [P] Test : `P.ATHLETE_CLAIMS_REVIEW` (`athlete_claims:review`, administration) au catalogue, dans `backend/tests/test_auth/test_permissions_catalogue.py`
- [ ] T006 Pouvoir dans `backend/app/core/permissions.py`

## Phase 2: US1, demander (P1)

- [ ] T007 [P] [US1] Tests repository `backend/tests/test_repositories/test_athlete_claim_repository.py` : `get_for_user`, `upsert_pending` (remplace pending/rejected), `delete_for_user`, `list_pending` (ancienneté), `count_pending`, `delete_for_athlete`, `repoint`
- [ ] T008 [US1] `backend/app/repositories/athlete_claim_repository.py`
- [ ] T009 [P] [US1] Tests service `backend/tests/test_services/test_athlete_claims.py` : demande (201 logique, remplace), fiche absente → `NotFoundError`, compte rattaché → conflit, annulation idempotente
- [ ] T010 [US1] `backend/app/services/athlete_claims.py` : `request_claim`, `cancel_claim`
- [ ] T011 [P] [US1] Tests API `backend/tests/test_api/test_athlete_claims_api.py` : `POST`/`DELETE /auth/me/athlete-claim` (401, 201, 404, 409, 204), champs `athlete` et `athlete_claim` de `/auth/me` ; `test_me_groups.py` : clés additives
- [ ] T012 [US1] Schémas `backend/app/schemas/athlete_claim.py`, champs additifs de `SessionUserRead` dans `backend/app/schemas/auth.py`, routes dans `backend/app/api/v1/auth.py`

## Phase 3: US2, valider ou refuser (P1)

- [ ] T013 [P] [US2] Tests service : `approve` pose `users.athlete_id`, supprime la demande, journalise ; `reject` passe en `rejected`, journalise ; demande non en attente → `NotFoundError` ; `list_pending_with_hints` (licencié de la saison, adresse sur la liste, comptes rattachés) dans `backend/tests/test_services/test_athlete_claims.py`
- [ ] T014 [US2] `approve`, `reject`, `list_pending_with_hints` dans `backend/app/services/athlete_claims.py` (+ lectures groupées dans `club_member_repository`, `member_email_repository`, `user_repository`)
- [ ] T015 [P] [US2] Tests API back-office (401, 403, 200, 204, 404) dans `backend/tests/test_api/test_athlete_claims_api.py` ; pastille `claims` dans `backend/tests/test_services/test_admin_badge_counts.py` ; `test_public_routes_still_open.py` classe les routes sous `/admin/`
- [ ] T016 [US2] `backend/app/api/v1/admin_athlete_claims.py`, montage dans `router.py`, pastille dans `backend/app/services/admin_badge_counts.py` et `BadgeCounts`
- [ ] T017 [P] [US2] Tests : `is_member` vrai pour un compte rattaché hors liste dans `backend/tests/test_services/test_membership.py`
- [ ] T018 [US2] `backend/app/services/membership.py`
- [ ] T019 [P] [US2] Tests : fusion de fiches reporte la demande (`test_athlete_merge*.py`), opposition supprime la demande de la fiche (`test_opposition*.py`)
- [ ] T020 [US2] `athlete_merge.merge_athletes` et `opposition_service` appellent le repository

## Phase 4: US4, se détacher (P2)

- [ ] T021 [P] [US4] Tests service et API : `DELETE /auth/me/athlete` (401, 204, idempotent, `is_member` retombe)
- [ ] T022 [US4] `detach` dans le service, route dans `backend/app/api/v1/auth.py`

## Phase 5: Interface (US1, US2, US3, US4)

- [ ] T023 [P] Tests types et client : `SessionUser.athlete`/`athlete_claim`, méthodes `requestAthleteClaim`, `cancelAthleteClaim`, `detachAthlete`, `listAthleteClaims`, `approveAthleteClaim`, `rejectAthleteClaim` dans `frontend/lib/api/client.test.ts`
- [ ] T024 Types `frontend/lib/types.ts`, client `frontend/lib/api/client.ts`, hooks `frontend/lib/queries/auth.ts` et `frontend/lib/queries/admin.ts`, mise à jour des fixtures `SessionUser` des tests existants
- [ ] T025 [P] [US1] Tests `AthleteSelection` : « C'est moi » pour un connecté sans rattachement, état en attente sur la fiche visée, rien pour un anonyme ; rien à choisir pour un rattaché (sa propre fiche marquée « Votre fiche »)
- [ ] T026 [US1] `frontend/app/(public_restricted)/athletes/[id]/AthleteSelection.tsx`
- [ ] T027 [P] [US1][US4] Tests `UserMenu` : fiche rattachée et « Me détacher de ma fiche » (confirmation), demande en attente et « Annuler la demande », demande refusée
- [ ] T028 [US1][US4] `frontend/components/auth/UserMenu.tsx`, `UserMenuDropdown.tsx`
- [ ] T029 [P] [US3] Tests `SessionAthleteSync` (écrit la fiche de la session dans le stock, le vide au détachement) dans `frontend/app/providers.test.tsx` ; `AppNav` et `MaSaison` ne proposent ni de relâcher ni de changer d'athlète pour un rattaché
- [ ] T030 [US3] `frontend/app/providers.tsx`, `frontend/components/layout/AppNav.tsx`, `frontend/components/dashboard/MaSaison.tsx`
- [ ] T031 [P] [US2] Tests `AthleteClaimsTable` (liste, indices, valider, refuser, état vide, refus serveur) et entrée de nav avec pastille `claims`
- [ ] T032 [US2] `frontend/app/admin/rattachements/page.tsx`, `frontend/components/admin/AthleteClaimsTable.tsx`, `frontend/components/layout/nav.config.ts` (et libellés du journal d'administration pour `athlete_claim.*` dans `frontend/lib/admin-action-log.ts`)

## Phase 6: Finitions

- [ ] T033 [P] Test : la politique de confidentialité mentionne le lien compte → fiche, `updatedAt` du jour, dans `frontend/components/legal/content/confidentialite.test.tsx`
- [ ] T034 Politique `frontend/components/legal/content/confidentialite.tsx`
- [ ] T035 Docs : `backend/app/models/AGENTS.md` (table vers `athletes.id` en cascade, report à la fusion), `docs/auth/membres.md` (dérivation du statut), `backend/app/services/auth/AGENTS.md` (table possédée), `frontend` (relais du stock dans `docs/frontend/athlete-retenu.md`)
- [ ] T036 Suites complètes backend (`pytest -m "not integration"`, `ruff`) et frontend (`tsc`, `lint`, `vitest`)

## Dépendances

Phase 1 → Phases 2-4 (backend, dans l'ordre) → Phase 5 (après T012, T016, T022) → Phase 6. Les tâches [P] d'une phase sont des tests indépendants les uns des autres.
