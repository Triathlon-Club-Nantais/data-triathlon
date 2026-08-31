# Implementation Plan: Liste des actions de bénévolat validées sur la fiche athlète

**Branch**: `781-liste-actions-validees-fiche-athlete` | **Date**: 2026-08-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/20260831-152635-liste-actions-validees/spec.md`

## Summary

Expose, en lecture seule, les actions de bénévolat déjà « validées » d'un
athlète sur sa fiche publique — visible uniquement aux titulaires de
`athletes:volunteer_validate` (#779). Un nouvel endpoint
(`GET .../volunteer-actions/validated`) dans le router déjà gardé par ce
pouvoir, une fonction repository dédiée, et un composant frontend qui se
rend nul sans le pouvoir (#439).

## Technical Context

**Language/Version**: Python 3.13 (backend) + TypeScript strict / Next.js 16 (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Pydantic v2 ; TanStack Query, composants `tcn`

**Storage**: aucune migration — `VolunteerAction`/`status` existent déjà (#778/#779)

**Testing**: pytest (backend, TDD non-réseau) ; vitest (frontend)

**Target Platform**: web

**Project Type**: web application (backend + frontend, les deux touchés)

**Performance Goals**: aucun objectif dédié — volume par athlète faible

**Constraints**: ne pas dupliquer `AdminVolunteerActionOut` (#779) ; ne pas reproduire la duplication grille/cartes complète d'`EventsTable.tsx` (research.md D5) ; garde de visibilité identique au patron `SeasonValidationPanel.tsx`/`AthleteAdminPanel.tsx`

**Scale/Scope**: 1 route, 1 fonction repository, 1 fonction service, 1 type TS, 1 méthode `apiClient`, 1 hook de requête, 1 composant frontend, 1 point de montage sur la page profil

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Identifiants/endpoint en anglais, libellés UI en français |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | Route mince déléguant au service, seule la nouvelle fonction repository requête |
| III | TDD sans réseau (non-négociable) | ✅ | Tests repository/service/API/composant en pytest/vitest, aucun réseau |
| IV | Contrats API et CLI stables | ✅ | Route neuve, additive ; endpoints existants (#709, #779) inchangés |
| V | Neutralité par défaut des paramètres transverses | N/A | Aucun paramètre `scope`/`federal_only`/`seasons` concerné |
| VI | Simplicité / YAGNI | ✅ | Réutilise `AdminVolunteerActionOut` (research.md D3) ; pas de duplication grille/cartes non justifiée (research.md D5) ; pas de nouvelle permission (research.md D6) |

Aucune violation — Complexity Tracking vide.

## Project Structure

### Documentation (this feature)

```text
specs/20260831-152635-liste-actions-validees/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── athlete-volunteer-actions-api.md
└── tasks.md
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── repositories/volunteer_action_repository.py  # MODIFIED — + list_validated_for_athlete()
│   ├── services/volunteer_action_service.py         # MODIFIED — + list_validated_for_athlete()
│   └── api/v1/admin_volunteer_actions.py             # MODIFIED — + GET .../volunteer-actions/validated
└── tests/
    ├── test_repositories/test_volunteer_action_repository.py  # MODIFIED
    ├── test_services/test_volunteer_action_service.py         # MODIFIED
    └── test_api/test_admin_volunteer_actions_api.py           # MODIFIED

frontend/
├── lib/
│   ├── api/client.ts                    # MODIFIED — + listValidatedVolunteerActions
│   └── types.ts                         # MODIFIED — + AdminVolunteerActionOut
├── lib/queries/admin.ts                 # MODIFIED — + useValidatedVolunteerActions
├── components/athletes/
│   ├── VolunteerActionsList.tsx         # NEW
│   └── VolunteerActionsList.test.tsx    # NEW
└── app/(public_restricted)/athletes/[id]/page.tsx  # MODIFIED — montage après EventsTable
```

**Structure Decision**: Web application existante — backend et frontend
tous deux modifiés, structure inchangée. Aucun nouveau router ni nouvelle
page ; extension du router `admin_volunteer_actions.py` (#779) et de la
page profil athlète existante.

## Complexity Tracking

*Aucune violation de la Constitution Check — table vide.*
