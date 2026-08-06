---

description: "Tâches d'implémentation — actions d'administration sur les épreuves, les athlètes et les résultats"
---

# Tasks: Actions d'administration sur les épreuves, les athlètes et les résultats

**Input**: Design documents from `specs/20260806-180938-admin-crud-actions/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/admin-data-api.md](contracts/admin-data-api.md), [quickstart.md](quickstart.md)

**Tests**: Principe III de la constitution — **non-négociable**. Chaque user story
porte ses tâches de test, écrites **avant** l'implémentation, et rouges avant
d'être vertes. Aucune dérogation demandée pour cette feature.

## Format: `[ID] [P?] [Story] Description`

- **[P]** : parallélisable — fichiers différents, aucune dépendance sur une tâche inachevée
- **[Story]** : US1 / US2 / US3 / US4, en regard des user stories de `spec.md`
- Chemins exacts dans chaque description

## Path Conventions

Application web à deux piles, arborescence existante (plan.md §Project
Structure). Le backend suit ses conventions de test par couche
(`tests/test_api/`, `tests/test_services/`, `tests/test_repositories/`) — il n'y
a **pas** de `tests/contract/` ni de `tests/integration/` dans ce dépôt. Le
front colocalise ses tests (`X.test.tsx` à côté de `X.tsx`).

---

## Phase 1: Setup

**Purpose**: établir la ligne de base. Le projet est existant : rien à
initialiser, tout à vérifier.

- [X] T001 Établir la ligne de base verte : `cd backend && uv run pytest -m "not integration"` et `uv run ruff check .`, puis `cd frontend && npm test && npm run build`. Noter le nombre de tests au départ — c'est la référence de non-régression de toute la branche.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: le journal d'audit et les pouvoirs traversent les quatre stories.
Rien d'utilisateur n'est livré ici, et c'est ce qui rend les quatre tranches
suivantes indépendantes.

**⚠️ CRITICAL**: aucune user story ne démarre avant la fin de cette phase.

- [X] T002 [P] Écrire `backend/tests/test_repositories/test_admin_action_log_repository.py` : `create` persiste auteur, action, type, id d'entité, payload et horodatage ; `list_for_entity` rend les entrées d'une entité, plus récente d'abord ; une entrée survit à la disparition de l'entité qu'elle décrit (FR-014). Rouge attendu.
- [X] ~~T003~~ **Reporté dans les stories** (constaté à l'implémentation) : `tests/test_permissions_catalogue.py` est paramétré sur `permissions.ALL` et exige que **chaque** pouvoir du catalogue garde déjà une ressource. Déclarer les cinq pouvoirs ici rendrait cinq tests rouges jusqu'à la Phase 6. Chaque pouvoir naît donc **avec sa garde**, dans la story qui la pose, et son passage dans `GET /admin/permissions` s'y vérifie.
- [X] T004 Créer le modèle `AdminActionLog` dans `backend/app/models/admin_action_log.py` selon [data-model.md](data-model.md) — `user_id` en FK **sans** `ondelete`, `entity_id` **sans** FK (c'est l'invariant qui permet de tracer une suppression), trois index.
- [X] T005 Enregistrer le modèle dans `backend/app/models/__init__.py` puis générer la migration : `cd backend && uv run alembic revision --autogenerate -m "admin action log"`. **Relire la révision à la main** (constitution §Additional Constraints) : elle ne doit contenir qu'un `create_table` et trois index. Toute autre opération proposée signale une dérive de modèle à instruire avant de continuer.
- [X] T006 Appliquer et vérifier : `uv run alembic upgrade head`, puis `uv run alembic downgrade -1` et `upgrade head` à nouveau — un `downgrade` qui casse est une migration à corriger maintenant, pas en production.
- [X] T007 Implémenter `backend/app/repositories/admin_action_log_repository.py` (`create`, `list_for_entity`) — T002 passe au vert.
- [X] ~~T008~~ **Scindé par story**, même motif que T003 : US1 déclare `courses:delete`, US2 `athletes:read` et `participations:reassign`, US3 `athletes:write`, US4 `courses:write` — chacun dans le commit qui pose sa garde. Les constantes `FEATURE_COURSES` et `FEATURE_ATHLETES` naissent avec leur premier pouvoir.
- [X] T009 Créer `backend/app/api/v1/admin_data.py` (router vide, docstring expliquant pourquoi les gardes sont individuelles et jamais posées sur le préfixe `/admin`) et le monter dans la boucle de `backend/app/api/v1/router.py`.
- [X] T010 Créer `backend/app/services/admin_actions.py` avec sa docstring de contrat : chaque geste `flush`, ne `commit` jamais (le router commite), et n'écrit au journal que sur succès (FR-015).

**Checkpoint**: journal, pouvoirs et point de montage en place. Les quatre stories peuvent démarrer.

---

## Phase 3: User Story 1 - Retirer une épreuve importée par erreur (Priority: P1) 🎯 MVP

**Goal**: un administrateur habilité supprime une épreuve depuis le back-office ; ses résultats et les fiches coureur devenues vides disparaissent avec elle, l'ampleur est annoncée avant, et l'opération est tracée.

**Independent Test**: importer une épreuve de test, la supprimer depuis `/admin/courses`, vérifier qu'elle a disparu du catalogue public, que le nombre de fiches coureur annoncé est exactement celui supprimé, et qu'une entrée `course.delete` figure au journal.

### Tests for User Story 1

> **Écrire ces tests EN PREMIER et vérifier qu'ils échouent** (Principe III, non-négociable).

- [X] T011 [P] [US1] Dans `backend/tests/test_repositories/test_course_repository.py` : `delete` retire l'épreuve **et** ses participations (cascade ORM, AC1), et ne touche pas les épreuves voisines.
- [X] T012 [P] [US1] Dans `backend/tests/test_repositories/test_athlete_repository.py` : `only_on_course` rend les athlètes dont **toutes** les participations sont sur l'épreuve visée ; `delete_orphans_among` ne supprime que les ids fournis **et** réellement sans participation ; `delete_orphans()` sans argument garde son comportement et son type de retour `int` (non-régression de `rescrape_service`).
- [X] T013 [P] [US1] Créer `backend/tests/test_services/test_admin_actions.py` : `delete_course` supprime, purge les fiches devenues vides (FR-022), écrit **une** entrée `course.delete` portant le nom de l'épreuve, le nombre de résultats et les ids purgés (FR-013) ; sur épreuve inexistante, lève `NotFoundError` et n'écrit **rien**.
- [X] T014 [P] [US1] Dans le même fichier : test d'ancrage SC-007 — sur une même épreuve, le compte rendu par le calcul d'impact est **exactement** celui supprimé ensuite. C'est le test qui empêche les deux définitions de diverger.
- [X] T015 [P] [US1] Créer `backend/tests/test_api/test_admin_data_api.py` : `DELETE /api/v1/admin/courses/{id}` → 204 avec le pouvoir, 403 sans, 401 sans session, 404 sur identifiant inconnu ; `GET /api/v1/admin/courses/{id}/deletion-impact` → 200 avec `participations` et `athletes`, **sans rien modifier**, 403 sans pouvoir, 404 sur identifiant inconnu.
- [X] T016 [P] [US1] Créer `frontend/components/admin/DeleteCourseDialog.test.tsx` : la modale nomme l'épreuve, le nombre de résultats **et** le nombre de fiches coureur (FR-017) ; aucun bouton d'annulation après confirmation (FR-018) ; l'échec affiche un message français.
- [X] T017 [P] [US1] Créer `frontend/components/admin/CoursesAdminTable.test.tsx` : le bouton de suppression est absent sans le pouvoir `courses:delete` (FR-011) ; 401, 403 et panne donnent trois messages distincts, et **jamais** « aucune épreuve » (le piège documenté par `PendingProvidersTable`).

### Implementation for User Story 1

- [X] T018 [P] [US1] Ajouter `delete(db, course)` à `backend/app/repositories/course_repository.py`, avec un commentaire `ponytail:` nommant le plafond assumé (cascade ORM = un DELETE par participation ; sortie = bulk delete + `ondelete` si le volume change de nature).
- [X] T019 [P] [US1] Ajouter `only_on_course(db, course_id)` et `delete_orphans_among(db, athlete_ids=None)` à `backend/app/repositories/athlete_repository.py` ; faire déléguer `delete_orphans(db)` à la nouvelle fonction en conservant son `int` (research.md §D5).
- [X] T020 [US1] Ajouter `CourseDeletionImpact` à `backend/app/schemas/admin.py`.
- [X] T021 [US1] Implémenter `delete_course` et `course_deletion_impact` dans `backend/app/services/admin_actions.py` — l'impact et la purge **appellent la même fonction de repository**, c'est ce qui rend SC-007 structurel plutôt que surveillé. **Ordre imposé** : relever les candidats (`only_on_course`) **avant** la suppression. Après, leurs participations n'existent plus, la liste revient vide, et la purge devient un no-op silencieux qu'aucune erreur ne signale.
- [X] T022 [US1] Ajouter les deux routes à `backend/app/api/v1/admin_data.py`, gardées par `require_permission(P.COURSES_DELETE)`, avec `db.commit()` dans la route de suppression.
- [X] T023 [P] [US1] Ajouter `getCourseDeletionImpact` et `deleteCourse` à `frontend/lib/api/client.ts`, les clés dans `frontend/lib/queries/keys.ts`, la lecture et la mutation dans `frontend/lib/queries/admin.ts` (invalidation de la liste d'épreuves au succès).
- [X] T024 [US1] Créer `frontend/app/admin/courses/page.tsx` (le layout `/admin` existant la protège déjà) et `frontend/components/admin/CoursesAdminTable.tsx` : liste alimentée par `GET /courses`, gating par `useSession().data.permissions`, distinction 401 / 403 / panne sur le patron de `PendingProvidersTable`.
- [X] T025 [US1] Créer `frontend/components/admin/DeleteCourseDialog.tsx` sur `components/ui/dialog.tsx` : charge l'impact à l'ouverture, annonce les deux nombres, confirme, `toast` de succès ou d'échec en français.
- [X] T026 [US1] Ajouter le lien vers `/admin/courses` depuis `frontend/app/admin/page.tsx` — sans point d'entrée, l'écran n'existe que pour qui connaît l'URL.

**Checkpoint**: US1 livrable et démontrable seule. C'est le MVP.

---

## Phase 4: User Story 2 - Rattacher un résultat au bon coureur (Priority: P2)

**Goal**: un administrateur habilité déplace un résultat vers la bonne fiche coureur, en voyant ce qui distingue deux homonymes, et la fiche d'origine devenue vide disparaît.

**Independent Test**: créer deux fiches pour une même personne, déplacer un résultat de l'une vers l'autre, vérifier les deux historiques et l'entrée de journal.

### Tests for User Story 2

- [X] T027 [P] [US2] Dans `backend/tests/test_repositories/test_participation_repository.py` : `exists_for_athlete_on_course` détecte un coureur déjà classé sur l'épreuve ; `reassign` réécrit `athlete_id` sans toucher temps, rangs ni statut.
- [X] T028 [P] [US2] Dans `backend/tests/test_repositories/test_athlete_repository.py` : `search_admin` filtre sur nom **et** prénom, rend l'identité complète (dont `birth_date`) et le nombre de résultats de chaque fiche (FR-024).
- [X] T029 [P] [US2] Dans `backend/tests/test_services/test_admin_actions.py` : `reassign_participation` réécrit le rattachement, purge la fiche d'origine si elle perd son dernier résultat, écrit une entrée `participation.reassign` avec origine et destination (AC3) ; refuse (`DuplicateError`) si la cible est déjà classée sur l'épreuve (FR-006) ; refuse (`NotFoundError`) sur résultat ou coureur inconnu ; un rattachement vers le coureur **déjà** porteur réussit sans rien changer et **n'écrit aucune entrée** — une demande sans effet n'est pas un geste (FR-012).
- [X] T030 [P] [US2] Dans `backend/tests/test_api/test_admin_data_api.py` : `POST /api/v1/admin/participations/{id}/reassign` → 200 / 403 / 401 / 404 / 409 ; `GET /api/v1/admin/athletes?search=` → 200 (liste vide comprise), 403 sans `athletes:read`.
- [X] T031 [P] [US2] Dans `backend/tests/test_api/test_athletes_api.py` : **non-régression FR-025** — `GET /api/v1/athletes` et `GET /api/v1/athletes/{id}` ne rendent aucune `birth_date`. Ce test garde la porte que `athletes:read` protège.
- [X] T032 [P] [US2] Créer `frontend/components/admin/AthleteSearchPicker.test.tsx` : chaque proposition affiche date de naissance, club et nombre de résultats ; deux homonymes du même club restent distinguables ; aucune sélection possible tant que rien n'est choisi.
- [X] T033 [P] [US2] Créer `frontend/components/admin/ReassignParticipationDialog.test.tsx` : confirmation, message français sur 409, pas d'annulation offerte ; le déclencheur est **absent** sans le pouvoir `participations:reassign` (FR-011).

### Implementation for User Story 2

- [X] T034 [P] [US2] Ajouter `exists_for_athlete_on_course` et `reassign` à `backend/app/repositories/participation_repository.py`.
- [X] T035 [P] [US2] Ajouter `search_admin` à `backend/app/repositories/athlete_repository.py` (identité complète + compte de participations, en une requête).
- [X] T036 [US2] Ajouter `AdminAthleteRead` et `ParticipationReassign` à `backend/app/schemas/admin.py`.
- [X] T037 [US2] Implémenter `reassign_participation` dans `backend/app/services/admin_actions.py`.
- [X] T038 [US2] Ajouter les deux routes à `backend/app/api/v1/admin_data.py` (`participations:reassign` et `athletes:read`).
- [X] T039 [P] [US2] Ajouter `searchAthletesAdmin` et `reassignParticipation` à `frontend/lib/api/client.ts`, les types dans `frontend/lib/types.ts`, la lecture et la mutation dans `frontend/lib/queries/admin.ts`.
- [X] T040 [US2] Créer `frontend/components/admin/AthleteSearchPicker.tsx` (recherche debouncée via le hook `useDebounce` existant).
- [X] T041 [US2] Créer `frontend/components/admin/ReassignParticipationDialog.tsx` et l'accrocher aux résultats d'une épreuve depuis `CoursesAdminTable`.

**Checkpoint**: US1 et US2 fonctionnent indépendamment.

---

## Phase 5: User Story 3 - Corriger l'identité d'un coureur (Priority: P3)

**Goal**: un administrateur habilité corrige nom, prénom et date de naissance d'une fiche coureur, sans jamais créer de doublon d'identité.

**Independent Test**: renommer un coureur et vérifier que la correction s'affiche partout, historique intact ; retenter vers une identité déjà prise et constater le refus.

### Tests for User Story 3

- [X] T042 [P] [US3] Dans `backend/tests/test_services/test_admin_actions.py` : `update_athlete` écrit les champs **présents seulement** (sémantique PATCH stricte), écrit une entrée `athlete.update` avec avant/après ; refuse (`DuplicateError`) une identité déjà prise en la **nommant** (AC2) et laisse la fiche strictement inchangée ; refuse un `nom` ou `prenom` blanc.
- [X] T043 [P] [US3] Dans `backend/tests/test_api/test_admin_data_api.py` : `PATCH /api/v1/admin/athletes/{id}` → 200 / 403 / 401 / 404 / 409, et 422 sur corps vide.
- [X] T044 [P] [US3] Créer `frontend/components/admin/EditAthleteDialog.test.tsx` : le message de conflit nomme la fiche en cause ; le formulaire ne se vide pas après un refus ; le déclencheur est **absent** sans le pouvoir `athletes:write` (FR-011).

### Implementation for User Story 3

- [X] T045 [US3] Ajouter `AdminAthleteUpdate` à `backend/app/schemas/admin.py` (champs facultatifs, `min_length=1` sur les chaînes, validateur refusant un corps sans aucun champ).
- [X] T046 [US3] Ajouter `update_identity` à `backend/app/repositories/athlete_repository.py`.
- [X] T047 [US3] Implémenter `update_athlete` dans `backend/app/services/admin_actions.py` — contrôle d'unicité **par lecture préalable** (`get_by_identity`), jamais en s'en remettant à l'`IntegrityError` (research.md §D6).
- [X] T048 [US3] Ajouter la route à `backend/app/api/v1/admin_data.py` (`athletes:write`).
- [X] T049 [P] [US3] Ajouter `updateAthlete` à `frontend/lib/api/client.ts` et la mutation dans `frontend/lib/queries/admin.ts`.
- [X] T050 [US3] Créer `frontend/components/admin/EditAthleteDialog.tsx`, atteignable depuis un résultat d'épreuve (FR-016). **Pas** depuis la recherche de coureurs : US3 resterait dépendante de US2, et aucun scénario ne le demande (spec §Hors périmètre).

**Checkpoint**: US1, US2 et US3 fonctionnent indépendamment.

---

## Phase 6: User Story 4 - Corriger le libellé d'une épreuve (Priority: P4)

**Goal**: un administrateur habilité corrige nom, date, type et caractère relais d'une épreuve, sans toucher un seul résultat ni créer de doublon d'épreuve.

**Independent Test**: renommer une épreuve, vérifier que le catalogue suit et que les temps et rangs des résultats sont identiques ; retenter vers une identité déjà prise et constater le refus.

### Tests for User Story 4

- [X] T051 [P] [US4] Dans `backend/tests/test_services/test_admin_actions.py` : `update_course` écrit les champs présents seulement, écrit une entrée `course.update` avec avant/après ; refuse (`DuplicateError`) le quadruplet déjà pris en **nommant** l'épreuve en conflit (FR-021) ; **aucun résultat n'est modifié** — temps, rangs, statut et rattachements identiques avant/après (FR-023).
- [X] T052 [P] [US4] Dans `backend/tests/test_api/test_admin_data_api.py` : `PATCH /api/v1/admin/courses/{id}` → 200 / 403 / 401 / 404 / 409, 422 sur corps vide, et `event_date: null` explicite distingué de l'absence du champ.
- [X] T053 [P] [US4] Créer `frontend/components/admin/EditCourseDialog.test.tsx` : les quatre champs sont éditables, le message de conflit nomme l'épreuve en cause ; le déclencheur est **absent** sans le pouvoir `courses:write` (FR-011).

### Implementation for User Story 4

- [X] T054 [US4] Ajouter `AdminCourseUpdate` à `backend/app/schemas/admin.py`.
- [X] T055 [US4] Ajouter `update_identity` à `backend/app/repositories/course_repository.py`.
- [X] T056 [US4] Implémenter `update_course` dans `backend/app/services/admin_actions.py`.
- [X] T057 [US4] Ajouter la route à `backend/app/api/v1/admin_data.py` (`courses:write`).
- [X] T058 [P] [US4] Ajouter `updateCourse` à `frontend/lib/api/client.ts` et la mutation dans `frontend/lib/queries/admin.ts`.
- [X] T059 [US4] Créer `frontend/components/admin/EditCourseDialog.tsx` et son bouton dans `CoursesAdminTable`.

**Checkpoint**: les quatre stories fonctionnent indépendamment.

---

## Phase 7: Polish & Cross-Cutting Concerns

### Retours de revue de code (2026-08-06)

Une revue par sous-agent a relevé 4 problèmes importants et 7 mineurs, aucun
critique. Tous vérifiés avant correction — aucun n'était infondé.

- [X] R1 `PATCH {"nom": null}` rendait **500** (`IntegrityError`) au lieu du 422 du contrat : le `None` de ces champs veut dire « absent », pas « NULL ». Garde `_NULLABLES` par modèle.
- [X] R2 `nom = "   "` était écrit tel quel — `min_length=1` compte les caractères, pas les non-blancs, et mon test choisissait `""`, le cas déjà couvert. `str_strip_whitespace` + tests paramétrés sur `"   "`.
- [X] R3 L'écran plafonnait à 50 épreuves sans pagination : **211 en base de dev**, donc 161 inatteignables, ce qui vidait SC-001. Pagination + recherche serveur (`q`) dans les résultats d'une épreuve.
- [X] R4 `event_type` était un champ libre : un `triathlon_m` fautif retirait l'épreuve des filtres fédéraux **en silence**. Validé contre `classify.CANONICAL_TYPES` (les 18 types en base sont canoniques, aucune donnée existante n'est bloquée).
- [X] R5 `only_on_course` — plafond mémoire nommé par un commentaire `ponytail:` (le `NOT EXISTS` corrélé est la sortie si le volume change).
- [X] R6 Docstring de `course_deletion_impact` : SC-007 tient **à base constante**, pas entre deux requêtes HTTP. La promesse est bornée.
- [X] R7 Clé de cache `adminCourseDetail` distincte de `courseParticipations`, qui porte un autre type.
- [X] R8 Branches 401/403 de `CoursesAdminTable` retirées : `GET /courses` est public, elles étaient inatteignables et leurs tests fabriquaient un état impossible (Principe VI).
- [X] R9 `data-model.md` aligné : les instantanés portent le triplet/quadruplet entier, pas les seuls champs modifiés.
- [X] R10 Helper `_fiche()` — trois constructions identiques d'`AdminAthleteRead` supprimées.
- [X] R11 `CourseParticipationsDialog` : test créé, et cul-de-sac corrigé — un rôle `athletes:write` sans `athletes:read` bloquait l'écran sans message. État **dérivé**, pas corrigé dans un effet.
- [X] R12 Tests manquants ajoutés : un 409 n'écrit rien au journal à l'étage HTTP, et un `event_type` de la nomenclature est accepté.


- [X] T060 [P] Documenter les routes d'administration des données dans `backend/app/api/AGENTS.md` : les six routes, leurs pouvoirs, et **pourquoi** aucune garde n'est posée sur le préfixe `/admin`.
- [X] T061 [P] Ajouter la ligne « Actions d'administration sur les données (#117) » à la table « Où lire quoi » de `AGENTS.md` si — et seulement si — la note de T060 ne suffit pas à la trouver.
- [ ] T062 Dérouler `quickstart.md` §2 en entier (scénarios A à E) sur une base de démonstration, dans le navigateur.
- [X] T063 Vérifier les trois non-régressions de `quickstart.md` §3 : signalement anonyme toujours ouvert, contrats de lecture publics inchangés, `orphans_removed` toujours entier dans la CLI.
- [X] T064 `cd backend && uv run pytest -m "not integration" && uv run ruff check .` puis `cd frontend && npm test && npm run lint && npm run build` — comparer le nombre de tests à la ligne de base de T001.
- [ ] T065 Clôture de branche : `requesting-code-review`, puis `verification-before-completion`, puis `finishing-a-development-branch` (AGENTS.md §Workflow IA). La PR lie l'issue par `Closes #117` — mot-clé anglais, c'est un jeton machine.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** : aucune dépendance.
- **Foundational (Phase 2)** : dépend de Setup — **bloque les quatre stories**.
- **User Stories (Phases 3 à 6)** : toutes dépendent de Phase 2, et d'elle seule.
- **Polish (Phase 7)** : dépend des stories livrées.

