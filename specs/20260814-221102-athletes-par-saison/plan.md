# Implementation Plan: Page de visualisation des athlètes par saison

**Branch**: `feature-page-visualisation-des-preuves-par-athl` | **Date**: 2026-08-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/20260814-221102-athletes-par-saison/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Une page dédiée `/club/athletes`, publique, liste les athlètes du club ayant
≥1 participation sur la saison sélectionnée (saison en cours par défaut), avec
leur nombre d'épreuves sur cette saison, triable par nombre d'épreuves ou par
nom de famille. Approche : un nouvel endpoint additif `GET /athletes/season-activity`
(agrégat en lecture seule, aucune nouvelle table) réutilisant tels quels les
briques existantes — `season.py` (bornes de saison), `club.py` (`tcn_clause`),
et le composant `SeasonSelector` déjà en place sur `/dashboard`. Le tri est géré
côté client comme `RankTypeToggle` (`?rank=`) : aucun rendu serveur ne lit ce
paramètre, donc `pushState` + recalcul en mémoire sur une liste déjà chargée
en entier (dizaines de lignes, pas de pagination — cf. Assomptions du spec).

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript strict / Next.js 16 App Router (frontend) — stack imposée par `AGENTS.md`, aucune déviation.

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2 côté backend ; Tailwind + shadcn/ui (`components/tcn`) côté frontend. Aucune nouvelle dépendance.

**Storage**: PostgreSQL (Supabase prod) / SQLite (dev) — lecture seule sur le schéma existant (`Athlete`, `Course`, `Participation`), aucune nouvelle table ni colonne.

**Testing**: `uv run pytest -m "not integration"` (repository + API, fixtures SQLite en mémoire) ; `npm test` (Vitest + RTL) pour le composant de tri et la page.

**Target Platform**: Web — backend Render, frontend Vercel (inchangé).

**Project Type**: Web application (backend + frontend, déjà en place — Option 2 de la structure ci-dessous).

**Performance Goals**: Aucune cible chiffrée nouvelle — la page charge la liste complète d'une saison en un aller-retour, comme `/club` (`page_size: 1000` sur `listParticipations`) ; le volume par saison reste dans les dizaines d'athlètes (cf. Assomptions du spec).

**Constraints**: Aucune contrainte technique nouvelle. Filtre club et filtre saison doivent réutiliser exactement `tcn_clause`/`season_bounds` existants (Principe II — la règle club ne se réimplémente nulle part ailleurs).

**Scale/Scope**: Une page front, un endpoint backend additif, aucune migration.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Passage explicite des 6 principes de `.specify/memory/constitution.md` (v1.1.1).
Statuts autorisés : ✅ conforme / ⚠️ justifié (ligne à créer dans Complexity
Tracking) / N/A (le principe ne s'applique pas à cette feature).

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | UI et libellés en français ; endpoint, fonctions repository, tests en anglais. |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | Nouvelle requête dans `athlete_repository.py` (seule couche Session), router `athletes.py` délègue sans logique. |
| III | TDD sans réseau (non-négociable) | ✅ | Repository + endpoint testés en SQLite mémoire (`backend/tests/conftest.py`), aucun scraping impliqué. |
| IV | Contrats API et CLI stables | ✅ | Endpoint **additif** (`GET /athletes/season-activity`), aucune modification d'un contrat `/api/v1` existant. |
| V | Neutralité par défaut des paramètres transverses | ✅ | `scope`/`seasons` sur le nouvel endpoint gardent le défaut neutre des endpoints `/stats/*` existants ; c'est le front qui impose `scope=club` et la saison en cours, jamais l'API. |
| VI | Simplicité / YAGNI | ✅ | Pas de pagination, pas de paramètre de tri serveur (tri client sur liste déjà chargée, comme `RankTypeToggle`), pas de nouvelle table. |

Un principe en ⚠️ doit être justifié dans « Complexity Tracking » ci-dessous
avec l'alternative rejetée et la raison. Un principe violé sans justification
bloque le passage à `/speckit-tasks`.

## Project Structure

### Documentation (this feature)

```text
specs/20260814-221102-athletes-par-saison/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/v1/athletes.py            # + route GET /athletes/season-activity
│   ├── repositories/athlete_repository.py  # + list_with_season_participation_count()
│   └── schemas/athlete.py            # + AthleteSeasonActivity
└── tests/
    ├── test_repositories/test_athlete_repository.py  # + cas saison/club/tri
    └── test_api/test_athletes_api.py                 # + cas endpoint

frontend/
├── app/club/athletes/page.tsx        # nouvelle page (RSC, lit ?seasons & ?sort)
├── components/club/                  # composant liste + tri (mirroring RankTypeToggle)
├── lib/api/server.ts                 # + apiServer.listAthleteSeasonActivity
├── lib/types.ts                      # + AthleteSeasonActivity
└── components/layout/nav.config.ts   # + 1 entrée dans la section "club"
```

**Structure Decision**: Option 2 (web application, backend + frontend déjà en
place). Aucun nouveau dossier de premier niveau — la feature s'insère dans
l'arborescence existante des deux applications, couche par couche, sans
déroger à `api → services → repositories → DB` (pas de couche `services/`
nouvelle : l'agrégat est une requête de lecture pure, comme `search_admin`
dans le même repository, sans règle métier au-delà du filtre saison/club déjà
centralisé dans `core/season.py`/`core/club.py`).

## Complexity Tracking

> Aucune violation de la Constitution Check ci-dessus — section sans objet.
