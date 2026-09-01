# Tasks: Écran de validation admin des déclarations de crédit d'athlète

**Input**: Design documents from `specs/20260901-170045-admin-validation-screen/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/enriched-response.md, quickstart.md

**Tests**: TDD non-négociable (Principe III) — feature additive, chaque
test est écrit avant le code qu'il couvre et confirmé rouge.

**Organization**: une seule user story (P1) — pas de phase Setup ni
Foundational, le travail complète une chaîne verticale déjà en place
(#779).

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: User Story 1 - Instruire les déclarations en attente (Priority: P1) 🎯 MVP

**Goal**: `/admin/benevolat` affiche les déclarations en attente avec le
nom de l'athlète, et permet de les accepter ou refuser.

**Independent Test**: cf. quickstart.md scénarios 1-3.

### Tests backend — écrire avant l'implémentation, confirmer rouge

- [ ] T001 [P] [US1] Étendre le test de `backend/tests/test_api/test_admin_volunteer_actions_api.py` qui couvre `GET /admin/volunteer-actions/pending` : asserter que la réponse porte `athlete_nom`/`athlete_prenom` corrects ; lancer, confirmer rouge (champs absents).
- [ ] T002 [P] [US1] Ajouter un test dans `backend/tests/test_repositories/test_volunteer_action_repository.py` : `list_pending()` rend des objets dont `.athlete_nom`/`.athlete_prenom` correspondent à l'athlète de la déclaration ; lancer, confirmer rouge (propriétés inexistantes).

### Implémentation backend

- [ ] T003 [US1] Ajouter la relation `athlete` et les propriétés `athlete_nom`/`athlete_prenom` à `backend/app/models/volunteer_action.py`.
- [ ] T004 [US1] Ajouter `athlete_nom: str`/`athlete_prenom: str` à `AdminVolunteerActionOut` dans `backend/app/schemas/volunteer_action.py` (dépend de T003).
- [ ] T005 [US1] Ajouter `selectinload(VolunteerAction.athlete)` dans `list_pending()` de `backend/app/repositories/volunteer_action_repository.py` (dépend de T003).
- [ ] T006 [US1] Vérifier : `cd backend && uv run pytest -m "not integration" && uv run ruff check .` — suite verte, T001/T002 désormais verts.

### Tests frontend — écrire avant l'implémentation, confirmer rouge

- [ ] T007 [P] [US1] Écrire `frontend/components/benevolat/AdminVolunteerActionsTable.test.tsx` : chargement (skeleton), refus (message via `messageDeRefus`), liste vide (état vide explicite), données (nom d'athlète + titre + description + date, boutons Accepter/Refuser, disparition de la ligne après clic) ; lancer, confirmer rouge (composant inexistant).

### Implémentation frontend

- [ ] T008 [US1] Ajouter `listPendingVolunteerActions`, `acceptVolunteerAction`, `rejectVolunteerAction` à `frontend/lib/api/client.ts`.
- [ ] T009 [US1] Ajouter `pendingVolunteerActions` à `frontend/lib/queries/keys.ts`.
- [ ] T010 [US1] Ajouter `usePendingVolunteerActions`, `useAcceptVolunteerAction`, `useRejectVolunteerAction` à `frontend/lib/queries/admin.ts` (invalidation de `pendingVolunteerActions` après accept/reject) (dépend de T008, T009).
- [ ] T011 [US1] Ajouter `athlete_nom`/`athlete_prenom` à `AdminVolunteerActionOut` dans `frontend/lib/types.ts`.
- [ ] T012 [US1] Implémenter `frontend/components/benevolat/AdminVolunteerActionsTable.tsx` sur le patron de `AdminVolunteerDeclarationTable.tsx` (research.md D3) — fait passer T007 (dépend de T010, T011).
- [ ] T013 [US1] Donner son contenu définitif à `frontend/app/admin/benevolat/page.tsx` : `PageHeader` + `AdminVolunteerActionsTable` (dépend de T012).
- [ ] T014 [US1] Ajouter l'entrée `id: "a-benevolat-validation"` à `frontend/components/layout/nav.config.ts` (href `/admin/benevolat`, permission `athletes:volunteer_validate`, research.md D4).
- [ ] T015 [US1] Vérifier : `cd frontend && npm test && npm run lint && npx tsc --noEmit && npm run build` — suite verte, T007 désormais vert.

**Checkpoint**: User Story 1 complète et vérifiable — `/admin/benevolat`
porte son contenu définitif, jamais un état vide au-delà de cette même
fenêtre de travail (avec #816).

---

## Phase 2: Polish

- [ ] T016 Dérouler manuellement les 3 scénarios de `quickstart.md`
  (instruire une déclaration, état vide, refus d'accès).

---

## Dependencies & Execution Order

- T001/T002 (tests backend) avant T003-T006 (implémentation backend) — rouge puis vert.
- T003 → T004/T005 → T006 (modèle avant schéma/repository).
- T007 (test frontend) écrit avant T012 (implémentation qui le fait passer) — mais T008-T011 (dépendances techniques du composant) peuvent être posées avant.
- T008/T009 → T010 → T011 → T012 → T013 → T014 (client avant hooks, hooks + types avant composant, composant avant page, page avant nav — l'ordre de nav n'a en réalité aucune dépendance technique, listé en dernier par convention).
- T015 clôture le frontend.
- T016 après T006 et T015.

## Parallel Opportunities

- T001, T002 : fichiers de test distincts, aucune dépendance entre eux.
- T004, T005 : dépendent tous deux de T003 mais pas l'un de l'autre.

## Implementation Strategy

Story unique (P1 = MVP). Tests d'abord (T001/T002 backend, T007 frontend,
rouge confirmé), puis implémentation backend (T003-T006), puis
implémentation frontend (T008-T015), puis validation manuelle (T016).
Implémentée dans la continuité directe de #816 (même worktree, même
branche), avant tout push.
