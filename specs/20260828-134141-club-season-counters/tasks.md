---

description: "Task list template for feature implementation"
---

# Tasks: Compteurs de saison distincts + validation humaine du quota club

**Input**: Design documents from `specs/20260828-134141-club-season-counters/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: Le Principe III de la constitution (`.specify/memory/constitution.md`) est
**non-négociable** — TDD sans réseau. Chaque tâche d'implémentation est précédée
d'une tâche de test qui doit **échouer** avant l'implémentation, puis passer au vert.

**Organization**: Tasks are grouped by user story (spec.md) to enable independent
implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Peut s'exécuter en parallèle (fichiers différents, aucune dépendance sur une tâche non terminée)
- **[Story]**: US1 (compteurs distincts), US2 (déclarer un bénévolat), US3 (valider la saison)
- Chemins de fichiers exacts dans chaque description

## Path Conventions

Web app existante : `backend/app/`, `backend/tests/`, `frontend/`.

---

## Phase 1: Setup

Aucune tâche : dépôt existant, aucune nouvelle dépendance ni configuration
(`plan.md` §Technical Context).

---

## Phase 2: Foundational (Blocking Prerequisites)

Aucune tâche bloquante partagée par les trois user stories : US1 ne touche à
aucune table nouvelle, US2 et US3 posent chacune leur propre table dans leur
propre phase (`data-model.md`). US3 lit la table posée par US2 pour
l'indicateur de quota (FR-012) — dépendance documentée dans « Dependencies &
Execution Order » ci-dessous, pas une tâche foundational.

---

## Phase 3: User Story 1 - Compteurs de saison fiables (Priority: P1) 🎯 MVP

**Goal**: `/club/athletes` affiche trois compteurs distincts (total réel,
validées, affiliées club) au lieu d'un chiffre unique sous-comptant 39 % du
roster (FR-001 à FR-005).

**Independent Test**: Comparer, pour un athlète connu pour être sous-compté,
le total de sa fiche « Ma saison » au `total_count` renvoyé par
`/club/athletes` — doivent être identiques (`quickstart.md` Scénario 1).

### Tests for User Story 1

> **NOTE: Écrire ces tests D'ABORD, vérifier qu'ils ÉCHOUENT avant implémentation.**

- [X] T001 [P] [US1] Test repository : `list_with_season_participation_count` sélectionne le roster via `tcn_clause(Athlete.club)` (et non plus `Participation.club`) et renvoie `total_count`/`validated_count`/`club_affiliated_count` distincts pour un athlète avec des participations mixtes (validées/en attente, affiliées/non affiliées club) — dans `backend/tests/test_repositories/test_athlete_repository.py` (`research.md` D1, D2)
- [X] T002 [P] [US1] Test API : `GET /athletes/season-activity` renvoie les 3 nouveaux champs et conserve `participation_count` inchangé — dans `backend/tests/test_api/test_athletes_api.py` (`contracts/api.md`)
- [X] T003 [P] [US1] Test frontend : `AthleteSeasonList` affiche les trois compteurs sous des libellés distincts pour un athlète où ils divergent — dans `frontend/components/club/AthleteSeasonList.test.tsx` (FR-004)

### Implementation for User Story 1

- [X] T004 [US1] Réécrire `list_with_season_participation_count` dans `backend/app/repositories/athlete_repository.py` : jointure/`group_by` inchangés, sélection du roster sur `tcn_clause(Athlete.club)`, trois agrégats `func.count`/`func.sum(case(...))` (`research.md` D1, D2) — fait passer T001 au vert
- [X] T005 [P] [US1] Ajouter `total_count`, `validated_count`, `club_affiliated_count` à `AthleteSeasonActivity` dans `backend/app/schemas/athlete.py`
- [X] T006 [US1] Mettre à jour `list_athletes_season_activity` dans `backend/app/api/v1/athletes.py` pour peupler les nouveaux champs depuis T004 (dépend de T004, T005) — fait passer T002 au vert
- [X] T007 [P] [US1] Ajouter les trois champs à `AthleteSeasonActivity` dans `frontend/lib/types.ts`
- [X] T008 [US1] Modifier `frontend/components/club/AthleteSeasonList.tsx` : `total_count` en compteur principal, `validated_count`/`club_affiliated_count` en détail (tooltip ou texte secondaire) — libellés non ambigus (FR-004) (dépend de T007) — fait passer T003 au vert

**Checkpoint**: `/club/athletes` affiche des compteurs exacts et distincts,
livrable et démontrable seul (MVP).

---

## Phase 4: User Story 2 - Déclarer une action de bénévolat (Priority: P2)

**Goal**: Un titulaire d'un pouvoir dédié déclare une action de bénévolat
pour un athlète et une saison, tracée dans `AdminActionLog` (FR-006 à FR-008).

**Independent Test**: Déclarer une action de bénévolat pour un athlète et une
saison, vérifier son apparition dans l'historique de l'athlète et dans
`AdminActionLog`, sans qu'aucune validation de saison n'ait eu lieu
(`quickstart.md` Scénario 2).

### Tests for User Story 2

- [X] T009 [P] [US2] Test repository : créer plusieurs `VolunteerAction` pour le même `(athlete_id, season)` et les relire — dans `backend/tests/test_repositories/test_volunteer_action_repository.py` (nouveau fichier, `data-model.md`)
- [X] T010 [P] [US2] Test service : déclarer un bénévolat écrit une entrée `AdminActionLog` (`action="athlete.volunteer_action.create"`) dans la même transaction — dans `backend/tests/test_services/test_admin_actions.py` (`research.md` D6)
- [X] T011 [P] [US2] Test API : `POST /admin/athletes/{id}/volunteer-actions` renvoie `403` sans `P.ATHLETES_VOLUNTEER_MANAGE`, `201` avec, et accepte deux déclarations successives pour la même saison — dans `backend/tests/test_api/test_admin_data_api.py` (`contracts/api.md`)
- [X] T012 [P] [US2] Test frontend : le panneau de bénévolat n'affiche l'action « Déclarer » qu'à un utilisateur ayant le pouvoir, et l'affiche en lecture seule sinon — dans `frontend/components/athletes/SeasonValidationPanel.test.tsx` (nouveau fichier)

### Implementation for User Story 2

- [X] T013 [US2] Créer le modèle `VolunteerAction` dans `backend/app/models/volunteer_action.py` (`data-model.md` : `athlete_id`, `season`, `declared_by_user_id`, `created_at`)
- [X] T014 [US2] Générer et relire la migration Alembic (`uv run alembic revision --autogenerate`) créant `volunteer_actions` — dans `backend/alembic/versions/` (dépend de T013)
- [X] T015 [P] [US2] Ajouter `P.ATHLETES_VOLUNTEER_MANAGE` (`"athletes:volunteer_manage"`) au catalogue dans `backend/app/core/permissions.py` (`research.md` D7)
- [X] T016 [US2] Créer `backend/app/repositories/volunteer_action_repository.py` : `create(...)`, `exists_for_athlete_season(...)` (dépend de T013) — fait passer T009 au vert
- [X] T017 [US2] Ajouter `declare_volunteer_action(...)` dans `backend/app/services/admin_actions.py` : écrit la ligne puis l'entrée `AdminActionLog`, même transaction, patron `delete_course` (dépend de T016) — fait passer T010 au vert
- [X] T018 [US2] Ajouter `POST /admin/athletes/{athlete_id}/volunteer-actions` dans `backend/app/api/v1/admin_data.py`, gardé par `require_permission(P.ATHLETES_VOLUNTEER_MANAGE)` (dépend de T015, T017) — fait passer T011 au vert
- [X] T019 [P] [US2] Ajouter le schéma `VolunteerActionCreate`/`VolunteerActionOut` dans `backend/app/schemas/athlete.py`
- [X] T020 [P] [US2] Ajouter `useDeclareVolunteerAction` dans `frontend/lib/queries/admin.ts` (patron `useUpdateAthlete`)
- [X] T021 [US2] Créer `frontend/components/athletes/SeasonValidationPanel.tsx` : section « Bénévolat », bouton « Déclarer » gardé par `useSession()` côté client (dépend de T020) — fait passer T012 au vert
- [X] T022 [US2] Intégrer `SeasonValidationPanel` dans `frontend/app/(public_restricted)/athletes/[id]/page.tsx`, aux côtés d'`AthleteAdminPanel` (dépend de T021)

**Checkpoint**: un titulaire du pouvoir dédié peut déclarer une action de
bénévolat, tracée et journalisée, indépendamment de toute validation de
saison.

---

## Phase 5: User Story 3 - Valider la saison d'un athlète (Priority: P3)

**Goal**: Un titulaire d'un pouvoir dédié valide ou dévalide manuellement la
saison d'un athlète du club ; `/club/athletes` permet de trier/filtrer sur ce
statut (FR-009 à FR-014).

**Independent Test**: Donner à un athlète 3 épreuves validées et 1 action de
bénévolat pour la saison, valider sa saison, vérifier le statut visible et
filtrable, puis la dévalider (`quickstart.md` Scénario 3).

### Tests for User Story 3

- [X] T023 [P] [US3] Test repository : créer une `SeasonValidation`, vérifier la contrainte d'unicité `(athlete_id, season)`, puis la supprimer — dans `backend/tests/test_repositories/test_season_validation_repository.py` (nouveau fichier, `data-model.md`)
- [X] T024 [P] [US3] Test service : valider une saison déjà validée lève une erreur `409`-mappable ; dévalider une saison non validée lève une erreur `404`-mappable ; chaque opération écrit une entrée `AdminActionLog` distincte (`create`/`delete`) — dans `backend/tests/test_services/test_admin_actions.py`
- [X] T025 [P] [US3] Test API : `POST`/`DELETE /admin/athletes/{id}/season-validations[/{season}]` gardés par `P.ATHLETES_SEASON_VALIDATE`, codes `201`/`204`/`403`/`404`/`409` — dans `backend/tests/test_api/test_admin_data_api.py` (`contracts/api.md`)
- [X] T026 [P] [US3] Test repository : `season_validated` est `None` quand `seasons` désigne plusieurs saisons, `bool` sinon — dans `backend/tests/test_repositories/test_athlete_repository.py` (`research.md` D9)
- [X] T027 [P] [US3] Test frontend : tri/filtre par statut de validation sur `AthleteSeasonList`, désactivé quand plusieurs saisons sont sélectionnées — dans `frontend/components/club/AthleteSeasonList.test.tsx`
- [X] T028 [P] [US3] Test frontend : le panneau affiche l'indicateur « quota atteint » (3 validées + 1 bénévolat) sans bloquer la validation si non atteint (FR-012), et le bouton bascule Valider/Dévalider selon le statut — dans `frontend/components/athletes/SeasonValidationPanel.test.tsx`

### Implementation for User Story 3

- [X] T029 [US3] Créer le modèle `SeasonValidation` dans `backend/app/models/season_validation.py` avec `UniqueConstraint("athlete_id", "season")` (`data-model.md`)
- [X] T030 [US3] Générer et relire la migration Alembic créant `season_validations` — dans `backend/alembic/versions/` (dépend de T029)
- [X] T031 [P] [US3] Ajouter `P.ATHLETES_SEASON_VALIDATE` (`"athletes:season_validate"`) au catalogue dans `backend/app/core/permissions.py`
- [X] T032 [US3] Créer `backend/app/repositories/season_validation_repository.py` : `create(...)`, `delete(...)`, `get_for_athlete_season(...)` (dépend de T029) — fait passer T023 au vert
- [X] T033 [US3] Ajouter `validate_season(...)`/`unvalidate_season(...)` dans `backend/app/services/admin_actions.py` : vérifie l'état courant (409/404), écrit la ligne puis l'`AdminActionLog` en une transaction (dépend de T032) — fait passer T024 au vert
- [X] T034 [US3] Ajouter `POST`/`DELETE /admin/athletes/{athlete_id}/season-validations[/{season}]` dans `backend/app/api/v1/admin_data.py`, gardés par `require_permission(P.ATHLETES_SEASON_VALIDATE)` (dépend de T031, T033) — fait passer T025 au vert
- [X] T035 [US3] Enrichir `list_with_season_participation_count` (ou une fonction dédiée appelée depuis la route) dans `backend/app/repositories/athlete_repository.py` pour joindre `SeasonValidation` et renvoyer le statut par athlète seulement quand une saison unique est demandée (dépend de T032) — fait passer T026 au vert
- [X] T036 [P] [US3] Ajouter `season_validated: bool | None` à `AthleteSeasonActivity` (`backend/app/schemas/athlete.py`) et le peupler dans `backend/app/api/v1/athletes.py` (dépend de T035)
- [X] T037 [P] [US3] Ajouter `season_validated` à `AthleteSeasonActivity` dans `frontend/lib/types.ts`
- [X] T038 [US3] Ajouter le tri/filtre par statut de validation dans `frontend/components/club/AthleteSeasonList.tsx`, désactivé si plusieurs saisons sélectionnées (dépend de T037) — fait passer T027 au vert
- [X] T039 [P] [US3] Ajouter `useValidateSeason`/`useUnvalidateSeason` dans `frontend/lib/queries/admin.ts`
- [X] T040 [US3] Étendre `frontend/components/athletes/SeasonValidationPanel.tsx` : section « Validation de saison », indicateur de quota (lit `validated_count` de US1 et l'existence d'un bénévolat de US2), bouton Valider/Dévalider (dépend de T039, et fonctionnellement de T008/T021) — fait passer T028 au vert

**Checkpoint**: les trois user stories fonctionnent ensemble ; `/club/athletes`
permet de filtrer sur les athlètes ayant rempli leur quota de saison.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T041 [P] `uv run ruff check .` vert sur `backend/`
- [X] T042 [P] `npm run lint` vert sur `frontend/`
- [ ] T043 Dérouler manuellement les 3 scénarios de `quickstart.md` contre `uv run python scripts/dev_server.py` + `npm run dev` — **partiel** : migrations appliquées (`alembic upgrade head`, base dev locale), backend démarre sans erreur ; parcours navigateur non fait (pas d'outil navigateur dans cette session)
- [X] T044 `uv run pytest -m "not integration"` (backend, 4332/4336 — 4 échecs pré-existants `test_startup_warning.py` sans rapport) et `npm run build`/`npx vitest run --project jsdom` (frontend, 1612/1614) verts

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup / Foundational** : aucune tâche — les user stories démarrent immédiatement.
- **User Story 1 (P1)** : aucune dépendance sur US2/US3 — livrable seule (MVP).
- **User Story 2 (P2)** : aucune dépendance sur US1/US3 — livrable seule.
- **User Story 3 (P3)** : **dépendance fonctionnelle** (pas structurelle) sur
  US1 (`validated_count` pour l'indicateur de quota, T040) et US2
  (`volunteer_action_repository.exists_for_athlete_season`, T040) — les
  routes d'écriture de validation (T029-T034) restent indépendantes et
  testables sans US1/US2 ; seul l'indicateur d'aide (FR-012) les requiert.
- **Polish** : après les user stories livrées.

### Within Each User Story

- Tests écrits et rouges avant l'implémentation qui les fait passer au vert.
- Modèle → migration → repository → service → route → schéma → frontend.

### Parallel Opportunities

- Toutes les tâches `[P]` d'une même phase (fichiers distincts, aucune
  dépendance entre elles) sont lançables ensemble.
- US1 et US2 sont entièrement parallélisables entre deux développeurs dès le
  départ (aucun fichier partagé hors `backend/app/schemas/athlete.py`,
  touché par des ajouts de champs distincts — coordonner sur ce fichier).
- US3 démarre en parallèle de US1/US2 pour ses tâches d'écriture
  (T023-T034), mais T040 (indicateur de quota) attend que T008 et T021/T017
  soient mergés.

---

## Parallel Example: User Story 1

```bash
# Tests, en parallèle :
Task: "Test repository list_with_season_participation_count dans backend/tests/test_repositories/test_athlete_repository.py"
Task: "Test API GET /athletes/season-activity dans backend/tests/test_api/test_athletes_api.py"
Task: "Test frontend AthleteSeasonList dans frontend/components/club/AthleteSeasonList.test.tsx"

# Implémentation, une fois les tests rouges :
Task: "Schéma AthleteSeasonActivity dans backend/app/schemas/athlete.py"
Task: "Type AthleteSeasonActivity dans frontend/lib/types.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Compléter Phase 3 (US1).
2. **STOP et VALIDER** : Scénario 1 de `quickstart.md`, seul.
3. Démo possible : `/club/athletes` affiche des compteurs exacts — la
   correction du bug mesuré (39 % du roster sous-compté) est livrée sans
   attendre le reste de l'issue.

### Incremental Delivery

1. US1 → démo (correctif du bug, valeur immédiate).
2. US2 → démo (bénévolat déclarable et tracé, encore sans effet sur le tri).
3. US3 → démo (validation de saison, tri/filtre, indicateur de quota
   complet).

## Notes

- `[P]` = fichiers différents, aucune dépendance non résolue.
- Vérifier que chaque test échoue avant d'écrire l'implémentation
  correspondante (Principe III).
- Committer après chaque tâche ou groupe logique cohérent.
- S'arrêter à chaque checkpoint pour valider la user story indépendamment.
