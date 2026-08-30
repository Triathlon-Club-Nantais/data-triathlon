---

description: "Task list for Déclaration de bénévolat (#751)"

---

# Tasks: Déclaration de bénévolat

**Input**: Design documents from `specs/20260830-160242-declaration-benevolat/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Le Principe III de la constitution v1.2.0 est non-négociable — TDD
sans réseau. Toute la logique de cette feature est nouvelle (nouvelle table,
nouveau service, nouveaux endpoints) : chaque story porte donc ses tâches de
test, à écrire et faire échouer avant l'implémentation qui les fait passer.

**Organization**: Tasks are grouped by user story (spec.md) to enable
independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies). **Deux
  tâches ciblant le même fichier ne sont jamais toutes deux `[P]`**, même si
  leurs assertions sont indépendantes — écrire en parallèle sur un même
  fichier de test s'écrase, `/speckit-analyze` (I1) l'a relevé une première
  fois sur cette liste.
- **[Story]**: Which user story this task belongs to (US1..US5)
- Include exact file paths in descriptions

## Path Conventions

Web app existant : `backend/app/...`, `backend/tests/...`,
`frontend/app/...`, `frontend/components/...`, `frontend/lib/...` (voir
`plan.md` § Project Structure).

**Note de réallocation (par rapport à spec.md)** : l'« Independent Test » de
US1 exige déjà que l'auteur retrouve sa déclaration dans sa liste — la liste
personnelle (`GET /api/v1/volunteer-declarations`) est donc livrée dans US1,
pas différée à US5. US5 (P3) ne porte alors que la partie réellement nouvelle
à ce stade : la vue d'ensemble admin (tous membres, tous statuts).

**Amendements post-`/speckit-analyze`** : T012 et T055 sont des tâches
ajoutées (findings G1/G2) — elles décalent la numérotation par rapport à la
première génération. T057 corrige la garde de permission (finding U1). Les
marqueurs `[P]` sur fichier partagé ont été retirés (finding I1).

---

## Phase 1: Setup (Shared Infrastructure)

Aucune tâche : stack existante (FastAPI/SQLAlchemy/Alembic, Next.js/React
Query), aucune dépendance nouvelle — voir `plan.md` § Technical Context.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: le socle (modèle, migration, pouvoirs RBAC, schémas, repository)
que toutes les stories consomment. Bloquant pour US1 à US5.

**⚠️ CRITICAL**: aucune story ne peut commencer avant que cette phase soit verte.

- [X] T001 [P] Créer le modèle `VolunteerDeclaration` dans
      `backend/app/models/volunteer_declaration.py` (data-model.md) :
      `id`, `title` (String, NOT NULL), `description` (Text, NOT NULL),
      `beneficiary_user_id` (FK `users.id`, index, NOT NULL),
      `author_user_id` (FK `users.id`, NOT NULL), `status` (String, NOT NULL,
      default `"en_attente"`), `created_at` (DateTime, default `utcnow`).
      Patron `UserFeedback`/`VolunteerAction` : pas d'`ondelete` sur les FK.
- [X] T002 Ajouter l'import de `VolunteerDeclaration` dans
      `backend/app/models/__init__.py` (nécessaire pour qu'Alembic
      autogenerate détecte le nouveau modèle). Dépend de T001.
- [X] T003 Générer et relire la migration Alembic :
      `uv run alembic revision --autogenerate -m "add volunteer_declarations table"`
      dans `backend/migrations/versions/` — vérifier à la main les types de
      colonnes et l'absence de `ondelete` avant `uv run alembic upgrade head`.
      Dépend de T002.
- [X] T004 [P] Ajouter `FEATURE_VOLUNTEERING = "Déclarations de bénévolat"`,
      `P.BENEVOLAT_READ` (code `"benevolat:read"`) et `P.BENEVOLAT_MANAGE`
      (code `"benevolat:manage"`) dans `backend/app/core/permissions.py`,
      et les ajouter au tuple `ALL` (data-model.md § Permissions). Vérifier
      `uv run pytest backend/tests/test_permissions_catalogue.py` reste vert.
- [X] T005 [P] Créer les schémas Pydantic dans
      `backend/app/schemas/volunteer_declaration.py` :
      `VolunteerDeclarationCreate` (title, description — `min_length=1`,
      **aucun champ bénéficiaire** — c'est ce qui rend FR-003 structurel,
      cf. T012), `VolunteerDeclarationOut` (id, title, description, status,
      beneficiary_user_id, author_user_id, created_at),
      `AdminVolunteerDeclarationCreate` (title, description,
      beneficiary_user_id), `AdminVolunteerDeclarationOut` (hérite de
      `VolunteerDeclarationOut` + `beneficiary_display_name`,
      `beneficiary_email` — patron `AdminAthleteRead` vs `AthleteRead`).
      Contrats : `contracts/volunteer-declaration-api.md`.
- [X] T006 Écrire le test rouge du repository dans
      `backend/tests/test_repositories/test_volunteer_declaration_repository.py` :
      `create` (auteur == bénéficiaire et auteur != bénéficiaire),
      `get(id)`, `list_for_beneficiary(user_id)` (triée `created_at desc`),
      `list_all()` (tous membres/statuts), `delete(id)`, `set_status(id,
      status)`. Dépend de T001, T003 (schéma en base).
- [X] T007 Implémenter `backend/app/repositories/volunteer_declaration_repository.py`
      pour faire passer T006 — seule couche à construire des requêtes
      (Principe II). Dépend de T006.

**Checkpoint**: modèle + migration + pouvoirs + schémas + repository prêts —
les stories peuvent commencer.

---

## Phase 3: User Story 1 - Déclarer sa propre activité de bénévolat (Priority: P1) 🎯 MVP

**Goal**: un membre connecté crée une déclaration (titre + description),
enregistrée « en attente », et la retrouve dans sa liste personnelle.

**Independent Test**: `POST /api/v1/volunteer-declarations` puis
`GET /api/v1/volunteer-declarations` en session membre standard — la
déclaration apparaît, statut `"en_attente"`.

### Tests for User Story 1

- [X] T008 [US1] Red test : `POST /api/v1/volunteer-declarations` crée une
      déclaration `status="en_attente"`,
      `beneficiary_user_id == author_user_id == current_user.id` — dans
      `backend/tests/test_api/test_volunteer_declarations_api.py` (nouveau
      fichier).
- [X] T009 [US1] Red test : titre ou description vide → `422`, aucune
      ligne créée (FR-002) — même fichier.
- [X] T010 [US1] Red test : `GET /api/v1/volunteer-declarations` ne
      retourne que les déclarations du membre connecté, triées de la plus
      récente à la plus ancienne — même fichier.
- [X] T011 [US1] Red test : les deux routes rendent `401` sans session
      valide (garde `current_user`) — même fichier.
- [X] T012 [US1] Red test (finding G1 de `/speckit-analyze`) : un
      `beneficiary_user_id` surnuméraire injecté dans le corps de
      `POST /api/v1/volunteer-declarations` est ignoré — la déclaration
      créée reste `beneficiary_user_id == author_user_id == current_user.id`
      (FR-003 : le schéma self-service n'expose aucun champ bénéficiaire,
      ce test verrouille que rien ne le fait remonter par accident) — même
      fichier.

  *(T008-T012 partagent le même fichier de test : aucune marquée `[P]`.)*

### Implementation for User Story 1

- [X] T013 [US1] Implémenter `create_self(db, *, user_id, title, description)`
      et `list_for_self(db, *, user_id)` dans
      `backend/app/services/volunteer_declaration_service.py` (nouveau
      fichier). Dépend de T007.
- [X] T014 [US1] Créer `backend/app/api/v1/volunteer_declarations.py` :
      `POST /volunteer-declarations` et `GET /volunteer-declarations`, garde
      `current_user` (`app/api/deps.py`). Dépend de T013 ; fait passer
      T008-T012.
- [X] T015 [US1] Enregistrer le router dans `backend/app/api/v1/router.py`
      (import + `include_router`). Dépend de T014.
- [X] T016 [P] [US1] Ajouter le type `VolunteerDeclaration` et les appels
      `createVolunteerDeclaration`/`listMyVolunteerDeclarations` dans
      `frontend/lib/types.ts` et `frontend/lib/api/client.ts`.
- [X] T017 [US1] Créer `frontend/lib/queries/volunteer-declarations.ts` —
      hooks React Query `useCreateVolunteerDeclaration`,
      `useMyVolunteerDeclarations` (invalidation croisée à la création).
      Dépend de T016.
- [X] T018 [P] [US1] Créer
      `frontend/components/benevolat/VolunteerDeclarationForm.tsx` — champs
      titre/description, messages de validation en français, soumission via
      `useCreateVolunteerDeclaration`.
- [X] T019 [P] [US1] Créer
      `frontend/components/benevolat/VolunteerDeclarationList.tsx` — liste
      des déclarations du membre connecté, pastille de statut (« En attente
      de validation » / « Validée »), état vide invitant à en créer une.
- [X] T020 [US1] Créer
      `frontend/app/(public_restricted)/benevolat/page.tsx` — assemble
      `VolunteerDeclarationForm` + `VolunteerDeclarationList`. Utiliser
      `useSession()` (`frontend/lib/queries/auth.ts`, patron `UserMenu.tsx`)
      pour distinguer connecté/anonyme : la garde `(public_restricted)`
      (mot de passe partagé du site) n'implique **pas** une session
      individuelle — un visiteur ayant passé le mot de passe du site peut
      rester anonyme côté identité. Sans session, afficher une invite à se
      connecter (« Se connecter » → `/login`, patron `UserMenu.tsx`), pas le
      formulaire. Dépend de T017, T018, T019.
- [X] T021 [P] [US1] Test frontend
      `frontend/components/benevolat/VolunteerDeclarationForm.test.tsx` —
      refus des champs vides, soumission appelle le hook de création.
- [X] T022 [P] [US1] Test frontend
      `frontend/components/benevolat/VolunteerDeclarationList.test.tsx` —
      rendu des déclarations avec pastille de statut, état vide.

**Checkpoint**: US1 fonctionnelle et testable seule (MVP).

---

## Phase 4: User Story 2 - Un admin déclare pour n'importe quel membre, validée d'office (Priority: P2)

**Goal**: un admin (`benevolat:manage`) crée une déclaration pour lui-même ou
un tiers, enregistrée directement « validée ».

**Independent Test**: `POST /admin/volunteer-declarations` en session admin
avec `benevolat:manage` → `201`, `status="validee"` immédiatement.

### Tests for User Story 2

- [X] T023 [US2] Red test : `POST /admin/volunteer-declarations` (avec
      `benevolat:manage`) crée une déclaration `status="validee"` pour le
      `beneficiary_user_id` choisi — dans
      `backend/tests/test_api/test_admin_volunteer_declarations_api.py`
      (nouveau fichier).
- [X] T024 [US2] Red test : même route sans `benevolat:manage` → `403`
      (couvre FR-003 : un membre standard n'a structurellement pas accès à
      cette route pour déclarer au nom d'un tiers) — même fichier.
- [X] T025 [US2] Red test : `beneficiary_user_id` inconnu → `404` — même
      fichier.
- [X] T026 [US2] Red test : une ligne `AdminActionLog`
      (`action="volunteer_declaration.create_for_other"`,
      `entity_type="volunteer_declaration"`) est créée — même fichier.

  *(T023-T026 partagent le même fichier de test : aucune marquée `[P]`.)*

### Implementation for User Story 2

- [X] T027 [US2] Ajouter `create_for_other(db, *, admin_user_id,
      beneficiary_user_id, title, description)` dans
      `backend/app/services/volunteer_declaration_service.py` — statut
      `"validee"` d'emblée, écrit `AdminActionLog` (patron
      `admin_actions.declare_volunteer_action`). Dépend de T007.
- [X] T028 [US2] Créer `backend/app/api/v1/admin_volunteer_declarations.py` :
      `POST /admin/volunteer-declarations`, garde
      `require_permission(P.BENEVOLAT_MANAGE)`. Dépend de T027 ; fait passer
      T023-T026.
- [X] T029 [US2] Enregistrer le router admin dans
      `backend/app/api/v1/router.py`. Dépend de T028.
- [X] T030 [P] [US2] Ajouter le type `AdminVolunteerDeclaration` et l'appel
      `adminCreateVolunteerDeclaration` dans `frontend/lib/types.ts` et
      `frontend/lib/api/client.ts`.
- [X] T031 [US2] Ajouter `useAdminCreateVolunteerDeclaration` dans
      `frontend/lib/queries/admin.ts` (réutiliser la liste des utilisateurs
      existante — `USERS_READ`, page `/admin/utilisateurs` — pour le
      sélecteur de bénéficiaire). Dépend de T030.
- [X] T032 [US2] Créer `frontend/app/admin/benevolat/page.tsx` (coquille) et
      le formulaire « Déclarer pour un membre » (sélecteur de bénéficiaire +
      titre + description). Dépend de T031.
- [X] T033 [P] [US2] Test frontend du formulaire de création pour un tiers
      (sélection du membre, soumission, statut affiché « Validée »).

**Checkpoint**: US1 + US2 fonctionnelles indépendamment.

---

## Phase 5: User Story 3 - Un admin valide ou rejette une déclaration en attente (Priority: P2)

**Goal**: un admin fait passer une auto-déclaration « en attente » à
« validée », ou la rejette en la supprimant.

**Independent Test**: `POST /admin/volunteer-declarations/{id}/validate` sur
une déclaration en attente → `status="validee"`.

### Tests for User Story 3

- [X] T034 [US3] Red test :
      `POST /admin/volunteer-declarations/{id}/validate` (avec
      `benevolat:manage`) fait passer une déclaration « en attente » à
      « validée » — `test_admin_volunteer_declarations_api.py`.
- [X] T035 [US3] Red test : rejouer sur une déclaration déjà « validée »
      → `200`, aucun changement (idempotent, edge case du spec) — même
      fichier.
- [X] T036 [US3] Red test : `id` inconnu → `404` ; sans
      `benevolat:manage` → `403` — même fichier.
- [X] T037 [US3] Red test : une ligne `AdminActionLog`
      (`action="volunteer_declaration.validate"`) est créée — même fichier.

  *(T034-T037 partagent le même fichier de test : aucune marquée `[P]`.)*

### Implementation for User Story 3

- [X] T038 [US3] Ajouter `validate(db, *, admin_user_id, declaration_id)`
      dans `volunteer_declaration_service.py` — idempotent, écrit
      `AdminActionLog`. Dépend de T007 (même fichier que T027, après T027).
- [X] T039 [US3] Ajouter
      `POST /admin/volunteer-declarations/{id}/validate` dans
      `admin_volunteer_declarations.py`, garde
      `require_permission(P.BENEVOLAT_MANAGE)`. Dépend de T028, T038 ; fait
      passer T034-T037.
- [X] T040 [US3] Créer
      `frontend/components/benevolat/AdminVolunteerDeclarationTable.tsx` —
      liste des déclarations « en attente » avec bouton « Valider »
      (patron `PendingProvidersTable`), et le hook de mutation associé dans
      `frontend/lib/queries/admin.ts`. Dépend de T031.
- [X] T041 [US3] Intégrer `AdminVolunteerDeclarationTable` dans
      `frontend/app/admin/benevolat/page.tsx`. Dépend de T032, T040.
- [X] T042 [P] [US3] Test frontend de l'action « Valider » sur
      `AdminVolunteerDeclarationTable`.

**Checkpoint**: US1 + US2 + US3 fonctionnelles indépendamment.

---

## Phase 6: User Story 4 - Supprimer une déclaration (Priority: P3)

**Goal**: l'auteur d'une déclaration (en attente ou validée) la supprime ;
un admin peut supprimer celle de n'importe quel membre.

**Independent Test**: `DELETE /api/v1/volunteer-declarations/{id}` par
l'auteur → `204`, disparaît de sa liste.

### Tests for User Story 4

- [X] T043 [US4] Red test : `DELETE /api/v1/volunteer-declarations/{id}`
      par son auteur supprime la déclaration (`204`), quel que soit son
      statut — `test_volunteer_declarations_api.py`.
- [X] T044 [US4] Red test : même route par un membre standard qui n'en
      est pas l'auteur → `404` (pas de fuite d'existence, FR-007) — même
      fichier.

  *(T043-T044 partagent `test_volunteer_declarations_api.py` : aucune
  marquée `[P]`.)*

- [X] T045 [US4] Red test :
      `DELETE /admin/volunteer-declarations/{id}` (avec `benevolat:manage`)
      supprime la déclaration de n'importe quel membre (`204`) + ligne
      `AdminActionLog` (`action="volunteer_declaration.delete"`) —
      `test_admin_volunteer_declarations_api.py`.
- [X] T046 [US4] Red test : suppression admin d'un `id` inconnu → `404` ;
      sans `benevolat:manage` → `403` — même fichier.

  *(T045-T046 partagent `test_admin_volunteer_declarations_api.py` : aucune
  marquée `[P]`.)*

### Implementation for User Story 4

- [X] T047 [US4] Ajouter `delete_self(db, *, user_id, declaration_id)` et
      `delete_any(db, *, admin_user_id, declaration_id)` dans
      `volunteer_declaration_service.py` (patron FR-008 : `DELETE` réel, pas
      de soft-delete). Dépend de T007.
- [X] T048 [US4] Ajouter `DELETE /volunteer-declarations/{id}` dans
      `volunteer_declarations.py`. Dépend de T014, T047 ; fait passer
      T043-T044.
- [X] T049 [US4] Ajouter `DELETE /admin/volunteer-declarations/{id}` dans
      `admin_volunteer_declarations.py`. Dépend de T028, T047 ; fait passer
      T045-T046.
- [X] T050 [P] [US4] Ajouter le bouton de suppression (avec confirmation) et
      son hook de mutation dans
      `frontend/components/benevolat/VolunteerDeclarationList.tsx`.
- [X] T051 [P] [US4] Ajouter le bouton de suppression et son hook de
      mutation dans `AdminVolunteerDeclarationTable.tsx`. Dépend de T040.
- [X] T052 [P] [US4] Tests frontend des deux interactions de suppression.

**Checkpoint**: US1 à US4 fonctionnelles indépendamment.

---

## Phase 7: User Story 5 - Consulter les déclarations, vue d'ensemble admin (Priority: P3)

**Goal**: un admin dispose d'une vue d'ensemble sur les déclarations de tous
les membres, tous statuts confondus, avec l'identité du bénéficiaire (la
consultation personnelle d'US1 couvre déjà le cas membre standard — voir
Note de réallocation en tête de fichier).

**Independent Test**: `GET /admin/volunteer-declarations` en session admin
avec `benevolat:read` → toutes les déclarations, tous membres, tous statuts.

### Tests for User Story 5

- [X] T053 [US5] Red test : `GET /admin/volunteer-declarations` (avec
      `benevolat:read`) retourne les déclarations de tous les membres et
      tous statuts, avec l'identité du bénéficiaire —
      `test_admin_volunteer_declarations_api.py`.
- [X] T054 [US5] Red test : sans `benevolat:read` → `403` — même fichier.
      **Ne pas tester qu'un titulaire de `benevolat:manage` seul passe** :
      finding U1 de `/speckit-analyze`, confirmé sur `admin_feedback.py`
      (`GET` exige `FEEDBACK_READ` seul, `PATCH` exige `FEEDBACK_MANAGE`
      seul, aucune inclusion entre les deux) — un rôle qui doit à la fois
      valider et consulter la vue d'ensemble se compose avec **les deux**
      codes, comme n'importe quel rôle admin existant du catalogue.
- [X] T055 [US5] Red test (finding G2 de `/speckit-analyze`) : une
      déclaration supprimée (via T048 ou T049, US4) n'apparaît plus dans
      `GET /admin/volunteer-declarations` (FR-008, recoupement avec US4) —
      même fichier.

  *(T053-T055 partagent `test_admin_volunteer_declarations_api.py` : aucune
  marquée `[P]`.)*

### Implementation for User Story 5

- [X] T056 [US5] Ajouter `list_all(db)` dans
      `volunteer_declaration_service.py`, résolvant l'affichage du
      bénéficiaire (`display_name`/`email`). Dépend de T007.
- [X] T057 [US5] Ajouter `GET /admin/volunteer-declarations` dans
      `admin_volunteer_declarations.py`, garde
      `require_permission(P.BENEVOLAT_READ)` **seul** — correction du
      finding U1 : pas de garde composée, pas d'inclusion implicite de
      `benevolat:manage`. Dépend de T028, T056 ; fait passer T053-T055.
- [X] T058 [US5] Étendre `AdminVolunteerDeclarationTable.tsx` pour afficher
      tous les statuts (pas seulement « en attente ») et la colonne
      bénéficiaire. Dépend de T040.
- [X] T059 [P] [US5] Mettre à jour le test frontend de
      `AdminVolunteerDeclarationTable` pour la vue d'ensemble (tous
      statuts, colonne bénéficiaire).

**Checkpoint**: les 5 user stories sont fonctionnelles indépendamment.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T060 [P] Exécuter `uv run pytest -m "not integration"` (suite backend
      complète) et corriger toute régression.
- [X] T061 [P] Exécuter `npm test` (suite frontend complète) et corriger
      toute régression.
- [X] T062 Dérouler manuellement les 5 scénarios de `quickstart.md` sur
      `uv run python scripts/dev_server.py` + `npm run dev`.
- [X] T063 [P] `uv run ruff check backend` et `npm run lint` (frontend).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: aucune tâche.
- **Foundational (Phase 2)**: bloque toutes les user stories (T001-T007).
- **User Stories (Phase 3-7)**: dépendent toutes de Phase 2. Priorité
  d'exécution recommandée : P1 (US1) → P2 (US2, US3) → P3 (US4, US5) — mais
  US2/US3 sont indépendantes entre elles, de même US4/US5.
- **Polish (Phase 8)**: dépend des stories retenues pour cette itération.

### User Story Dependencies

- **US1 (P1)**: après Phase 2 uniquement. Aucune dépendance aux autres
  stories.
- **US2 (P2)**: après Phase 2. Indépendante d'US1 côté backend ; partage
  `admin/benevolat/page.tsx` avec US3 (coquille créée en US2, complétée en
  US3).
- **US3 (P2)**: après Phase 2. Modifie le même fichier de service qu'US2
  (`volunteer_declaration_service.py`) — tâches T038/T039 séquentielles
  après T027/T028, pas `[P]`.
- **US4 (P3)**: après Phase 2. Modifie les mêmes fichiers de routers qu'US1
  (self) et US2/US3 (admin) — tâches séquentielles sur ces fichiers.
- **US5 (P3)**: après Phase 2. Étend `AdminVolunteerDeclarationTable.tsx`
  créé en US3 — séquentiel sur ce fichier.

### Parallel Opportunities

- T001, T004, T005 (Phase 2) : fichiers distincts, en parallèle.
- Aucune tâche de test partageant un fichier n'est marquée `[P]` (finding
  I1) — les tâches de test d'une même story s'exécutent dans l'ordre au sein
  de leur fichier ; seules les tâches touchant des fichiers distincts (ex.
  T016 vs T018/T019, ou T050 vs T051) restent `[P]`.
- US2 et US3 peuvent être menées par deux personnes en parallèle après
  Phase 2 (fichiers de test distincts ; le service partagé se règle par
  rebase, pas par conflit fonctionnel).
- US4 et US5 de même, une fois US1/US2/US3 posées.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 (rien à faire) → Phase 2 (Foundational) → Phase 3 (US1).
2. **STOP and VALIDATE** : un membre déclare et retrouve sa déclaration
   « en attente ».
3. Démo possible à ce stade — la validation admin n'existe pas encore, mais
   la trace existe et est visible à son auteur (spec.md, Why this priority).

### Incremental Delivery

1. Foundational → US1 (MVP) → US2 → US3 (workflow de validation complet) →
   US4 (suppression étendue) → US5 (vue d'ensemble admin).
2. Chaque story ajoute de la valeur sans casser les précédentes.
