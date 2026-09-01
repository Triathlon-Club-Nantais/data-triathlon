# Tasks: Retrait de l'auto-déclaration de bénévolat

**Input**: Design documents from `specs/20260901-164525-retrait-auto-declaration/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/removed-endpoints.md, quickstart.md

**Tests**: feature de suppression pure — les tests du code retiré sont
retirés avec lui (research.md, aucun red-green sur ces suppressions) ; les
deux tests d'inventaire (catalogue de pouvoirs, routes publiques) sont
adaptés **avant** le retrait du code qu'ils couvrent et confirmés rouges
(genuine TDD, comme #780/#809).

**Organization**: deux user stories P1 étroitement couplées (même travail
de suppression) — une seule phase.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: User Story 1+2 - Une seule section sur /benevolat, aucune ressource orpheline (Priority: P1) 🎯 MVP

**Goal**: `/benevolat` ne porte plus que le crédit d'un athlète ; aucune
route, pouvoir, fonction ou composant de l'auto-déclaration ne subsiste.

**Independent Test**: cf. quickstart.md scénarios 1-3.

### Tests d'inventaire — adapter avant le retrait, confirmer rouge

- [ ] T001 [P] [US2] Retirer `"benevolat:read"`/`"benevolat:manage"` de `CODES_ATTENDUS` dans `backend/tests/test_core/test_permissions.py` ; lancer, confirmer rouge (les pouvoirs existent encore dans `ALL`).
- [ ] T002 [P] [US2] Retirer `ROUTES_VOLUNTEER_DECLARATIONS_FERMEES` (et sa référence dans `ROUTES_FERMEES`) de `backend/tests/test_auth/test_public_routes_still_open.py` ; lancer, confirmer rouge (les routes exigent encore une session).

### Tests du code retiré — supprimés avec lui, pas de red-green

- [ ] T003 [P] [US2] Supprimer `backend/tests/test_api/test_volunteer_declarations_api.py`.
- [ ] T004 [P] [US2] Supprimer `backend/tests/test_api/test_admin_volunteer_declarations_api.py`.
- [ ] T005 [P] [US2] Supprimer `backend/tests/test_repositories/test_volunteer_declaration_repository.py`.
- [ ] T006 [P] [US2] Corriger le commentaire de `backend/tests/test_api/test_admin_volunteer_actions_api.py:6` qui renvoie vers `test_admin_volunteer_declarations_api.py` (research.md D5).

**Checkpoint**: T001/T002 rouges, le reste de la suite backend vert (code
pas encore retiré).

### Implémentation backend — retrait, dans l'ordre des couches

- [ ] T007 [US2] Retirer `BENEVOLAT_READ`, `BENEVOLAT_MANAGE`, `FEATURE_VOLUNTEERING` de `backend/app/core/permissions.py` (classe `P` et tuple `ALL`).
- [ ] T008 [US2] Supprimer `backend/app/api/v1/volunteer_declarations.py` et `backend/app/api/v1/admin_volunteer_declarations.py` ; retirer leur enregistrement dans `backend/app/api/v1/router.py` (dépend de T007).
- [ ] T009 [US2] Corriger le commentaire de `backend/app/api/v1/volunteer_actions.py:5` qui renvoie vers `volunteer_declarations.py` (research.md D5, dépend de T008).
- [ ] T010 [US2] Supprimer `backend/app/services/volunteer_declaration_service.py` (dépend de T008).
- [ ] T011 [US2] Supprimer `backend/app/schemas/volunteer_declaration.py` (dépend de T008).
- [ ] T012 [US2] Supprimer `backend/app/repositories/volunteer_declaration_repository.py` (dépend de T010).
- [ ] T013 [US2] Supprimer `backend/app/models/volunteer_declaration.py`, retirer son import/export dans `backend/app/models/__init__.py`, générer et relire la migration Alembic (`op.drop_table`) (dépend de T012).
- [ ] T014 [US2] Vérifier : `cd backend && uv run pytest -m "not integration" && uv run ruff check .` — suite verte, T001/T002 désormais verts.

### Implémentation frontend — retrait

- [ ] T015 [US1] Retirer la section d'auto-déclaration de `frontend/app/(public_restricted)/benevolat/page.tsx` — ne garder que la section de crédit d'un athlète ; retirer `useSession`/`useRouter` si devenus inutiles.
- [ ] T016 [US2] Supprimer `frontend/components/benevolat/VolunteerDeclarationForm.tsx` (+`.test.tsx`) et `VolunteerDeclarationList.tsx` (+`.test.tsx`) (dépend de T015).
- [ ] T017 [US2] Supprimer `frontend/components/benevolat/AdminVolunteerDeclarationCreateForm.tsx` (+`.test.tsx`) et `AdminVolunteerDeclarationTable.tsx` (+`.test.tsx`) ; réduire `frontend/app/admin/benevolat/page.tsx` à un état minimal buildable (sans ces composants) — #817, enchaînée immédiatement dans cette même fenêtre de travail avant tout push, lui donne son contenu définitif (research.md D3).
- [ ] T018 [US2] Supprimer `frontend/lib/queries/volunteer-declarations.ts` (dépend de T016).
- [ ] T019 [US2] Retirer `useAllVolunteerDeclarations`, `useAdminCreateVolunteerDeclaration`, `useValidateVolunteerDeclaration`, `useAdminDeleteVolunteerDeclaration` de `frontend/lib/queries/admin.ts` (dépend de T017).
- [ ] T020 [US2] Retirer `myVolunteerDeclarations`, `adminVolunteerDeclarations` de `frontend/lib/queries/keys.ts` (dépend de T018, T019).
- [ ] T021 [US2] Retirer les 7 méthodes et imports de types associés dans `frontend/lib/api/client.ts` (dépend de T018, T019).
- [ ] T022 [US2] Grep `VolunteerDeclaration`/`AdminVolunteerDeclaration`/`VolunteerDeclarationCreate`/`AdminVolunteerDeclarationCreate` — retirer de `frontend/lib/types.ts` si orphelines (dépend de T021).
- [ ] T023 [US2] Retirer les deux entrées `id: "a-benevolat"` de `frontend/components/layout/nav.config.ts` (lignes 215-221 et 265).
- [ ] T024 [US2] Corriger le commentaire de `frontend/components/benevolat/VolunteerActionForm.tsx:14` qui référence `VolunteerDeclarationForm` (research.md D5, dépend de T016).
- [ ] T025 [US1] Vérifier : `cd frontend && npm test && npm run lint && npx tsc --noEmit && npm run build` — suite verte.

**Checkpoint**: User Stories 1 et 2 complètes et vérifiables — `/admin/
benevolat` reste buildable (T017), sa reconstruction par #817 suit
immédiatement, avant tout push.

---

## Dependencies & Execution Order

- T001/T002 (tests d'inventaire) avant T007+ (retrait backend) — rouge puis vert.
- T003-T006 : indépendants entre eux, aucune dépendance.
- T007 → T008 → T009/T010/T011 → T012 → T013 (ordre des couches : permission avant route, route avant service/schéma, service avant repository, repository avant modèle/migration).
- T014 clôture le backend.
- T015 → T016/T017 → T018 → T019 → T020/T021 → T022 → T023/T024 (frontend : page avant composants, composants avant hooks, hooks avant clés/client, client avant types, indépendant : nav et commentaire).
- T025 clôture le frontend.

## Parallel Opportunities

- T001, T002 : fichiers de test distincts, aucune dépendance entre eux.
- T003, T004, T005, T006 : fichiers distincts, aucune dépendance entre eux.
- T023, T024 : fichiers distincts, aucune dépendance avec le reste une fois T016/T017 faites.

## Implementation Strategy

Stories couplées (P1 = MVP unique). Tests d'inventaire d'abord (T001/T002,
rouge confirmé), tests du code retiré supprimés en parallèle (T003-T006),
puis retrait backend couche par couche (T007-T014), puis retrait frontend
(T015-T025). #817 (écran de validation `/admin/benevolat`) est implémentée
immédiatement après, dans la même fenêtre de travail, avant tout push
(research.md D3, décision produit explicite).
