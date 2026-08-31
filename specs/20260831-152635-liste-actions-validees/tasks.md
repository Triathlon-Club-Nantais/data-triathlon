---

description: "Task list for #781 — liste des actions de bénévolat validées sur la fiche athlète"

---

# Tasks: Liste des actions de bénévolat validées sur la fiche athlète

**Input**: Design documents from `specs/20260831-152635-liste-actions-validees/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/athlete-volunteer-actions-api.md, quickstart.md

**Tests**: Principe III de la constitution v1.2.0 — TDD sans réseau, non-négociable.

**Organization**: Une seule user story (P1) — pas de découpage en phases multiples.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

Aucune tâche : projet existant.

## Phase 2: Foundational

Aucune tâche distincte — une seule user story, tout tombe dans sa phase.

---

## Phase 3: User Story 1 - Un admin habilité consulte les actions validées d'un athlète (Priority: P1) 🎯 MVP

**Goal**: Afficher, sur la fiche athlète, la liste des `VolunteerAction`
« validée » de cet athlète — visible seulement avec `athletes:volunteer_validate`.

**Independent Test**: cf. spec.md US1 Acceptance Scenarios 1-4 / quickstart.md Scénarios 1-3.

### Tests for User Story 1

> **Écrire ces tests d'abord, vérifier qu'ils échouent avant implémentation.**

- [X] T001 [P] [US1] Test repository : `list_validated_for_athlete()` ne rend que les lignes `"validee"` de l'athlète donné, triées `created_at desc`, aucune autre saison/athlète mélangée dans `backend/tests/test_repositories/test_volunteer_action_repository.py`
- [X] T002 [P] [US1] Test service : `list_validated_for_athlete()` délègue au repository dans `backend/tests/test_services/test_volunteer_action_service.py`
- [X] T003 [P] [US1] Test API : `GET /admin/athletes/{id}/volunteer-actions/validated` — `200` liste filtrée (title/description `null` toléré), `403` sans `athletes:volunteer_validate`, liste vide sur athlète sans action validée dans `backend/tests/test_api/test_admin_volunteer_actions_api.py`
- [ ] T004 [P] [US1] Test composant : `VolunteerActionsList` — rendu nul sans le pouvoir, liste avec titre/description si habilité, état vide explicite si aucune validée, repli d'affichage sur title/description `null` dans `frontend/components/athletes/VolunteerActionsList.test.tsx` (NEW)

### Implementation for User Story 1

- [X] T005 [US1] Implémenter `list_validated_for_athlete()` dans `backend/app/repositories/volunteer_action_repository.py` — fait passer T001
- [X] T006 [US1] Implémenter `volunteer_action_service.list_validated_for_athlete()` dans `backend/app/services/volunteer_action_service.py` — fait passer T002 (depends on T005)
- [X] T007 [US1] Ajouter `GET /admin/athletes/{athlete_id}/volunteer-actions/validated` au router `backend/app/api/v1/admin_volunteer_actions.py`, gardé par `require_permission(P.ATHLETES_VOLUNTEER_VALIDATE)` — fait passer T003 (depends on T006)
- [ ] T008 [P] [US1] Ajouter le type `AdminVolunteerActionOut` (title/description `string | null`) dans `frontend/lib/types.ts`
- [ ] T009 [US1] Ajouter `listValidatedVolunteerActions(athleteId)` dans `frontend/lib/api/client.ts` (depends on T008 pour le type de retour ; `/speckit-analyze` finding I1 — retrait du `[P]` contradictoire)
- [ ] T010 [US1] Ajouter `useValidatedVolunteerActions(athleteId, enabled)` dans `frontend/lib/queries/admin.ts` (depends on T009)
- [ ] T011 [US1] Implémenter `VolunteerActionsList.tsx` (garde `session.data?.permissions.includes("athletes:volunteer_validate")`, rendu nul sinon, patron `.tcn-table` simplifié, état vide, repli « — » sur title/description `null`) dans `frontend/components/athletes/VolunteerActionsList.tsx` (NEW) — fait passer T004 (depends on T010)
- [ ] T012 [US1] Monter `<VolunteerActionsList>` après `<EventsTable>` dans `frontend/app/(public_restricted)/athletes/[id]/page.tsx` (depends on T011)

**Checkpoint**: US1 fonctionnelle et testable de bout en bout.

---

## Phase 4: Polish & Cross-Cutting Concerns

- [ ] T013 [P] Rejouer les 3 scénarios de `quickstart.md` contre le serveur de dev réel
- [ ] T014 [P] `cd backend && uv run pytest -m "not integration"` — suite complète verte
- [ ] T015 [P] `cd backend && uv run ruff check .`
- [ ] T016 [P] `cd frontend && npm test && npm run lint && npx tsc --noEmit && npm run build`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup / Foundational** : aucune tâche.
- **User Story 1 (Phase 3)** : aucune dépendance externe.
- **Polish** : dépend de US1.

### Within User Story 1

- T005 → T006 → T007 (repository → service → route)
- T008 → T009 → T010 → T011 → T012 (chaîne frontend)
- Les deux chaînes (backend, frontend) sont indépendantes jusqu'à ce que
  T011 consomme le contrat posé par T007 — en pratique développées en
  parallèle, testées ensemble par T003/T004.

### Parallel Opportunities

- T001-T004 (tous les tests US1) en parallèle — fichiers distincts.
- T008 (type TS) en parallèle du backend (T005-T007) — aucune dépendance
  de code, seulement de contrat déjà figé par `contracts/`.

---

## Implementation Strategy

### MVP First

Une seule user story — Foundational + US1 livrent déjà la valeur complète
de l'issue #781. Polish avant PR.

### Hors périmètre (rappel)

Aucune tâche ne touche le workflow de validation (#779, déjà livré sur la
branche parente) ni le formulaire de déclaration (#778).