### User Story Dependencies

Les quatre stories sont **indépendantes entre elles** — aucune ne dépend du code
d'une autre. Deux points de contact seulement, et ce sont des points
d'assemblage, pas des dépendances logiques :

- US2, US3 et US4 accrochent leurs boutons dans `CoursesAdminTable.tsx`, créé
  par US1. Livrées avant US1, elles poseraient leur propre point d'entrée.
- US1 et US2 partagent `delete_orphans_among` (T019). Si US2 passe en premier,
  la tâche migre vers sa phase.

### Within Each User Story

- Tests écrits **et rouges** avant l'implémentation (Principe III).
- Repositories → schémas → service → route → front.
- Story complète et vérifiée avant de passer à la suivante.

### Parallel Opportunities

- **Phase 2** : T002 et T003 en parallèle (fichiers de test distincts).
- **Chaque story** : toutes les tâches de test marquées [P] en parallèle — elles touchent des fichiers différents.
- **US1** : T018 et T019 en parallèle (deux repositories distincts) ; T023 en parallèle du backend.
- **US2** : T034 et T035 en parallèle ; T039 en parallèle du backend.
- **Entre stories** : une fois Phase 2 finie, US1 à US4 sont parallélisables à plusieurs. À une personne, l'ordre de priorité reste le bon.

