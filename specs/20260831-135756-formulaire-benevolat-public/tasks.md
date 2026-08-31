---

description: "Task list for #778 — formulaire public de déclaration de bénévolat"

---

# Tasks: Formulaire public de déclaration de bénévolat

**Input**: Design documents from `specs/20260831-135756-formulaire-benevolat-public/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/volunteer-action-public-api.md, quickstart.md

**Tests**: Principe III de la constitution v1.2.0 — TDD sans réseau, non-négociable. Chaque tâche d'implémentation backend est précédée d'un test qui échoue.

**Organization**: Tasks are grouped by user story (spec.md).

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

Aucune tâche : projet existant, dépendances déjà déclarées (`uv sync`,
`npm ci`). Rien à initialiser pour cette feature.

## Phase 2: Foundational

Aucune tâche distincte : le modèle étendu, le schéma et la route ne servent
qu'à l'US1 (US2 ne touche aucun fichier backend, cf. research.md D2) — ils
vivent directement dans la Phase 3, pas de prérequis partagé entre user
stories.

---

## Phase 3: User Story 1 - Déclarer une action de bénévolat pour un athlète (Priority: P1) 🎯 MVP

**Goal**: Un adhérent connecté recherche un athlète, saisit titre +
description, crée une déclaration `VolunteerAction` à l'état « en attente ».

**Independent Test**: cf. spec.md US1 Acceptance Scenarios 1-4 /
quickstart.md Scénarios 1, 2, 4.

### Tests for User Story 1

> **Écrire ces tests d'abord, vérifier qu'ils échouent avant implémentation.**

- [X] T001 [P] [US1] Test repository : `create_pending()` crée une ligne `status="en_attente"` avec `title`/`description` ; `create()` existant (chemin admin) reste inchangé (title/description restent `None`, `status` prend le défaut DB) dans `backend/tests/test_repositories/test_volunteer_action_repository.py`
- [X] T002 [P] [US1] Test service : `volunteer_action_service.create_pending` crée pour l'athlète choisi, saison = `current_season()`, lève `NotFoundError` si `athlete_id` inconnu dans `backend/tests/test_services/test_volunteer_action_service.py` (NEW)
- [X] T003 [P] [US1] Test API : `POST /api/v1/volunteer-actions` — `201` corps valide, `422` titre/description vide **et** `422` titre >200 ou description >10 000 caractères, `401` sans session, `404` `athlete_id` inconnu dans `backend/tests/test_api/test_volunteer_actions_api.py` (NEW)
- [X] T004 [P] [US1] Test composant : `VolunteerActionForm` — aucune requête sous 2 caractères, recherche déclenchée à partir de 2 caractères, état vide explicite si aucun athlète ne correspond, sélection d'un athlète, soumission désactivée si titre/description vide, bouton désactivé pendant la requête dans `frontend/components/benevolat/VolunteerActionForm.test.tsx` (NEW)

### Implementation for User Story 1

- [X] T005 [US1] Ajouter les colonnes `title` (nullable), `description` (nullable), `status` (`NOT NULL`, défaut `"en_attente"`) à `VolunteerAction` dans `backend/app/models/volunteer_action.py`
- [X] T006 [US1] Générer et relire la migration Alembic (`uv run alembic revision --autogenerate -m "add title/description/status to volunteer_actions"`) dans `backend/alembic/versions/` (depends on T005)
- [X] T007 [P] [US1] Créer `VolunteerActionSelfCreate` (`athlete_id`, `title` 1-200, `description` 1-10 000 — noms distincts de `VolunteerActionCreate`/`Out` de `admin.py`, cf. `/speckit-analyze` finding C1) et `VolunteerActionSelfOut` dans `backend/app/schemas/volunteer_action.py` (NEW) (depends on T005)
- [X] T008 [US1] Implémenter `create_pending()` dans `backend/app/repositories/volunteer_action_repository.py` — fait passer T001 (depends on T005)
- [X] T009 [US1] Implémenter `volunteer_action_service.create_pending()` (résout l'athlète ou `NotFoundError`, saison via `app.core.season.current_season()`, délègue au repository) dans `backend/app/services/volunteer_action_service.py` (NEW) — fait passer T002 (depends on T007, T008)
- [X] T010 [US1] Implémenter `POST /volunteer-actions` (garde `current_user`, aucun pouvoir RBAC) dans `backend/app/api/v1/volunteer_actions.py` (NEW) — fait passer T003 (depends on T009)
- [X] T011 [US1] Enregistrer le nouveau router (hors `_EXEMPTES_DE_LA_GARDE_SITE`) dans `backend/app/api/v1/router.py` (depends on T010)
- [X] T012 [P] [US1] Ajouter `createVolunteerAction` et `searchAthletesConnected` (réutilise `GET /athletes`, cf. research.md D2) dans `frontend/lib/api/client.ts` (depends on T007 pour la forme du contrat)
- [X] T013 [P] [US1] Ajouter les types `VolunteerActionSelfCreate`/`VolunteerActionSelfOut` dans `frontend/lib/types.ts` — noms distincts de l'interface `VolunteerAction` déjà existante (l.928, flux admin, cf. `/speckit-analyze` finding C2) (depends on T007)
- [X] T014 [US1] Créer `useCreateVolunteerAction` (mutation) dans `frontend/lib/queries/volunteer-actions.ts` (NEW) (depends on T012, T013)
- [X] T015 [US1] Implémenter `VolunteerActionForm.tsx` (recherche d'athlète — patron `ReattributionField.tsx`, débounce 300 ms, seuil 2 caractères — + champs titre/description + soumission) dans `frontend/components/benevolat/VolunteerActionForm.tsx` (NEW) — fait passer T004 (depends on T014)
- [X] T016 [US1] Ajouter la section « Créditer un athlète pour le quota de saison » à la page existante dans `frontend/app/(public_restricted)/benevolat/page.tsx` (depends on T015)

**Checkpoint**: US1 fonctionnelle et testable de bout en bout.

---

## Phase 4: User Story 2 - Rechercher un athlète sans exposer de données sensibles (Priority: P2)

**Goal**: Confirmer que la recherche du formulaire ne rend jamais de champ
réservé aux admins et ne dépend pas du mot de passe bénévoles.

**Independent Test**: cf. spec.md US2 Acceptance Scenarios 1-2 /
quickstart.md Scénario 3.

**Note** : aucune implémentation backend dédiée — `GET /athletes` est
réutilisée telle quelle (research.md D2), déjà couverte par
`backend/tests/test_api/test_athletes_api.py` (rend `AthleteBrief`, jamais
`birth_date`). Le câblage frontend est livré par T012/T015 de l'US1 ; cette
phase n'ajoute qu'un test dédié qui verrouille la propriété côté composant.

### Tests for User Story 2

- [X] T017 [US2] Étendre le test de `VolunteerActionForm` : les résultats de recherche affichés ne portent que nom/prénom/club (jamais de date de naissance) dans `frontend/components/benevolat/VolunteerActionForm.test.tsx` (depends on T015)

**Checkpoint**: US1 et US2 fonctionnelles indépendamment.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [ ] T018 [P] Rejouer les 4 scénarios de `quickstart.md` contre le serveur de dev réel
- [ ] T019 [P] `cd backend && uv run pytest -m "not integration"` — suite complète verte
- [ ] T020 [P] `cd backend && uv run ruff check .`
- [ ] T021 [P] `cd frontend && npm test && npm run lint && npx tsc --noEmit && npm run build`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup / Foundational** : aucune tâche — l'US1 démarre immédiatement.
- **User Story 1 (Phase 3)** : aucune dépendance externe.
- **User Story 2 (Phase 4)** : dépend de T015 (US1) — le composant qu'elle teste doit exister.
- **Polish (Phase 5)** : dépend de US1 et US2 complètes.

### Within User Story 1

- T005 → T006, T007, T008 (colonnes avant migration, schéma, repository)
- T007, T008 → T009 (service a besoin du schéma et du repository)
- T009 → T010 → T011 (router avant enregistrement)
- T007 → T012, T013 (contrat avant client/types front)
- T012, T013 → T014 → T015 → T016

### Parallel Opportunities

- T001-T004 (tous les tests US1) en parallèle — fichiers distincts.
- T007 (schéma) en parallèle de T006 (migration) une fois T005 fait.
- T012 et T013 (fichiers front distincts) en parallèle.

---

## Parallel Example: User Story 1

```bash
# Tests US1, en parallèle :
Task: "Repository test in backend/tests/test_repositories/test_volunteer_action_repository.py"
Task: "Service test in backend/tests/test_services/test_volunteer_action_service.py"
Task: "API test in backend/tests/test_api/test_volunteer_actions_api.py"
Task: "Component test in frontend/components/benevolat/VolunteerActionForm.test.tsx"
```

---

## Implementation Strategy

### MVP First

1. Phase 3 (US1) seule livre déjà la valeur complète de l'issue #778 —
   c'est aussi tout le périmètre de cette sous-issue.
2. Phase 4 (US2) verrouille une propriété de sécurité déjà vraie par
   construction (réutilisation de `GET /athletes`) — s'exécute juste après,
   coût marginal.
3. Phase 5 avant PR.

### Hors périmètre (rappel FR-008/FR-009)

Aucune tâche ne touche `SeasonValidationPanel.tsx`,
`admin_data.declare_volunteer_action`, ni n'implémente la transition de
statut « en attente » → « validée » — sous-issues #780 et #779.
