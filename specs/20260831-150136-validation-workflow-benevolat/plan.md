# Implementation Plan: Workflow de validation admin des actions de bénévolat

**Branch**: `779-validation-workflow-benevolat` | **Date**: 2026-08-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/20260831-150136-validation-workflow-benevolat/spec.md`

## Summary

Donner enfin un sens au statut posé par #778 : un nouveau pouvoir
`athletes:volunteer_validate` permet à un admin habilité de consulter les
déclarations `VolunteerAction` en attente et de les accepter/refuser
(idempotent). `exists_for_athlete_season` (quota de saison) ne compte
désormais que les lignes `"validee"`. Aucune nouvelle table, aucune
nouvelle colonne — extension de code sur un schéma déjà en place.

## Technical Context

**Language/Version**: Python 3.13 (backend uniquement — aucun changement frontend dans cette sous-issue)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2

**Storage**: SQLite (dev) / PostgreSQL (prod) — aucune migration, `status` existe déjà (#778)

**Testing**: pytest (TDD non-réseau — Principe III)

**Target Platform**: web — backend Render

**Project Type**: web application (cette sous-issue ne touche que `backend/`)

**Performance Goals**: aucun objectif dédié — volume attendu faible (file d'attente d'un club)

**Constraints**: ne pas toucher `POST /admin/athletes/{athlete_id}/volunteer-actions` (#709, inchangé) ; ne pas réutiliser `benevolat:read`/`benevolat:manage` (#751, domaine indépendant) ; `exists_for_athlete_season` reste la seule fonction de lecture du quota (un seul appelant, grep vérifié)

**Scale/Scope**: 1 permission, 1 schéma de réponse, 2 fonctions repository (existantes) modifiée/ajoutées, 3 fonctions service, 1 router (3 routes) — pas de frontend

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Identifiants/endpoints en anglais, libellés de permission en français |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | Router mince, service orchestre + journalise, repository seul à requêter |
| III | TDD sans réseau (non-négociable) | ✅ | Tests repository/service/API en pytest, aucun réseau |
| IV | Contrats API et CLI stables | ✅ | Routes neuves, additives ; endpoint de création admin existant inchangé ; `season-quota` garde sa forme, seul le calcul interne change |
| V | Neutralité par défaut des paramètres transverses | N/A | Aucun paramètre `scope`/`federal_only`/`seasons` concerné |
| VI | Simplicité / YAGNI | ✅ | Une seule permission (pas de couple read/manage, research.md D2) ; modification de la fonction existante plutôt qu'une nouvelle (research.md D3) |

Aucune violation — Complexity Tracking vide.

## Project Structure

### Documentation (this feature)

```text
specs/20260831-150136-validation-workflow-benevolat/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── admin-volunteer-actions-api.md
└── tasks.md
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── core/permissions.py                        # MODIFIED — + ATHLETES_VOLUNTEER_VALIDATE
│   ├── schemas/volunteer_action.py                 # MODIFIED — + AdminVolunteerActionOut
│   ├── repositories/volunteer_action_repository.py # MODIFIED — exists_for_athlete_season filtre "validee" ; + list_pending(), get(), set_status()
│   ├── services/volunteer_action_service.py        # MODIFIED — + list_pending(), accept(), reject()
│   └── api/v1/
│       ├── admin_volunteer_actions.py              # NEW — GET pending, POST accept/reject
│       └── router.py                               # MODIFIED — enregistrement du nouveau router
└── tests/
    ├── test_repositories/test_volunteer_action_repository.py  # MODIFIED
    ├── test_services/test_volunteer_action_service.py         # MODIFIED
    ├── test_api/test_admin_volunteer_actions_api.py           # NEW
    └── test_auth/test_public_routes_still_open.py             # inchangé — nouvelles routes sous /admin/, couvertes par le préfixe
```

**Structure Decision**: Backend uniquement — aucune modification frontend
dans cette sous-issue (l'affichage de la file d'attente admin, s'il en
faut un, serait une extension future hors périmètre de #779).

## Complexity Tracking

*Aucune violation de la Constitution Check — table vide.*
