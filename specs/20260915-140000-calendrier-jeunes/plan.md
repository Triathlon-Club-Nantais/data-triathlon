# Implementation Plan: Calendrier des entraînements jeunes

**Branch**: `868-calendrier-jeunes` | **Date**: 2026-09-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/20260915-140000-calendrier-jeunes/spec.md`

## Summary

Poser le modèle de données d'un entraînement jeunes (date, heure, lieu, type
optionnels) et de sa liste de participants inscrits, avec les routes backend
CRUD/consultation gardées par `jeunes:read`/`jeunes:write`, et un écran
frontend calendrier mobile-first en lecture (US1) et écriture (US2, US3). Le
flux d'appel de présence (#869) est hors périmètre : ce lot ne pose que ce sur
quoi il s'appuiera.

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript strict / Next.js 16 App Router (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2, Alembic ; côté front, Tailwind, shadcn/ui, `lib/api/client.ts`

**Storage**: PostgreSQL (Supabase) en production, SQLite en dev — via Alembic

**Testing**: pytest (backend, sans réseau), Vitest + RTL (frontend)

**Target Platform**: API web `/api/v1` (Render) consommée par le front Vercel

**Project Type**: web (backend + frontend, patron déjà en place)

**Performance Goals**: aucun objectif spécifique au-delà du reste de l'API — le
volume (quelques dizaines de séances, quelques dizaines de jeunes) est trop
faible pour justifier une pagination dès ce lot.

**Constraints**: écran mobile-first (375 px sans défilement horizontal),
garde RBAC route par route (jamais un `dependencies=` de router).

**Scale/Scope**: un club (TCN), une poignée d'encadrants, quelques dizaines de
jeunes et de séances par saison.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Identifiants Python/TS en anglais (`entrainement` reste le nom métier retenu, cf. research.md — nom d'entité, pas un terme technique substituable) ; libellés UI, messages d'erreur et docstrings de règle métier en français. |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | Nouveau router `admin_jeunes_entrainements.py` → nouveau service `services/jeunes/entrainements.py` → nouveau repository `repositories/entrainement_jeunes_repository.py` → modèles SQLAlchemy. Aucune requête hors repository. |
| III | TDD sans réseau (non-négociable) | ✅ | `tasks.md` pose un test rouge avant chaque capacité (repository, service, route, composant frontend) ; aucun appel réseau réel dans ce lot. |
| IV | Contrats API et CLI stables | ✅ | Nouvelle surface `/api/v1`, aucun contrat existant modifié. |
| V | Neutralité par défaut des paramètres transverses | N/A | Aucun paramètre transverse (`scope`, `federal_only`, `seasons`) ne s'applique à une ressource jeunes, périmètre fermé au club unique. |
| VI | Simplicité / YAGNI | ✅ | Pas de pagination, pas de récurrence de séance, pas de nomenclature fermée pour `lieu`/`type` — rien de spéculatif au-delà de ce que l'issue #868 demande. |

## Project Structure

### Documentation (this feature)

```text
specs/20260915-140000-calendrier-jeunes/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── api.md
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── models/
│   │   ├── entrainement.py            # NOUVEAU — Entrainement
│   │   └── entrainement_participant.py # NOUVEAU — EntrainementParticipant
│   ├── schemas/
│   │   └── entrainement.py            # NOUVEAU — DTO Pydantic
│   ├── repositories/
│   │   └── entrainement_repository.py # NOUVEAU
│   ├── services/jeunes/
│   │   └── entrainements.py           # NOUVEAU
│   └── api/v1/
│       ├── admin_jeunes_entrainements.py # NOUVEAU — routes gardées
│       └── router.py                     # MODIFIÉ — enregistrement du router
├── alembic/versions/
│   └── <rev>_entrainements_jeunes.py  # NOUVEAU — migration
└── tests/
    ├── test_repositories/test_entrainement_repository.py  # NOUVEAU
    ├── test_services/test_entrainements_jeunes.py          # NOUVEAU
    ├── test_api/test_admin_jeunes_entrainements.py          # NOUVEAU
    └── test_permissions_catalogue.py                        # MODIFIÉ — retire jeunes:read de GARDE_A_VENIR

frontend/
├── app/admin/jeunes/calendrier/
│   └── page.tsx                        # NOUVEAU — écran calendrier
├── components/admin/jeunes/
│   ├── CalendrierEntrainements.tsx     # NOUVEAU — liste + garde d'écriture
│   ├── EntrainementForm.tsx            # NOUVEAU — création/modification
│   └── ParticipantsList.tsx            # NOUVEAU — liste + inscription/désinscription
├── lib/api/client.ts                   # MODIFIÉ — nouveaux appels
├── lib/types.ts                        # MODIFIÉ — nouveaux types
└── components/layout/nav.config.ts     # MODIFIÉ — entrée de navigation gardée par jeunes:read
```

**Structure Decision**: patron web existant (`backend/` + `frontend/`), aucune
nouvelle couche. L'écran vit sous `app/admin/jeunes/` (back-office, données
personnelles sensibles de mineurs, gardé par pouvoir RBAC — même famille que
`app/admin/groupes`, pas le groupe `(public_restricted)` du mot de passe
site).

## Complexity Tracking

*Aucune ligne : aucune violation de principe à justifier.*
