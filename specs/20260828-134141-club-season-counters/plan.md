# Implementation Plan: Compteurs de saison distincts + validation humaine du quota club

**Branch**: `20260828-134141-club-season-counters` | **Date**: 2026-08-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/20260828-134141-club-season-counters/spec.md`

## Summary

`/club/athletes` compte aujourd'hui les épreuves d'un athlète en filtrant les
lignes de `Participation` sur le club **inscrit sur le résultat** — un champ
que deux fournisseurs de chronométrage ne publient jamais, ce qui sous-compte
39 % du roster (issue #709). Le correctif sépare deux usages aujourd'hui
confondus dans une même clause SQL (`research.md` D1) : la **sélection** des
athlètes du roster club (bascule sur `Athlete.club`, comme `athlete_repository.search()`)
et le **calcul** de trois compteurs distincts par athlète (total réel, validées,
affiliées club — une seule requête agrégée, D2). Le second volet ajoute une
déclaration de bénévolat en journal (`VolunteerAction`) et un statut de
validation de saison porté par l'existence d'une ligne (`SeasonValidation`),
tous deux gardés par des pouvoirs RBAC dédiés et tracés dans
`AdminActionLog` — patron déjà en place dans le dépôt (D4-D8).

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript strict / Next.js 16 App Router (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2, Alembic — aucune nouvelle dépendance

**Storage**: PostgreSQL (Supabase, prod) / SQLite (dev) — deux tables additives (`volunteer_actions`, `season_validations`)

**Testing**: pytest (backend, marker `integration` exclu par défaut), vitest (frontend)

**Target Platform**: Backend Render, frontend Vercel — inchangé

**Project Type**: Web application (backend + frontend, dépôt existant)

**Performance Goals**: Pas de régression sur `GET /athletes/season-activity` — une requête agrégée unique (comme aujourd'hui), pas de N+1 (research.md D2)

**Constraints**: Additivité stricte du contrat `/api/v1` (Principe IV, D3) ; aucune migration destructive

**Scale/Scope**: ~315 athlètes de roster club, volumes de bénévolat/validations bornés par la taille du club — pas de préoccupation de scale nouvelle

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Passage explicite des 6 principes de `.specify/memory/constitution.md` (v1.1.1).
Statuts autorisés : ✅ conforme / ⚠️ justifié (ligne à créer dans Complexity
Tracking) / N/A (le principe ne s'applique pas à cette feature).

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Nouveaux identifiants (`VolunteerAction`, `SeasonValidation`, `athletes:volunteer_manage`, `athletes:season_validate`) en anglais ; messages d'erreur utilisateur en français |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | Deux nouveaux repositories dédiés (`volunteer_action_repository.py`, `season_validation_repository.py`) ; routes dans `admin_data.py` existant, aucune Session hors repository |
| III | TDD sans réseau (non-négociable) | ✅ | Tests unitaires sur les nouveaux repositories/services/routes, aucun réseau ; réutilise les fixtures SQLite existantes |
| IV | Contrats API et CLI stables | ✅ | `season-activity` gagne 4 champs additifs, `participation_count` inchangé (D3) — aucune CLI touchée |
| V | Neutralité par défaut des paramètres transverses | ✅ | Aucun nouveau paramètre transverse de lecture ; `scope`/`seasons`/`federal_only` inchangés sur `season-activity` |
| VI | Simplicité / YAGNI | ✅ | `SeasonValidation` sans colonne de statut (existence de ligne suffit, D5) ; `VolunteerAction` sans lien `course_id` spéculatif (D4) |

Aucun principe en ⚠️ — pas d'entrée en Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/20260828-134141-club-season-counters/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── api.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── models/
│   │   ├── volunteer_action.py        # NOUVEAU (data-model.md)
│   │   └── season_validation.py       # NOUVEAU (data-model.md)
│   ├── repositories/
│   │   ├── athlete_repository.py      # MODIFIÉ — list_with_season_participation_count (D1, D2)
│   │   ├── volunteer_action_repository.py   # NOUVEAU
│   │   └── season_validation_repository.py  # NOUVEAU
│   ├── services/
│   │   └── admin_actions.py           # MODIFIÉ — déclarer bénévolat, valider/dévalider saison (D6)
│   ├── schemas/
│   │   └── athlete.py                 # MODIFIÉ — AthleteSeasonActivity, 4 champs additifs (contracts/api.md)
│   ├── api/v1/
│   │   ├── athletes.py                # MODIFIÉ — season-activity enrichi
│   │   └── admin_data.py              # MODIFIÉ — 3 nouvelles routes (D8)
│   └── core/
│       └── permissions.py             # MODIFIÉ — P.ATHLETES_VOLUNTEER_MANAGE, P.ATHLETES_SEASON_VALIDATE (D7)
├── alembic/versions/
│   ├── <rev>_volunteer_action.py       # NOUVEAU — migration additive (US2)
│   └── <rev>_season_validation.py      # NOUVEAU — migration additive (US3), séparée pour préserver l'indépendance des stories
└── tests/
    ├── test_repositories/test_athlete_repository.py    # MODIFIÉ
    ├── test_repositories/test_volunteer_action_repository.py  # NOUVEAU
    ├── test_repositories/test_season_validation_repository.py # NOUVEAU
    └── test_api/test_admin_data_api.py                   # MODIFIÉ

frontend/
├── components/club/
│   └── AthleteSeasonList.tsx          # MODIFIÉ — 3 compteurs, filtre validation (D8)
├── components/athletes/
│   └── SeasonValidationPanel.tsx      # NOUVEAU — action bénévolat + validation, patron ParticipationAdminActions.tsx (D8)
├── lib/
│   ├── types.ts                       # MODIFIÉ — AthleteSeasonActivity enrichi
│   └── queries/admin.ts               # MODIFIÉ — hooks pour les 3 nouvelles routes
```

**Structure Decision**: Web application existante (backend/ + frontend/,
Option 2 du gabarit). Aucune nouvelle couche architecturale — deux nouveaux
repositories suivent le patron Principe II, deux nouveaux modèles suivent
`AdminActionLog`/`BenevoleAccessConfig`, les routes rejoignent le router
`admin_data.py` déjà responsable de la fiche athlète administrable.

## Complexity Tracking

*Aucune entrée — Constitution Check entièrement ✅.*
