# Implementation Plan: Les 13 questions que l'app ne sait pas montrer

**Branch**: `20260826-113857-viz-13-questions` | **Date**: 2026-08-26 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/20260826-113857-viz-13-questions/spec.md`

## Summary

Livrer, dans une seule PR parapluie traitée séquentiellement (13 user
stories, US1→US13), les 13 visualisations que l'issue #466 identifie comme
manquantes. L'approche technique, confirmée par la recherche de Phase 0
(`research.md`) : **la quasi-totalité de la donnée existe déjà**, calculée
côté backend ou déjà chargée côté frontend, puis réduite ou jetée avant
affichage. 10 des 13 US se résolvent par agrégation côté client sans aucune
extension backend ; 2 US (US4, US5) étendent additivement un schéma Pydantic
existant (`participation_stats.py`) avec des valeurs déjà calculées ; une
seule US (US13) nécessite une migration Alembic (timestamps de résolution
absents du modèle) et une nouvelle route de lecture. Tout graphique ajouté
se pose sur `d3-scale`/`d3-shape`, déjà en dépendance, sans rouvrir
l'identité visuelle ni le standard responsive posé par #480.

## Technical Context

**Language/Version**: Python 3.13 (backend) ; TypeScript strict, Next.js 16
App Router (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2,
Alembic ; `d3-scale@4`, `d3-shape@3` (déjà en dépendance frontend, aucune
nouvelle bibliothèque de visualisation), Tailwind, shadcn/ui

**Storage**: PostgreSQL (Supabase, prod) / SQLite (dev), une migration
Alembic (US13 : `validated_at`/`rejected_at` nullable sur `Participation`)

**Testing**: `uv run pytest -m "not integration"` (backend, TDD sans
réseau) ; `npm test` (vitest, frontend) ; `npm run build` (TS strict + RSC)

**Target Platform**: web, rendu serveur (SSR) préservé sans JavaScript sur
les graphiques ajoutés, cohérent avec l'existant (`Histogram`,
`CategoryBars`)

**Project Type**: application web (frontend Next.js + backend FastAPI)

**Performance Goals**: aucune requête N+1 nouvelle — réutilisation des
fetches déjà en place (patron `courses/[id]/page.tsx:60-64`, fetch parallèle
de `getCourseSummary`) ; agrégations côté client sur des payloads déjà
chargés, pas de nouvel aller-retour réseau pour 10 des 13 US

**Constraints**: pas de nouvelle bibliothèque de visualisation ; identité
visuelle non rouverte (`--tcn-*`, Anton/Barlow) ; responsive au standard déjà
posé par #480 ; formats de temps en strings normalisées (`app/scrapers/
utils.py`), jamais de `timedelta` en base ni en DTO ; contrats `/api/v1`
existants étendus uniquement de façon additive (Principe IV)

**Scale/Scope**: 13 user stories sur 6 écrans (`/athletes/[id]`,
`/courses/[id]` + détail de participation, `/club`, `/dashboard`,
`/resultats`, `/carte`, `/benevoles`) ; 1 migration Alembic ; 2 schémas
Pydantic étendus additivement ; 1 route nouvelle

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Libellés, états vides et messages UI en français ; nouveaux identifiants (`cumulative_seconds`, `validated_at`, `ValidationQueueHistory`…) en anglais |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | Nouvelle colonne écrite par le service de validation existant (`admin_actions`) via repository ; nouvelle route `benevoles.py` fine, délègue à un service qui délègue à un repository — aucun raccourci |
| III | TDD sans réseau (non-négociable) | ✅ | Chaque US précédée d'un test rouge (contrat de schéma additif, migration, agrégation client) avant le code, suivi en `tasks.md` |
| IV | Contrats API et CLI stables | ✅ | Toutes les extensions de schéma sont additives (`cumulative_seconds`, `mine_seconds`/`theirs_seconds`) ; la seule route nouvelle (`GET /benevoles/queue/history`) ne modifie aucun contrat existant — pas de v2 nécessaire |
| V | Neutralité par défaut des paramètres transverses | N/A | Aucune US n'introduit de nouveau paramètre transverse (`scope`/`federal_only`/`seasons`) ; les vues consommées existent déjà avec leurs défauts neutres actuels |
| VI | Simplicité / YAGNI | ✅ | 10/13 US n'ajoutent aucune ligne d'API : agrégation client sur des données déjà chargées plutôt que de nouveaux endpoints ; réutilisation de composants existants (`MonthlyTrend`, `CategoryBars`, `GenderDonut` en pattern) quand c'est possible |

Aucun principe en ⚠️ : pas d'entrée en Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/20260826-113857-viz-13-questions/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── participation-stats.md
│   └── validation-queue-history.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── models/
│   │   └── participation.py                    # US13 : + validated_at, rejected_at
│   ├── schemas/
│   │   ├── participation_stats.py               # US4, US5 : champs additifs
│   │   └── validation_queue.py                  # US13 : nouveau schéma ValidationQueueHistory (ou ajouté à participation.py)
│   ├── repositories/
│   │   └── participation_repository.py           # US13 : nouvelle fonction de lecture d'historique
│   ├── services/
│   │   ├── participation_stats_service.py         # US4, US5 : exposer les valeurs déjà calculées
│   │   ├── admin_actions.py                        # US13 : écrire validated_at/rejected_at à la transition
│   │   └── benevole_queue_history_service.py       # US13 : nouveau, agrégation arriéré/délai (nom à confirmer en tasks)
│   ├── api/v1/
│   │   └── benevoles.py                             # US13 : nouvelle route GET /benevoles/queue/history
│   └── alembic/versions/
│       └── <nouvelle révision>                       # US13 : migration
└── tests/
    ├── test_services/test_participation_stats_service.py   # US4, US5
    ├── test_api/test_benevoles_api.py                       # US13
    └── test_repositories/test_participation_repository.py   # US13

frontend/
├── app/(public_restricted)/
│   ├── athletes/[id]/page.tsx                          # US1, US4 (récurrence), US6, US7
│   ├── courses/[id]/page.tsx                            # US2 (source), inchangé pour l'essentiel
│   ├── .../participations/[participationId]/page.tsx    # US2, US3, US4, US5
│   ├── club/page.tsx                                     # US9, US10
│   ├── dashboard/page.tsx                                 # US8, US10
│   ├── resultats/page.tsx                                 # US11
│   ├── carte/page.tsx                                      # US12
│   └── benevoles/page.tsx                                   # US13
├── components/charts/
│   ├── MonthlyTrend.tsx                # réutilisé tel quel (US8 perf, US11 couverture)
│   ├── CategoryBars.tsx                 # étendu (US3, repère catégorie)
│   ├── Histogram.tsx                    # étendu (US2, repère athlète)
│   ├── RankingEvolutionChart.tsx        # étendu (US5, allure)
│   ├── ComparisonTable.tsx              # étendu (US4, écarts visuels)
│   ├── GenderDonut.tsx                  # pattern réutilisé, pas instance (US9)
│   ├── ProgressionChart.tsx              # nouveau (US1)
│   ├── AthleteComparisonChart.tsx        # nouveau (US6)
│   ├── ClubPerformanceChart.tsx          # nouveau (US8, US10)
│   └── ValidationBacklogChart.tsx        # nouveau (US13)
├── lib/utils/
│   ├── ranking.ts                        # inchangé, réutilisé (US1)
│   ├── club-aggregate.ts                 # étendu (US9 category, US10 discipline)
│   └── format.ts                          # réutilisé (US7)
└── lib/api/
    └── client.ts                          # US13 : nouvel appel getValidationQueueHistory
```

**Structure Decision**: application web existante (frontend Next.js +
backend FastAPI), aucune nouvelle direction de dossier. Le travail se
répartit sur les couches déjà en place : extension de schémas/repository/
service backend pour 2 US, une migration + un nouveau trio service/
repository/route pour 1 US, et agrégation/composants côté
`frontend/lib/utils/` + `frontend/components/charts/` pour les 10 restantes.

## Complexity Tracking

*Aucune entrée — aucun principe en ⚠️.*
