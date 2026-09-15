# Tasks: Pouvoir « jeunes »

**Input**: Design documents from `specs/20260915-130107-permission-scope-jeunes/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Principe III (TDD sans réseau, non-négociable). Toutes les tâches
de test s'écrivent et échouent **avant** l'implémentation.

**Organization**: Une seule user story (P1) — le périmètre de #866 est le
catalogue de pouvoirs, pas de setup ni de socle transverse à part.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

Aucune tâche : aucune dépendance nouvelle, aucun projet à initialiser — le
catalogue existant (`backend/app/core/permissions.py`) et ses tests
(`backend/tests/test_core/test_permissions.py`,
`backend/tests/test_permissions_catalogue.py`) sont le seul périmètre.

## Phase 2: Foundational

Aucune tâche : rien ne bloque la user story unique.

---

## Phase 3: User Story 1 - Composer un rôle avec le pouvoir jeunes (Priority: P1) 🎯 MVP

**Goal**: Les codes `jeunes:read` et `jeunes:write` existent dans le
catalogue de référence, sont affichés en français, et attribuables à un rôle
via l'écran d'administration déjà en place — sans aucune route ni écran
jeunes.

**Independent Test**: `uv run python -c "from app.core import permissions; assert {'jeunes:read', 'jeunes:write'} <= {p.code for p in permissions.ALL}"` réussit ; `GET /admin/permissions` (via un test API existant) liste un groupe « Jeunes » avec les deux pouvoirs.

### Tests for User Story 1

> **NOTE: Écrire ces tests D'ABORD, vérifier qu'ils ÉCHOUENT avant l'implémentation.**

- [X] T001 [US1] Étendre `CODES_ATTENDUS` dans `backend/tests/test_core/test_permissions.py` avec `"jeunes:read"` et `"jeunes:write"` (commentaire mis à jour : « les deux codes de #866/epic #863 »), ce qui fait échouer `test_le_catalogue_expose_exactement_les_codes_du_contrat` tant que `permissions.py` n'est pas modifié.
- [X] T002 [US1] Documenter dans `backend/tests/test_permissions_catalogue.py` une liste nominative `GARDE_A_VENIR: dict[str, str]` (code → sous-issue qui posera la garde, ex. `"jeunes:read": "#867/#868 (epic #863)"`, `"jeunes:write": "#869 (epic #863)"`) et faire sauter (`pytest.skip`, pas `xfail` silencieux) `test_chaque_pouvoir_du_catalogue_garde_au_moins_une_ressource` pour les codes qui y figurent — comportement décrit dans `research.md` §Décision 2. Cette tâche seule ne change rien tant que T003 n'a pas ajouté les codes : elle prépare le filet.

### Implementation for User Story 1

- [X] T003 [US1] Dans `backend/app/core/permissions.py` : ajouter la constante `FEATURE_JEUNES = "Jeunes"` (regroupée avec les autres `FEATURE_*`, avec un commentaire si la portée du regroupement n'est pas évidente — cf. `FEATURE_GROUPS`), puis `P.JEUNES_READ` (`jeunes:read`, libellé « Consulter les jeunes », description couvrant profils + calendrier) et `P.JEUNES_WRITE` (`jeunes:write`, libellé « Encadrer les jeunes », description couvrant création/modification de profil, calendrier, appel, journal de bord), puis les deux entrées dans le tuple `ALL` (après `P.PAGES_PREVIEW`, dans l'ordre de déclaration).
- [X] T004 [US1] Lancer `uv run pytest tests/test_core/test_permissions.py tests/test_permissions_catalogue.py -v` (depuis `backend/`) et confirmer que T001 et T002 passent désormais au vert.

**Checkpoint**: `jeunes:read`/`jeunes:write` existent, sont affichés en
français, groupés sous « Jeunes », attribuables via `/admin/roles`, et la
suite de tests dédiée est verte.

---

## Phase 4: Polish & Cross-Cutting Concerns

- [X] T005 [P] Exécuter `uv run pytest -m "not integration"` (depuis `backend/`) et confirmer 100 % vert sur l'ensemble de la suite (pas seulement les fichiers de T004). **Résultat** : 4599 passed, 2 skipped, 1 failed — `test_config.py::test_cors_origins_defaut`, préexistant, sans rapport avec ce diff (`.env` de ce worktree, absent en CI ; confirmé par `git diff --stat` limité à `permissions.py` et aux deux fichiers de test du catalogue).
- [X] T006 [P] Exécuter `uv run ruff check .` (depuis `backend/`) et confirmer aucune erreur. **Résultat** : All checks passed!
- [X] T007 Dérouler `quickstart.md` manuellement (catalogue en Python + lecture de `GET /admin/permissions` si un serveur dev est disponible) et noter tout écart. **Résultat** : le catalogue expose `jeunes:read`/`jeunes:write` groupés sous « Jeunes » (vérifié via `permissions.grouped_by_feature()`, le code exact que sert la route) ; parcours SSO complet non rejoué (pas de session admin disponible en session agent), mais la route est couverte par les tests API existants, tous verts.

---

## Dependencies & Execution Order

- T001 et T002 sont indépendantes entre elles (fichiers différents) mais
  toutes deux précèdent T003 (TDD : rouge avant vert).
- T003 dépend de T001 et T002 (c'est l'implémentation qui les fait passer au
  vert).
- T004 dépend de T003.
- T005/T006/T007 dépendent de T004 (aucune n'a de sens tant que la user
  story n'est pas complète), et peuvent tourner en parallèle entre elles.

## Parallel Example: User Story 1

```bash
# T001 et T002 touchent deux fichiers de test différents : parallélisables.
Task: "Étendre CODES_ATTENDUS dans backend/tests/test_core/test_permissions.py"
Task: "Documenter GARDE_A_VENIR dans backend/tests/test_permissions_catalogue.py"
```

## Implementation Strategy

Une seule user story : Setup → Foundational → US1 → Polish, sans découpage
MVP supplémentaire (le MVP **est** la user story unique).
