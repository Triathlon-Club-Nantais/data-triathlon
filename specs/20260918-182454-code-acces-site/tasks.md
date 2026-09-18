---

description: "Task list for feature implementation"
---

# Tasks: Code d'accès du site : affichage en clair, reword, validité 3 mois

**Input**: Design documents from `specs/20260918-182454-code-acces-site/`

**Prerequisites**: plan.md, spec.md, research.md, quickstart.md

**Tests**: Le Principe III de la constitution v1.2.0 (`.specify/memory/constitution.md`) est **non-négociable** — TDD sans réseau. Chaque user story ci-dessous a ses tâches de test écrites et rouges avant l'implémentation.

**Organization**: Tâches groupées par user story (spec.md) pour une implémentation et une validation indépendantes de chacune.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: peut s'exécuter en parallèle (fichiers différents, aucune dépendance)
- **[Story]**: user story concernée (US1, US2, US3)

## Phase 1: Setup

*Aucune tâche* — l'écran `/acces`, le composant `SiteAccessGate.tsx` et la constante de configuration existent déjà (#509) ; aucune initialisation de projet, dépendance ou outillage supplémentaire n'est nécessaire.

---

## Phase 2: Foundational (Blocking Prerequisites)

*Aucune tâche* — les trois user stories ci-dessous sont indépendantes entre elles et ne partagent aucun préalable bloquant (fichiers, modèles ou services différents).

---

## Phase 3: User Story 1 - Voir le code d'accès saisi en clair (Priority: P1) 🎯 MVP

**Goal**: le champ de saisie du code d'accès sur `/acces` affiche chaque caractère en clair, jamais masqué.

**Independent Test**: ouvrir `/acces`, saisir des caractères dans le champ, vérifier qu'ils restent visibles (pas de points noirs) — indépendant des deux autres stories.

### Tests for User Story 1

> **Écrire ce test D'ABORD, vérifier qu'il ÉCHOUE avant l'implémentation** (Principe III).

- [ ] T001 [P] [US1] Dans `frontend/components/site-access/SiteAccessGate.test.tsx`, ajouter une assertion vérifiant que l'input `id="site-password"` a l'attribut `type="text"` (et non `type="password"`).

### Implementation for User Story 1

- [ ] T002 [US1] Dans `frontend/components/site-access/SiteAccessGate.tsx`, changer `type="password"` en `type="text"` sur le champ de saisie du code d'accès.

**Checkpoint**: User Story 1 fonctionnelle et testable indépendamment (T001 passe au vert).

---

## Phase 4: User Story 2 - Bénéficier d'une session valable 3 mois (Priority: P2)

**Goal**: la session ouverte après validation du code d'accès reste valide 90 jours au lieu de 7.

**Independent Test**: valider le code d'accès, inspecter le `max_age` du cookie de session posé par le serveur — indépendant des deux autres stories.

### Tests for User Story 2

> **Écrire ce test D'ABORD, vérifier qu'il ÉCHOUE avant l'implémentation** (Principe III).

- [ ] T003 [P] [US2] Dans `backend/tests/test_api/test_site_access_api.py::test_ouvre_une_session_avec_le_bon_mot_de_passe`, ajouter une assertion vérifiant que le cookie de session posé par `POST /site-access/session` a un `max_age` de `90 * 24 * 60 * 60` secondes (et non `7 * 24 * 60 * 60`) — parser `reponse.headers["set-cookie"]` si le cookie jar du `TestClient` n'expose pas `Max-Age` directement.

### Implementation for User Story 2

- [ ] T004 [US2] Dans `backend/app/core/config.py`, changer `site_access_session_ttl_days: int = 7` en `site_access_session_ttl_days: int = 90`.
- [ ] T005 [P] [US2] Dans `docs/ci-cd.md`, mettre à jour la ligne documentant `SITE_ACCESS_SESSION_TTL_DAYS` : "défaut (7 j)" → "défaut (90 j)".

**Checkpoint**: User Stories 1 ET 2 fonctionnelles indépendamment (T001 et T003 passent au vert).

---

## Phase 5: User Story 3 - Comprendre qu'il s'agit d'un code d'accès partagé (Priority: P3)

