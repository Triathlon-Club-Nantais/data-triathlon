# Tasks: Profil individuel jeune (#867)

**Input**: `spec.md`, `plan.md`, `research.md`, `data-model.md`,
`contracts/admin-profiles.md`, `quickstart.md` (specs/20260915-111701-profil-jeune/)

**Tests**: obligatoires (Principe III, TDD non-négociable). Chaque tâche de
code de production est précédée d'une tâche de test qui échoue d'abord.

## Phase 1: Foundational (bloquant — modèle de données partagé par toutes les US)

- [ ] T001 [P] Écrire les tests de `profile_repository` (échouent : le module
      n'existe pas) dans `backend/tests/test_repositories/test_profile_repository.py`
      — création, lecture par id, liste triée `last_name, first_name`, ajout
      d'entrée de journal, liste des entrées triée `entry_date desc, created_at desc`.
- [ ] T002 [P] Créer `PersonalProfile` dans `backend/app/models/personal_profile.py`
      (table `personal_profiles`, colonnes par `data-model.md`).
- [ ] T003 [P] Créer `ProfileLogEntry` dans `backend/app/models/profile_log_entry.py`
      (table `profile_log_entries`, colonnes par `data-model.md`, relation
      `PersonalProfile.log_entries` avec `delete-orphan`).
- [ ] T004 Enregistrer les deux modèles dans `backend/app/models/__init__.py`
      (import + `__all__`).
- [ ] T005 Générer la migration Alembic (`uv run alembic revision --autogenerate
      -m "add personal_profiles and profile_log_entries"` depuis `backend/`),
      relire la révision générée à la main, l'appliquer
      (`uv run alembic upgrade head`).
- [ ] T006 Créer `backend/app/repositories/profile_repository.py` (patron
      `group_repository.py`) : `get`, `list_all`, `create`, `update`,
      `add_log_entry`, `list_log_entries`. Fait passer T001.
- [ ] T007 [P] Créer `backend/app/schemas/profile.py` : `ProfileRead`,
      `ProfileDetailRead`, `ProfileCreate`, `ProfileUpdate`,
      `ProfileLogEntryRead`, `ProfileLogEntryCreate` (validation non-vide sur
      `text`, `first_name`, `last_name` — `data-model.md` §Validation).
- [ ] T008 Créer `backend/app/services/profile_service.py` (patron
      `services/auth/groups.py`) : `get_profile_or_404`, `profile_view`,
      `profile_detail_view`, `list_profiles`, `create_profile`,
      `update_profile`, `add_log_entry`.
- [ ] T009 Créer `backend/app/api/v1/admin_profiles.py` avec les 5 routes de
      `contracts/admin-profiles.md`, gardées par `require_permission(P.JEUNES_READ)`
      / `require_permission(P.JEUNES_WRITE)` (patron `admin_groups.py`).
- [ ] T010 Enregistrer `admin_profiles` dans `backend/app/api/v1/router.py`
      (import + boucle `require_site_access`, comme les autres routers `admin_*`).

**Checkpoint** : `uv run alembic upgrade head` applique proprement, T001 passe,
les 5 routes existent (visibles dans `/docs`). Aucune US n'est encore
utilisable de bout en bout côté HTTP tant que les tests d'API n'existent pas
(Phase 2).

---

## Phase 2: User Story 1 + 2 — Consulter la liste et le détail d'un profil (P1)

**Objectif** : `GET /admin/profiles` et `GET /admin/profiles/{id}` gardés par
`jeunes:read`, rendent respectivement la liste triée et le détail avec journal.

**Test d'indépendance** : avec un compte `jeunes:read` seul, lister et ouvrir
un profil créé directement en base (fixture de test) ; sans session, 401 ;
avec session sans le pouvoir, 403.

- [ ] T011 [P] [US1] Écrire les tests API de lecture (échouent) dans
      `backend/tests/test_auth/test_admin_profiles_api.py` : liste triée,
      détail avec `log_entries` triées desc, 404 sur id inconnu, 401 anonyme,
      403 sans `jeunes:read`, `jeunes:write` seul ne passe pas la lecture.
- [ ] T012 [US1] Faire passer T011 (ajustements des routes `GET` de
      `admin_profiles.py`/`profile_service.py` si nécessaire).
- [ ] T013 [US1] Retirer l'entrée `"jeunes:read"` de `GARDE_A_VENIR` dans
      `backend/tests/test_permissions_catalogue.py` — la garde existe désormais.
- [ ] T014 [US1] Lancer `uv run pytest -m "not integration"` et confirmer que
      `test_permissions_catalogue.py` et `test_public_routes_still_open.py`
      restent verts (nouvelle ressource classée sous `/admin/` gardée).

**Checkpoint** : liste + détail consultables via HTTP, garde 401/403 prouvée.

---

## Phase 3: User Story 3 — Créer et modifier un profil (P2)

**Objectif** : `POST`/`PATCH /admin/profiles/{id}` gardés par `jeunes:write`.

**Test d'indépendance** : avec un compte `jeunes:write`, créer un profil,
le relire par `GET`, modifier un champ, le relire à nouveau ; avec
`jeunes:read` seul, 403 sur les deux écritures.

- [ ] T015 [US3] Écrire les tests API d'écriture (échouent) dans
      `backend/tests/test_auth/test_admin_profiles_api.py` : création
      (champs minimaux, 201), 422 sur nom/prénom vide, modification partielle
      (PATCH), 404 sur modification d'un id inconnu, 401/403/`jeunes:read`-seul
      sur les deux routes (patron `WRITES`/paramétrage de `test_admin_groups_api.py`).
- [ ] T016 [US3] Faire passer T015 (`ProfileCreate`/`ProfileUpdate`,
      `create_profile`/`update_profile`, routes `POST`/`PATCH`).
- [ ] T017 [US3] Retirer l'entrée `"jeunes:write"` de `GARDE_A_VENIR` dans
      `backend/tests/test_permissions_catalogue.py`.

**Checkpoint** : un profil complet peut être créé et corrigé via HTTP.

---

## Phase 4: User Story 4 — Ajouter une entrée au journal de bord (P2)

**Objectif** : `POST /admin/profiles/{id}/log-entries` gardé par `jeunes:write`,
rend le détail complet à jour.

**Test d'indépendance** : sur un profil existant, ajouter une entrée avec un
texte, relire le détail et constater sa présence en tête d'historique ; texte
vide → 422 ; sans `jeunes:write`, 403.

- [ ] T018 [US4] Écrire les tests API du journal (échouent) dans
      `backend/tests/test_auth/test_admin_profiles_api.py` : ajout d'entrée
      (201, apparaît en tête), 422 texte vide, 404 profil inconnu, 401/403,
      plusieurs entrées restent toutes visibles (FR-006 — aucune n'écrase la
      précédente).
- [ ] T019 [US4] Faire passer T018 (`ProfileLogEntryCreate`, `add_log_entry`,
      route `POST .../log-entries`).

**Checkpoint** : le journal de bord est alimentable et conserve tout son
historique — les quatre user stories backend sont livrées.

---

## Phase 5: Frontend — écran mobile-first (couvre US1-US4 côté consultation/édition)

- [ ] T020 [P] Ajouter les types `Profile`, `ProfileDetail`, `ProfileLogEntry`
      dans `frontend/lib/types.ts` (patron `Group`/`GroupDetail`).
- [ ] T021 [P] Ajouter les clés `profiles()`/`profile(id)` dans
      `frontend/lib/queries/keys.ts`.
- [ ] T022 Ajouter les méthodes `listProfiles`, `getProfile`, `createProfile`,
      `updateProfile`, `addProfileLogEntry` dans `frontend/lib/api/client.ts`
      (patron des méthodes `*Group*`).
- [ ] T023 Ajouter les hooks `useProfiles`, `useProfile`, `useCreateProfile`,
      `useUpdateProfile`, `useAddProfileLogEntry` dans
      `frontend/lib/queries/admin.ts` (patron des hooks `*Group*`).
- [ ] T024 [P] Écrire les tests (échouent) de `ProfilesList` dans
      `frontend/components/admin/ProfilesList.test.tsx` : rendu de la liste en
      cartes, état vide, garde d'écriture (`jeunes:write`) sur le formulaire de
      création, état de chargement/erreur (patron `GroupsTable.test.tsx`).
- [ ] T025 Créer `frontend/components/admin/ProfilesList.tsx` (liste en cartes
      mobile-first — pas de double-arbre grille/cartes, cf. `research.md` D3)
      pour faire passer T024.
- [ ] T026 [P] Écrire les tests (échouent) de `ProfileDetail` dans
      `frontend/components/admin/ProfileDetail.test.tsx` : informations
      personnelles, historique du journal trié, formulaire d'ajout d'entrée
      gardé par `jeunes:write`, formulaire d'édition du profil gardé par
      `jeunes:write`.
- [ ] T027 Créer `frontend/components/admin/ProfileDetail.tsx` pour faire
      passer T026.
- [ ] T028 [P] Créer `frontend/app/admin/jeunes/page.tsx` (patron
      `app/admin/groupes/page.tsx` : `PageShell` + `PageHeader` + `ecran()` +
      `ProfilesList`).
- [ ] T029 [P] Créer `frontend/app/admin/jeunes/[id]/page.tsx` (`PageShell` +
      `ProfileDetail`, lit l'id depuis les `params`).
- [ ] T030 Ajouter l'entrée de navigation « Jeunes » (`id: "a-jeunes"`, `href:
      "/admin/jeunes"`, `permission: "jeunes:read"`, `description`) dans la
      section `admin` de `frontend/components/layout/nav.config.ts`.

**Checkpoint** : `/admin/jeunes` visible dans le rail pour un porteur de
`jeunes:read`, écran utilisable au clavier et sur un viewport 375px.

---

## Phase 6: Polish

- [ ] T031 `cd backend && uv run pytest -m "not integration"` — suite complète
      verte.
- [ ] T032 `cd backend && uv run ruff check .` — aucun avertissement sur les
      fichiers ajoutés.
- [ ] T033 `cd frontend && npm test` — suite complète verte.
- [ ] T034 `cd frontend && npm run lint` — aucun avertissement.
- [ ] T035 `cd frontend && npm run build` — build de production OK (TS strict,
      RSC).
- [ ] T036 Relire `quickstart.md` et vérifier chacune de ses étapes contre
      l'implémentation livrée.

## Dependencies

- Phase 1 (Foundational) bloque toutes les phases suivantes.
- Phase 2 (US1+US2, P1) est le MVP : livrable seule après Phase 1.
- Phase 3 (US3, P2) et Phase 4 (US4, P2) dépendent de Phase 1 seulement — elles
  peuvent s'exécuter dans n'importe quel ordre entre elles, mais T017 suppose
  T016 fait (la garde `jeunes:write` doit exister avant de retirer l'entrée).
- Phase 5 (frontend) dépend des Phases 2-4 (contrat API stabilisé).
- Phase 6 dépend de tout ce qui précède.

## Parallel Example

Après T010 (Foundational fait) : T011 (tests US1/US2), T015 (tests US3, une
fois T011 écrit puisqu'ils partagent le même fichier `test_admin_profiles_api.py`
— en pratique séquentiel sur ce fichier), et côté frontend T020/T021 (fichiers
distincts, aucune dépendance sur le backend) peuvent démarrer en parallèle.

## Implementation Strategy

**MVP** = Phase 1 + Phase 2 (US1+US2) : un profil consultable, créé
directement en base (amorçage manuel), suffit à prouver la valeur du
référencement demandé par #863. Phases 3-4 ajoutent l'édition ; Phase 5 rend
tout consultable/éditable sans passer par l'API brute.
