# Implementation Plan: Page de résultats détaillée d'une participation

**Branch**: `20260813-163525-resultats-detail-participation` | **Date**: 2026-08-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/20260813-163525-resultats-detail-participation/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Nouvelle page de détail par participation (`/courses/[id]/participations/[participationId]`),
atteinte depuis une ligne de finisher (page course) ou une ligne d'épreuve
(page athlète), qui remplace la navigation actuelle vers l'autre page. Elle
compare l'athlète au classement complet de sa course sur trois blocs
(comparaison à d'autres positions, évolution du classement par étape,
simulation de gains par amélioration), calculés à la demande côté backend à
partir du classement déjà en base — aucune nouvelle donnée scrapée, aucune
migration. L'éligibilité d'une course (splits complets pour tous les
finishers) est tranchée par une liste de fournisseurs en code, jamais par une
donnée stockée ni un panel d'administration. Le contrat existant
`GET /api/v1/participations/{id}` est étendu par un champ optionnel `stats`
(`null` si non éligible), sans nouvelle route ni rupture de contrat.

## Technical Context

**Language/Version**: Python 3.13 (backend, `uv`) ; TypeScript strict (frontend, Next.js 16 App Router)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2 ; côté front, React/Next.js, Tailwind v4, shadcn/ui — aucune nouvelle dépendance (pas de librairie de charting, cf. research.md §4)

**Storage**: PostgreSQL (Supabase) en prod / SQLite en dev — aucune migration, aucune nouvelle table ni colonne (cf. data-model.md)

**Testing**: `uv run pytest -m "not integration"` (backend, unitaire sans réseau — Principe III) ; `npm test` (vitest, frontend)

**Target Platform**: Web — backend Render, frontend Vercel (déploiement existant, inchangé)

**Project Type**: Web application (monorepo `backend/` + `frontend/` existant)

**Performance Goals**: Page affichée en moins de 2 s pour une course de quelques centaines de finishers (SC-003) — un seul appel réseau front (`GET /participations/{id}` étendu), un seul parcours du classement complet côté backend par requête (pas de N+1, réutilise `list_for_course` déjà eager-loaded)

**Constraints**: Aucune authentification requise (lecture publique, cohérent avec l'existant) ; contrat `/api/v1` non cassé (Principe IV) ; aucune dépendance frontend ajoutée

**Scale/Scope**: Une nouvelle page frontend, une extension de schéma de sortie, un nouveau service de calcul backend, un nouveau module de règle métier (`app/core/splits_reliability.py`) — pas de nouvel endpoint, pas de nouvelle table

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Passage explicite des 6 principes de `.specify/memory/constitution.md` (v1.1.1).
Statuts autorisés : ✅ conforme / ⚠️ justifié (ligne à créer dans Complexity
Tracking) / N/A (le principe ne s'applique pas à cette feature).

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Nouveaux identifiants (`ParticipationStatsOut`, `has_reliable_splits`, `participation_stats_service`, `RankingEvolutionStep`...) en anglais ; texte affiché (état "statistiques indisponibles", libellés `"1er"`/`"10e"`...) en français. |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | Nouveau calcul dans `app/services/participation_stats_service.py`, réutilise `participation_repository.list_for_course` (aucune requête SQL ajoutée dans le router) ; règle d'éligibilité isolée dans un seul module (`app/core/splits_reliability.py`), miroir de `app/core/club.py` — pas de réimplémentation ailleurs. |
| III | TDD sans réseau (non-négociable) | ✅ | Logique de calcul pure testée sans DB (fakes `SimpleNamespace`, cf. research.md §6) ; aucun appel réseau réel, la feature ne scrape rien. |
| IV | Contrats API et CLI stables | ✅ | `stats` est un champ optionnel additif sur `ParticipationOut` existant — aucune route retirée/renommée, aucun champ existant modifié (cf. contracts/get-participation-stats.md). |
| V | Neutralité par défaut des paramètres transverses | N/A | Aucun nouveau paramètre transverse (`scope`, `federal_only`...) introduit ; l'éligibilité et l'absence de restriction club (FR-004) ne sont pas des paramètres de requête mais une propriété calculée de la ressource. |
| VI | Simplicité / YAGNI | ✅ | Calcul à la demande, pas de cache dédié ni de table de matérialisation ; liste d'éligibilité en code plutôt qu'en panel admin (décision actée en clarification) ; aucune dépendance frontend ajoutée pour un graphique à 2 séries / 5 points. |

Aucun principe en ⚠️ — Complexity Tracking vide.

## Project Structure

### Documentation (this feature)

```text
specs/20260813-163525-resultats-detail-participation/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── get-participation-stats.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── core/
│   │   └── splits_reliability.py        # NOUVEAU — has_reliable_splits(), is_stats_eligible()
│   ├── services/
│   │   └── participation_stats_service.py  # NOUVEAU — ranking_evolution / comparison / improvement
│   ├── schemas/
│   │   ├── participation_stats.py       # NOUVEAU — RankingEvolutionStep, ComparisonRow, ImprovementRow, ParticipationStatsOut
│   │   └── participation.py             # MODIFIÉ — ParticipationOut.stats: ParticipationStatsOut | None
│   └── api/v1/
│       └── participations.py            # MODIFIÉ — GET /{id} assemble stats via le nouveau service
└── tests/
    ├── test_services/
    │   └── test_participation_stats_service.py   # NOUVEAU
    ├── test_api/
    │   └── test_participations_api.py             # MODIFIÉ (cas stats null / peuplé)
    └── test_core/
        └── test_splits_reliability.py             # NOUVEAU

frontend/
├── app/courses/[id]/participations/[participationId]/
│   └── page.tsx                          # NOUVEAU — route de détail
├── components/tcn/participation-detail/  # NOUVEAU — ResultRow, ComparisonTable, RankingEvolutionChart, ImprovementMatrix, UnavailableState
├── lib/api/server.ts                     # MODIFIÉ — getParticipation(id)
├── lib/types.ts                          # MODIFIÉ — Participation.stats, ParticipationStats
├── components/results/RaceFinishers.tsx  # MODIFIÉ — clic de ligne → nouvelle route (remplace /athletes/[id])
└── app/athletes/[id]/page.tsx            # MODIFIÉ — clic de ligne → nouvelle route (remplace /courses/[id])
```

**Structure Decision**: Web application existante (Option 2), aucune nouvelle
app ni service — extension du monorepo `backend/` + `frontend/` en place.
Aucune migration Alembic (pas de nouveau champ persisté, cf. data-model.md).

## Complexity Tracking

> Aucune violation de principe — section sans objet pour cette feature.