**Goal**: tous les textes visibles de l'écran `/acces` (titre, libellé, aide, message d'erreur) emploient "code d'accès" plutôt que "mot de passe".

**Independent Test**: ouvrir `/acces`, lire titre/libellé/aide, puis saisir un code incorrect et lire le message d'erreur — indépendant des deux autres stories.

### Tests for User Story 3

> **Écrire ces tests D'ABORD, vérifier qu'ils ÉCHOUENT avant l'implémentation** (Principe III).

- [ ] T006 [P] [US3] Dans `frontend/components/site-access/SiteAccessGate.test.tsx`, remplacer les sélecteurs/assertions `/mot de passe/i` (label, aide) par `/code d'accès/i`.
- [ ] T007 [P] [US3] Dans `backend/tests/test_api/test_site_access_api.py::test_refuse_un_mauvais_mot_de_passe`, ajouter une assertion sur le message d'erreur : `reponse.json()["detail"] == "Code d'accès incorrect."`. **Attention** : `backend/tests/test_auth/test_site_access_gate.py:99` contient un littéral identique ("Mot de passe incorrect.") mais teste le flux **bénévoles** (`/api/v1/benevoles/session`, hors périmètre, FR-005) — ne pas le modifier.

### Implementation for User Story 3

- [ ] T008 [US3] Dans `frontend/components/site-access/SiteAccessGate.tsx`, reformuler le titre, le label du champ et le texte d'aide ("Le mot de passe vous a été communiqué par le club." → "Le code d'accès vous a été communiqué par le club.") — sans toucher `id="site-password"` ni au nom des props/variables.
- [ ] T009 [US3] Dans `backend/app/api/v1/site_access.py`, reformuler le message d'erreur levé en cas de code incorrect ("Mot de passe incorrect." → "Code d'accès incorrect.") — sans toucher au nom du champ JSON `password`.

**Checkpoint**: les trois user stories sont fonctionnelles et testables indépendamment (T001, T003, T006, T007 passent tous au vert).

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T010 [P] Dérouler manuellement les 3 scénarios de `quickstart.md` en environnement de dev (dont la vérification de l'écran `/admin/acces`, hors périmètre, non régressé).
- [ ] T011 Lancer `uv run pytest -m "not integration"` (depuis `backend/`) et `npm test` (depuis `frontend/`) — les deux suites doivent être vertes.
- [ ] T012 Lancer `uv run ruff check .` (depuis `backend/`) et `npm run lint` (depuis `frontend/`).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup / Foundational** : aucune tâche, rien ne bloque le démarrage des user stories.
- **User Stories (Phase 3-5)** : indépendantes entre elles, exécutables dans n'importe quel ordre ou en parallèle.
- **Polish (Phase 6)** : dépend des trois user stories terminées.

### Within Each User Story

- Le test de la story est écrit et rouge avant sa tâche d'implémentation correspondante (T001→T002, T003→T004, T006/T007→T008/T009).

### Parallel Opportunities

- T001, T003, T006, T007 (tests de stories différentes) peuvent s'écrire en parallèle.
- T004 et T005 (US2) touchent des fichiers différents (config vs doc) et peuvent s'exécuter en parallèle une fois T003 rouge.
- T008 et T009 (US3) touchent des fichiers différents (frontend vs backend) et peuvent s'exécuter en parallèle une fois T006/T007 rouges.

---

## Implementation Strategy

### MVP First (User Story 1 seule)

1. T001 (test rouge) → T002 (implémentation) → vérifier T001 vert.
2. Valider manuellement le scénario 1 de `quickstart.md`.

### Incremental Delivery

1. US1 (affichage en clair) → validation indépendante.
2. US2 (TTL 90 jours) → validation indépendante.
3. US3 (reword) → validation indépendante.
4. Polish (Phase 6) : suites complètes + lint + relecture manuelle des 3 scénarios.

## Notes

- Aucune tâche de migration Alembic : pas de changement de schéma DB.
- Aucune tâche touchant `SiteAccessConfig.tsx` (`/admin/acces`) ni `AccessGate.tsx` (bénévoles, #271) : hors périmètre assumé (voir spec.md, section Hors périmètre / Assumptions).
- Commit après chaque tâche ou groupe logique, conformément à la convention Conventional Commits du projet.