Attention : `admin_actions.py`, `admin_data.py` et `schemas/admin.py` sont
touchés par les quatre stories. Deux stories menées en parallèle par deux
personnes s'y croiseront — c'est le seul point de friction du découpage.

---

## Parallel Example: User Story 1

```bash
# Les sept tests de US1, ensemble — sept fichiers distincts :
Task: "T011 delete + cascade dans tests/test_repositories/test_course_repository.py"
Task: "T012 only_on_course + delete_orphans_among dans tests/test_repositories/test_athlete_repository.py"
Task: "T013 delete_course dans tests/test_services/test_admin_actions.py"
Task: "T015 routes DELETE et deletion-impact dans tests/test_api/test_admin_data_api.py"
Task: "T016 DeleteCourseDialog.test.tsx"
Task: "T017 CoursesAdminTable.test.tsx"

# Puis les deux repositories, ensemble :
Task: "T018 course_repository.delete"
Task: "T019 athlete_repository.only_on_course + delete_orphans_among"
```

---

## Implementation Strategy

### MVP (User Story 1 seule)

1. Phase 1 — ligne de base verte.
2. Phase 2 — journal, pouvoirs, montage. **Bloquant.**
3. Phase 3 — suppression d'épreuve, de bout en bout.
4. **Arrêt et validation** : quickstart §2 scénario A, plus le scénario E (droits).
5. Démontrable. C'est déjà le geste qui manquait le plus.

### Livraison incrémentale

Chaque story ajoute un geste sans toucher aux précédents : US2 (rattachement),
puis US3 (identité coureur), puis US4 (libellé d'épreuve). Chacune se valide par
son scénario du quickstart et peut s'arrêter là.

---

## Notes

- Un test qui passe du premier coup, avant l'implémentation, ne teste rien : le vérifier rouge fait partie de la tâche.
- Le refus est aussi important que le succès. Chaque geste a ses tests de refus (404, 409, 403, 401), et **tous** vérifient que la base est inchangée.
- Les messages rendus à l'utilisateur sont en français ; les codes de `action`, les identifiants et les noms de tests en anglais (Principe I).
- Commit par tâche ou par groupe cohérent.
