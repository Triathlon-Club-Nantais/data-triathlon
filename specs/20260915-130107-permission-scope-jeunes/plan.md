# Implementation Plan: Pouvoir « jeunes »

**Branch**: `866-permission-scope-jeunes` | **Date**: 2026-09-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/20260915-130107-permission-scope-jeunes/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Ajouter deux codes au catalogue de référence des pouvoirs
(`backend/app/core/permissions.py`) : `jeunes:read` et `jeunes:write`, sous
une nouvelle fonctionnalité « Jeunes ». Aucune route ni écran jeunes n'est
créé — l'écran existant de composition des rôles (`GET /admin/permissions`,
`PATCH` de composition) les expose et les attribue sans modification, car il
lit `permissions.grouped_by_feature()` / `permissions.ALL` génériquement.

Le seul point technique non trivial : le test de non-régression
`backend/tests/test_permissions_catalogue.py::test_chaque_pouvoir_du_catalogue_garde_au_moins_une_ressource`
exige, par parcours AST des routers, que chaque pouvoir catalogué garde au
moins une ressource. Comme aucune route jeunes n'existe encore (elle arrive
dans les sous-issues #867/#868/#869 de l'epic #863), ce test échouerait pour
les deux nouveaux codes. Approche retenue : ajouter au fichier de test une
liste explicite, nominative et commentée des pouvoirs dont la garde est en
attente (code → sous-issue qui la posera), lue par ce test pour les exempter
temporairement — jamais un `xfail`/`skip` global, jamais une garde factice
posée sur une ressource sans rapport.

## Technical Context

**Language/Version**: Python 3.13

**Primary Dependencies**: FastAPI (inchangé — aucune route touchée), SQLAlchemy 2.0 (inchangé — aucun modèle touché)

**Storage**: N/A — aucune migration, `roles`/`role_permissions`/`user_roles` existent déjà (#115)

**Testing**: pytest (`uv run pytest -m "not integration"`), méta-test AST existant (`test_permissions_catalogue.py`)

**Target Platform**: Backend Linux (Render)

**Project Type**: Web application (backend seul concerné par cette issue)

**Performance Goals**: N/A — catalogue statique en mémoire, aucun accès base ni réseau

**Constraints**: Aucune migration Alembic ; aucune route/écran jeunes (hors périmètre explicite de #866) ; suite de tests verte à l'issue de la PR

**Scale/Scope**: 2 constantes `Permission` + 1 constante `FEATURE_JEUNES` + entrée dans `ALL` ; 1 test de non-régression modifié pour documenter l'exemption temporaire

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Passage explicite des 6 principes de `.specify/memory/constitution.md` (v1.2.0).
Statuts autorisés : ✅ conforme / ⚠️ justifié (ligne à créer dans Complexity
Tracking) / N/A (le principe ne s'applique pas à cette feature).

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Labels/descriptions des `Permission` en français (visibles dans l'écran admin) ; codes, identifiants Python et docstrings techniques en anglais. |
| II | Architecture en couches (api → services → repositories → DB) | N/A | Aucune couche touchée : `core/permissions.py` reste sans session, sans état, sans I/O — la doctrine du module (cf. `backend/app/core/AGENTS.md`) est inchangée. |
| III | TDD sans réseau (non-négociable) | ✅ | Test rouge d'abord : un test unitaire vérifie que `jeunes:read`/`jeunes:write` sont dans `permissions.CODES` avant l'ajout ; le méta-test de garde est mis à jour dans la même tâche que l'ajout des codes, jamais après. |
| IV | Contrats API et CLI stables | ✅ | `GET /admin/permissions` est additif par construction (il énumère `permissions.ALL`) — précédent de chaque pouvoir déjà ajouté au catalogue (les 32 codes actuels), aucun champ retiré ni sémantique changée. |
| V | Neutralité par défaut des paramètres transverses | N/A | Aucun paramètre de lecture transverse (`scope`, `federal_only`, …) concerné. |
| VI | Simplicité / YAGNI | ✅ | Deux codes (`read`/`write`), pas un par sous-fonctionnalité (profils/calendrier/appel) — cf. Assumptions de `spec.md`. |

Un principe en ⚠️ doit être justifié dans « Complexity Tracking » ci-dessous
avec l'alternative rejetée et la raison. Un principe violé sans justification
bloque le passage à `/speckit-tasks`.

## Project Structure

### Documentation (this feature)

```text
specs/20260915-130107-permission-scope-jeunes/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

Pas de `contracts/` : aucune interface externe nouvelle — `GET
/admin/permissions` et le `PATCH` de composition d'un rôle existent déjà et
ne changent pas de forme, seul leur contenu énuméré s'enrichit (comportement
déjà couvert par les tests existants de ces routes).

### Source Code (repository root)

```text
backend/
├── app/
│   └── core/
│       └── permissions.py         # + FEATURE_JEUNES, P.JEUNES_READ, P.JEUNES_WRITE, entrées dans ALL
└── tests/
    ├── test_core/
    │   └── test_permissions.py    # existant — CODES_ATTENDUS étendu aux 2 nouveaux codes
    └── test_permissions_catalogue.py  # exemption documentée et temporaire pour jeunes:read / jeunes:write
```

**Structure Decision**: Projet web existant (backend FastAPI / frontend
Next.js) — cette issue ne touche que `backend/app/core/permissions.py` et ses
tests. Aucun fichier frontend, aucune migration, aucun router.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

Aucune ligne — la grille ci-dessus ne relève aucune violation non justifiée.
