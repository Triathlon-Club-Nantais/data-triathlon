# Implementation Plan: Formulaire public de déclaration de bénévolat

**Branch**: `778-formulaire-benevolat` | **Date**: 2026-08-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/20260831-135756-formulaire-benevolat-public/spec.md`

## Summary

Ouvrir la déclaration d'une action de bénévolat (aujourd'hui un geste admin
en un clic sans détail) à tout adhérent connecté, via un formulaire public
avec recherche d'athlète, titre et description. Approche : étendre le modèle
`VolunteerAction` existant (3 colonnes nullable/défaut), réutiliser la route
publique `GET /athletes` déjà en place pour la recherche (aucune nouvelle
route de recherche), et ajouter un endpoint self-service minimal
(`POST /volunteer-actions`, patron `volunteer_declarations.py` de #751) sans
toucher au bouton admin existant ni implémenter la validation (#779, #780
hors périmètre).

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript strict / Next.js 16 App Router (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2, Alembic ; TanStack Query, composants `tcn` (design system interne)

**Storage**: PostgreSQL (prod, Supabase) / SQLite (dev) — extension de la table `volunteer_actions` existante, aucune nouvelle table

**Testing**: pytest (backend, TDD non-réseau — Principe III) ; vitest (frontend)

**Target Platform**: web — backend Render, frontend Vercel

**Project Type**: web application (backend + frontend, structure existante)

**Performance Goals**: aucun objectif dédié — réutilise une route de recherche déjà en production (`GET /athletes`), pas de nouvelle charge de calcul

**Constraints**: ne pas modifier le bouton admin existant ni son endpoint (FR-008) ; ne pas implémenter la validation admin (FR-009, #779) ; colonnes nouvelles sans impact sur les lignes existantes (research.md D3/D4)

**Scale/Scope**: 1 migration (3 colonnes), 1 schéma Pydantic dédié, 1 fonction repository, 1 fonction service, 1 router (1 route), 1 section UI sur une page existante — pas de nouvelle route front

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Passage explicite des 6 principes de `.specify/memory/constitution.md` (v1.2.0).

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | UI/erreurs en français, identifiants/endpoints/schémas en anglais |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | Nouvelle route mince déléguant à un service, seule la nouvelle fonction repository construit la requête d'insertion |
| III | TDD sans réseau (non-négociable) | ✅ | Tests repository/service/API en `pytest`, aucun appel réseau (feature sans scraping) |
| IV | Contrats API et CLI stables | ✅ | `POST /volunteer-actions` est une route neuve, additive ; `VolunteerActionOut` de `admin.py` (endpoint admin existant) n'est pas modifiée |
| V | Neutralité par défaut des paramètres transverses | N/A | Aucun paramètre `scope`/`federal_only`/`seasons` concerné |
| VI | Simplicité / YAGNI | ✅ | Réutilise `GET /athletes` plutôt qu'une route de recherche redondante (research.md D2) ; nouvelle section sur une page existante plutôt qu'une route dédiée (research.md D7) |

Aucune violation — Complexity Tracking vide.

## Project Structure

### Documentation (this feature)

```text
specs/20260831-135756-formulaire-benevolat-public/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/            # Phase 1 output
│   └── volunteer-action-public-api.md
└── tasks.md              # Phase 2 output (/speckit-tasks — pas encore généré)
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/
│   └── <new>_add_title_description_status_to_volunteer_actions.py   # NEW
├── app/
│   ├── models/volunteer_action.py                # MODIFIED — 3 colonnes
│   ├── schemas/volunteer_action.py                # NEW — VolunteerActionCreate/Out self-service
│   ├── repositories/volunteer_action_repository.py  # MODIFIED — + create_pending()
│   ├── services/volunteer_action_service.py        # NEW — create_pending(), patron volunteer_declaration_service.py
│   └── api/v1/
│       ├── volunteer_actions.py                    # NEW — POST /volunteer-actions
│       └── router.py                               # MODIFIED — enregistrement du nouveau router
└── tests/
    ├── test_repositories/test_volunteer_action_repository.py  # MODIFIED
    ├── test_services/test_volunteer_action_service.py         # NEW
    └── test_api/test_volunteer_actions_api.py                 # NEW

frontend/
├── lib/
│   ├── api/client.ts                     # MODIFIED — createVolunteerAction, searchAthletesConnected
│   ├── types.ts                          # MODIFIED — VolunteerActionCreate/Out
│   └── queries/volunteer-actions.ts      # NEW — useCreateVolunteerAction (patron volunteer-declarations.ts)
├── components/benevolat/
│   └── VolunteerActionForm.tsx           # NEW — recherche athlète (patron ReattributionField.tsx) + titre/description
└── app/(public_restricted)/benevolat/
    └── page.tsx                          # MODIFIED — nouvelle section
```

**Structure Decision**: Web application existante (backend/ + frontend/,
architecture en couches). Aucune nouvelle route frontend ; le nouveau
formulaire est une section supplémentaire de la page `/benevolat` déjà
gardée par session (research.md D7). Côté backend, un router self-service de
plus, jumeau de `volunteer_declarations.py` (#751) — l'endpoint admin
existant (`admin_data.py`) n'est pas touché.

## Complexity Tracking

*Aucune violation de la Constitution Check — table vide.*
