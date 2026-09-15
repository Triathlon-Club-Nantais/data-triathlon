# Implementation Plan: Profil individuel jeune

**Branch**: `867-profil-jeune` | **Date**: 2026-09-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/20260915-111701-profil-jeune/spec.md`

## Summary

Poser le modèle de données générique du profil individuel (#863) et le livrer
côté jeunes : deux tables (`personal_profiles`, `profile_log_entries`),
cinq routes sous `/admin/profiles` gardées par `jeunes:read`/`jeunes:write`
(catalogue déjà posé par #866), et un écran frontend mobile-first sous
`/admin/jeunes` (liste + détail avec journal de bord). Aucune donnée
adulte, aucun calendrier d'entraînement (#868), aucun flux d'appel de
présence (#869) : cette feature couvre la consultation et l'édition directe
d'un profil et de son journal, rien de plus.

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript strict (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2,
Alembic ; Next.js 16 App Router, Tailwind, shadcn/ui

**Storage**: PostgreSQL (Supabase) en production, SQLite en dev — migration
Alembic, schéma appliqué identique aux deux moteurs

**Testing**: pytest (`uv run pytest -m "not integration"`), Vitest + RTL
(`npm test`)

**Target Platform**: API web (Render) + SPA Next.js (Vercel) ; écran
consulté principalement sur téléphone

**Project Type**: Web application (backend + frontend déjà en place)

**Performance Goals**: Pas de contrainte spécifique — effectif de jeunes
d'un club (dizaines, pas milliers), aucune pagination nécessaire au lancement

**Constraints**: Mobile-first pour l'écran de consultation ; aucune donnée
personnelle de jeune visible sans le pouvoir `jeunes:read`

**Scale/Scope**: 2 tables, 5 routes, 1 écran (liste + détail)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Identifiants (`PersonalProfile`, `ProfileLogEntry`, colonnes) en anglais ; libellés, messages d'erreur et écran en français |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | `admin_profiles.py` (router, fin) → `profile_service.py` (orchestration, commit) → `profile_repository.py` (seule couche à construire des requêtes) |
| III | TDD sans réseau (non-négociable) | ✅ | Tests repository/service/API écrits avant le code, aucun appel réseau (tests DB SQLite en mémoire, patron `conftest.py`) |
| IV | Contrats API et CLI stables | N/A | Nouvelle ressource, aucun contrat existant modifié |
| V | Neutralité par défaut des paramètres transverses | N/A | Aucun paramètre transverse (`scope`, `federal_only`…) sur ces routes — un profil n'a pas de notion de club/saison |
| VI | Simplicité / YAGNI | ✅ | Pas de pagination, pas de soft-delete, pas de multi-organisation développée — seul le nécessaire à #867 |

Aucune violation à justifier dans « Complexity Tracking ».

## Project Structure

### Documentation (this feature)

```text
specs/20260915-111701-profil-jeune/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/            # Phase 1 output
│   └── admin-profiles.md
└── tasks.md              # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── models/
│   │   ├── personal_profile.py       # NEW — table personal_profiles
│   │   └── profile_log_entry.py      # NEW — table profile_log_entries
│   ├── schemas/
│   │   └── profile.py                # NEW — DTO Pydantic (Read/Create/Update)
│   ├── repositories/
│   │   └── profile_repository.py     # NEW — seule couche à requêter les deux tables
│   ├── services/
│   │   └── profile_service.py        # NEW — orchestration, vues, 404
│   ├── api/v1/
│   │   ├── admin_profiles.py         # NEW — 5 routes gardées jeunes:read/write
│   │   └── router.py                 # MODIFIÉ — inclusion du nouveau router
│   └── alembic/versions/
│       └── <rev>_add_personal_profiles.py  # NEW — migration
└── tests/
    ├── test_repositories/test_profile_repository.py   # NEW
    ├── test_services/test_profile_service.py           # NEW
    ├── test_api/test_admin_profiles.py                 # NEW
    └── test_permissions_catalogue.py                    # MODIFIÉ — retrait des 2 entrées GARDE_A_VENIR

frontend/
├── app/admin/jeunes/
│   ├── page.tsx                      # NEW — liste des profils
│   └── [id]/page.tsx                 # NEW — détail + journal
├── components/admin/
│   ├── ProfilesTable.tsx             # NEW — liste (cartes, mobile-first)
│   └── ProfileDetail.tsx             # NEW — fiche + formulaire journal
├── lib/api/client.ts                 # MODIFIÉ — appels /admin/profiles
├── lib/types.ts                      # MODIFIÉ — types Profile / ProfileLogEntry
└── components/layout/nav.config.ts   # MODIFIÉ — entrée "Jeunes", permission jeunes:read
```

**Structure Decision**: Web application existante (Option 2), aucune structure
nouvelle. Les fichiers backend suivent le sens unique
`api → services → repositories → DB` ; le frontend ajoute un écran
`/admin/jeunes` au patron déjà en place (`/admin/groupes`).

## Complexity Tracking

*(vide — aucune violation à justifier)*
