# Tasks: Bouton de signalement (bug / feedback)

**Input**: Design documents from `specs/20260812-191428-bouton-signalement/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/feedback-api.md, quickstart.md

**Tests**: Le Principe III de la constitution (non-négociable) s'applique intégralement.
Chaque user story porte ses tâches de test **avant** ses tâches d'implémentation ;
elles doivent échouer avant que l'implémentation ne les fasse passer au vert.

**Organization**: Tâches groupées par user story (spec.md) pour une implémentation
et une validation indépendantes de chacune.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallélisable (fichiers différents, aucune dépendance non résolue)
- **[Story]**: US1 à US4, correspond aux priorités de spec.md (US1/US2 = P1, US3 = P2, US4 = P3)
- Chemins de fichiers exacts dans chaque description

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Réglages transverses nécessaires avant toute logique métier — aucune nouvelle dépendance (research.md §D1, §D3).

- [ ] T001 [P] Ajouter `feedback_rate_limit_max_per_window` et `feedback_rate_limit_window_seconds` dans `backend/app/core/config.py` (research.md §D1), aux côtés de `geocode_min_interval_seconds`
- [ ] T002 [P] Créer `frontend/lib/github.ts` exportant `GITHUB_REPOSITORY = "Triathlon-Club-Nantais/data-triathlon"`, sur le patron de `frontend/lib/club.ts` (research.md §D3)

**Checkpoint**: réglages en place, aucune story ne peut encore fonctionner.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Le socle que les quatre user stories partagent — table, schémas, montage de routeur.

**⚠️ CRITICAL**: aucune story ne démarre avant la fin de cette phase.

- [ ] T003 Créer le modèle `UserFeedback` dans `backend/app/models/user_feedback.py` (data-model.md : `type`, `title`, `body`, `page_url`, `user_agent`, `ip_address`, `user_id` FK nullable `ON DELETE SET NULL`, `status` défaut `"nouveau"`, `github_url`, `created_at`, index `(status, created_at)` et `(ip_address, created_at)`)
- [ ] T004 Générer la migration Alembic (`uv run alembic revision --autogenerate -m "add user_feedback table"` depuis `backend/`) puis relire manuellement le fichier généré sous `backend/alembic/versions/` (Constitution §Additional Constraints)
- [ ] T005 [P] Créer les schémas Pydantic `FeedbackCreate`, `FeedbackRead`, `FeedbackStatusUpdate`, `FeedbackGithubUrlUpdate` dans `backend/app/schemas/feedback.py` (contracts/feedback-api.md — `FeedbackRead` ne porte jamais `ip_address`, data-model.md §D4 ; `FeedbackCreate` porte `honeypot: str | None`)
- [ ] T006 Créer le squelette de routeur (`router = APIRouter(tags=["admin"])`, aucune route encore) dans `backend/app/api/v1/admin_feedback.py` et le monter dans `backend/app/api/v1/router.py`
- [ ] T021 Ajouter `FEEDBACK_READ` (libellé « Consulter les retours utilisateurs »), `FEEDBACK_MANAGE` (libellé « Instruire les retours utilisateurs ») et `FEATURE_FEEDBACK = "Retours utilisateurs"` dans `backend/app/core/permissions.py` (research.md §D5, patron `PENDING_PROVIDERS_READ`/`_HANDLE`) — libellés délibérément distincts de `PENDING_PROVIDERS_READ` (« Consulter les signalements ») pour ne pas dupliquer ce texte dans la grille de composition des rôles (`/speckit-analyze`, finding I2). *Déplacée depuis Phase 4 (US2) : requise par les gardes de T023 (US2), T033 (US3) et T041 (US4), donc structurellement bloquante pour trois stories et non une seule — `/speckit-analyze`, finding I1.*
- [ ] T048 Ajouter `optional_user()` dans `backend/app/api/deps.py`, à côté de `current_user` : appelle `session_service.resolve(db, token)` et rend `User | None` **sans** lever `NotAuthenticatedError` en l'absence de session — nécessaire pour capturer l'email de l'auteur connecté sur une route publique (FR-005) sans casser l'accès anonyme (FR-001), un cas que `current_user` seul ne couvre pas (`/speckit-analyze`, finding U1).

**Checkpoint**: socle prêt, les user stories peuvent démarrer.

---

## Phase 3: User Story 1 - Signaler un bug ou un retour depuis n'importe quelle page (Priority: P1) 🎯 MVP

**Goal**: un visiteur, connecté ou non, soumet un signalement complet depuis le bouton flottant public.

**Independent Test**: ouvrir une page publique sans session, soumettre le formulaire, vérifier en base que le signalement existe avec le statut `nouveau`, le contexte auto-joint, et aucune identité si non connecté.

### Tests for User Story 1

> **NOTE: écrire ces tests D'ABORD, vérifier qu'ils échouent avant l'implémentation** (Principe III, non-négociable).

- [ ] T007 [P] [US1] Test `feedback_repository.create` et `count_recent_by_ip` (fenêtre glissante, IP absente) dans `backend/tests/test_repositories/test_feedback_repository.py`
- [ ] T008 [P] [US1] Test `feedback_service.submit` : honeypot rempli → aucune persistance mais réponse de succès identique ; débit dépassé → refus ; `user_id` renseigné seulement si une session est fournie dans `backend/tests/test_services/test_feedback_service.py`
- [ ] T009 [P] [US1] Test API `POST /admin/feedback` : 201 sans authentification, 422 si titre/description vide ou trop long, 429 au-delà du seuil, honeypot silencieux (contracts/feedback-api.md) dans `backend/tests/test_api/test_admin_feedback_api.py`
- [ ] T010 [P] [US1] Test composant `FeedbackButton` : bouton visible, formulaire bloque la soumission si titre/description vides, confirmation affichée après envoi dans `frontend/components/tcn/FeedbackButton.test.tsx`

### Implementation for User Story 1

- [ ] T011 [US1] Implémenter `create` et `count_recent_by_ip` dans `backend/app/repositories/feedback_repository.py` (dépend de T003, T007)
- [ ] T012 [US1] Implémenter `feedback_service.submit` (honeypot, limitation de débit via les réglages T001, association `user_id` depuis la session SSO courante) dans `backend/app/services/feedback_service.py` (dépend de T008, T011)
- [ ] T013 [US1] Implémenter la route `POST /admin/feedback` dans `backend/app/api/v1/admin_feedback.py`, avec `user: User | None = Depends(optional_user)` pour renseigner `user_id` seulement si une session est présente (dépend de T005, T006, T009, T012, T048)
- [ ] T014 [P] [US1] Ajouter `submitFeedback` dans `frontend/lib/api/client.ts`
- [ ] T015 [US1] Implémenter `FeedbackButton` (bouton flottant + `ui/dialog` + formulaire titre/description/type + champ honeypot invisible) dans `frontend/components/tcn/FeedbackButton.tsx` (dépend de T010, T014)
- [ ] T016 [US1] Monter `FeedbackButton` dans `frontend/app/layout.tsx`

**Checkpoint**: US1 fonctionnelle et testable indépendamment — un signalement public arrive en base.

---

## Phase 4: User Story 2 - Consulter la liste des retours utilisateurs dans le panel admin (Priority: P1)

**Goal**: un administrateur habilité liste et trie les signalements dans `/admin/retours-utilisateurs`.

**Independent Test**: pré-remplir plusieurs signalements en base, ouvrir la section, vérifier l'affichage et le tri par date/type/statut ; vérifier le refus sans le pouvoir requis.

### Tests for User Story 2

- [ ] T017 [P] [US2] Test `feedback_repository.list_sorted` (tri par `created_at`, `type`, `status`, ordre asc/desc) dans `backend/tests/test_repositories/test_feedback_repository.py`
- [ ] T018 [P] [US2] Test API `GET /admin/feedback` : liste triée, 403 sans `feedback:read`, `ip_address` absent de la réponse dans `backend/tests/test_api/test_admin_feedback_api.py`
- [ ] T019 [P] [US2] Test composant `FeedbackTable` : colonnes date/type/titre/statut, changement de tri au clic d'en-tête dans `frontend/components/admin/FeedbackTable.test.tsx`
- [ ] T020 [P] [US2] Test page `frontend/app/admin/retours-utilisateurs/page.test.tsx` : rendu de la liste, garde d'accès (patron des autres pages `admin/*`)

### Implementation for User Story 2

- [ ] T022 [US2] Implémenter `list_sorted` dans `backend/app/repositories/feedback_repository.py` (dépend de T017)
- [ ] T023 [US2] Implémenter la route `GET /admin/feedback` (garde `require_permission(P.FEEDBACK_READ)`) dans `backend/app/api/v1/admin_feedback.py` (dépend de T018, T021, T022)
- [ ] T024 [P] [US2] Ajouter `listFeedback` dans `frontend/lib/api/client.ts` et la lecture correspondante dans `frontend/lib/queries/admin.ts` + clé dans `frontend/lib/queries/keys.ts`
- [ ] T025 [US2] Implémenter `FeedbackTable` (tri par date/type/statut) dans `frontend/components/admin/FeedbackTable.tsx` (dépend de T019, T024)
- [ ] T026 [US2] Implémenter `frontend/app/admin/retours-utilisateurs/page.tsx` (dépend de T020, T025)
- [ ] T027 [US2] Ajouter l'entrée « Retours utilisateurs » (permission `feedback:read`) dans `frontend/components/layout/nav.config.ts` (dépend de T021)

**Checkpoint**: US1 + US2 fonctionnelles ensemble — un signalement soumis publiquement est visible et triable côté admin.

---

## Phase 5: User Story 3 - Traiter un signalement depuis sa vue détail (Priority: P2)

**Goal**: un administrateur ouvre le détail complet d'un signalement et fait évoluer son statut.

**Independent Test**: ouvrir le détail d'un signalement existant (avec et sans email associé), vérifier l'affichage complet, changer le statut et vérifier la persistance et le reflet dans la liste.

### Tests for User Story 3

- [ ] T028 [P] [US3] Test `feedback_repository.get` et `update_status` (toutes les transitions autorisées dans les deux sens, data-model.md) dans `backend/tests/test_repositories/test_feedback_repository.py`
- [ ] T029 [P] [US3] Test API `GET /admin/feedback/{id}` : 404 si absent, email présent seulement si `user_id` renseigné, 403 sans `feedback:read` dans `backend/tests/test_api/test_admin_feedback_api.py`
- [ ] T030 [P] [US3] Test API `PATCH /admin/feedback/{id}` (champ `status`) : 422 si valeur hors des quatre statuts, 403 sans `feedback:manage`, champs non envoyés inchangés dans `backend/tests/test_api/test_admin_feedback_api.py`
- [ ] T031 [P] [US3] Test composant `FeedbackDetailDialog` : affichage titre/description/contexte/email conditionnel, sélecteur de statut déclenche la mutation dans `frontend/components/admin/FeedbackDetailDialog.test.tsx`

### Implementation for User Story 3

- [ ] T032 [US3] Implémenter `get` et `update_status` dans `backend/app/repositories/feedback_repository.py` (dépend de T028)
- [ ] T033 [US3] Implémenter les routes `GET /admin/feedback/{id}` (garde `FEEDBACK_READ`) et `PATCH /admin/feedback/{id}` pour le champ `status` (garde `FEEDBACK_MANAGE`) dans `backend/app/api/v1/admin_feedback.py` (dépend de T029, T030, T032)
- [ ] T034 [P] [US3] Ajouter `getFeedback` et `updateFeedbackStatus` dans `frontend/lib/api/client.ts` + mutation dans `frontend/lib/queries/admin.ts` (invalidation de la clé liste, `frontend/lib/queries/keys.ts`)
- [ ] T035 [US3] Implémenter `FeedbackDetailDialog` (vue détail + sélecteur de statut) dans `frontend/components/admin/FeedbackDetailDialog.tsx` (dépend de T031, T034)
- [ ] T036 [US3] Ouvrir `FeedbackDetailDialog` au clic sur une ligne de `FeedbackTable` dans `frontend/components/admin/FeedbackTable.tsx` (dépend de T025, T035)

**Checkpoint**: US1 + US2 + US3 fonctionnelles ensemble — cycle complet signaler → consulter → traiter.

---

## Phase 6: User Story 4 - Pré-remplir une création d'issue/discussion GitHub (Priority: P3)

**Goal**: depuis la vue détail, générer un lien de création d'issue GitHub pré-rempli et enregistrer l'URL obtenue en retour.

**Independent Test**: ouvrir un signalement, cliquer sur « Promouvoir », vérifier que le lien généré pointe vers une création d'issue avec titre/description repris ; coller une URL et vérifier sa persistance.

### Tests for User Story 4

- [ ] T037 [P] [US4] Test `feedback_repository.set_github_url` dans `backend/tests/test_repositories/test_feedback_repository.py`
- [ ] T038 [P] [US4] Test API `PATCH /admin/feedback/{id}` (champ `github_url`) : 422 si URL invalide, 403 sans `feedback:manage`, persistance dans `backend/tests/test_api/test_admin_feedback_api.py`
- [ ] T039 [P] [US4] Test de construction du lien de promotion (titre et corps correctement encodés en paramètres de requête, dépôt issu de `GITHUB_REPOSITORY`, aucun appel réseau déclenché) dans `frontend/components/admin/FeedbackDetailDialog.test.tsx`

### Implementation for User Story 4

- [ ] T040 [US4] Implémenter `set_github_url` dans `backend/app/repositories/feedback_repository.py` (dépend de T037)
- [ ] T041 [US4] Étendre la route `PATCH /admin/feedback/{id}` pour accepter le champ `github_url` (garde `FEEDBACK_MANAGE`) dans `backend/app/api/v1/admin_feedback.py` (dépend de T038, T040)
- [ ] T042 [P] [US4] Ajouter `updateFeedbackGithubUrl` dans `frontend/lib/api/client.ts` + mutation dans `frontend/lib/queries/admin.ts`
- [ ] T043 [US4] Ajouter le bouton « Promouvoir en issue GitHub » (construction d'URL via `GITHUB_REPOSITORY`, ouverture dans un nouvel onglet) et le champ de saisie de l'URL de retour dans `frontend/components/admin/FeedbackDetailDialog.tsx` (dépend de T039, T042)

**Checkpoint**: les quatre user stories fonctionnent, indépendamment et ensemble.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: vérifications transverses, aucune nouvelle capacité métier.

- [ ] T044 [P] Exécuter `uv run ruff check .` depuis `backend/` et corriger les écarts
- [ ] T045 [P] Exécuter `npm run lint` depuis `frontend/` et corriger les écarts
- [ ] T046 Dérouler `quickstart.md` de bout en bout (les 6 scénarios) sur un environnement de dev local
- [ ] T047 Vérifier que `uv run pytest -m "not integration"` et `npm test` sont verts sur l'ensemble de la feature

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: aucune dépendance — démarre immédiatement
- **Foundational (Phase 2)**: dépend de Setup — bloque les quatre user stories
- **User Stories (Phase 3-6)**: dépendent toutes de Foundational
  - US1 et US2 (P1) peuvent démarrer en parallèle si l'équipe le permet ; sinon ordre de priorité
  - US3 (P2) dépend de l'existence des composants US2 (`FeedbackTable`, pour l'ouverture du détail) mais pas de sa complétion fonctionnelle — testable seul via l'API
  - US4 (P3) dépend de l'existence de `FeedbackDetailDialog` (US3)
- **Polish (Phase 7)**: dépend de toutes les stories livrées

### User Story Dependencies

- **US1 (P1)**: aucune dépendance sur une autre story — le formulaire public fonctionne seul
- **US2 (P1)**: aucune dépendance fonctionnelle sur US1 (peut être testée avec des données insérées directement en base), mais démontre sa valeur réelle une fois US1 livrée
- **US3 (P2)**: réutilise le composant `FeedbackTable` d'US2 pour l'ouverture du détail (T036) ; ses routes API sont indépendamment testables sans US2
- **US4 (P3)**: étend `FeedbackDetailDialog` d'US3 ; sans elle, aucune UI pour l'exposer, mais la route `PATCH .../github_url` reste testable seule

### Within Each User Story

- Tests écrits et rouges avant l'implémentation (Principe III)
- Repository avant service avant route (backend)
- Route avant client API avant composant (frontend)
- Story complète avant de passer à la priorité suivante

### Parallel Opportunities

- T001 et T002 (Setup) en parallèle
- T005 (schémas) en parallèle du reste de Foundational une fois T003 posé
- Toutes les tâches de test marquées [P] d'une même story en parallèle
- US1 et US2 peuvent être développées en parallèle par deux personnes une fois Foundational terminé

---

## Parallel Example: User Story 1

```bash
# Tests US1 en parallèle :
Task: "Test feedback_repository.create et count_recent_by_ip dans backend/tests/test_repositories/test_feedback_repository.py"
Task: "Test feedback_service.submit (honeypot, rate-limit, user_id) dans backend/tests/test_services/test_feedback_service.py"
Task: "Test API POST /admin/feedback dans backend/tests/test_api/test_admin_feedback_api.py"
Task: "Test composant FeedbackButton dans frontend/components/tcn/FeedbackButton.test.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 seule)

1. Setup + Foundational (T001-T006)
2. User Story 1 (T007-T016)
3. **Arrêt et validation** : un signalement soumis publiquement arrive en base — vérifiable en base ou via `GET /admin/feedback` une fois US2 posée, ou directement en base en attendant.

### Incremental Delivery

1. Setup + Foundational → socle prêt
2. US1 → signalements collectés (valeur pour les utilisateurs du site)
3. US2 → signalements consultables (valeur pour les admins, MVP complet du besoin premier)
4. US3 → cycle de traitement complet
5. US4 → confort de promotion GitHub, dernier maillon, explicitement le plus sacrifiable de l'issue

### Parallel Team Strategy

1. Setup + Foundational en équipe
2. Une fois Foundational posé : une personne sur US1 (formulaire public), une autre sur US2 (liste admin) — aucune dépendance croisée avant T036
3. US3 puis US4 enchaînent une fois `FeedbackTable` (US2) disponible

---

## Notes

- [P] = fichiers différents, aucune dépendance non résolue
- Le label de story trace chaque tâche jusqu'à spec.md
- Vérifier que chaque test échoue avant d'implémenter (Principe III)
- Aucune ligne de Complexity Tracking à couvrir (plan.md) : pas de dérogation de test à justifier
