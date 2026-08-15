# Implementation Plan: Distinction abandons / non-partants / disqualifiés

**Branch**: `20260815-112430-abandons-dnf-dns-dsq` | **Date**: 2026-08-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/20260815-112430-abandons-dnf-dns-dsq/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

`CourseSummary.non_finishers` agrège aujourd'hui trois statuts (`DNF`, `DNS`,
`DSQ`) sous un seul entier, ce que la page `/courses/[id]` et le résumé de
`RaceFinishers` affichent tous deux sous le seul mot « abandons ». Cette
feature ajoute trois champs additifs (`dnf`, `dns`, `dsq`) à `CourseSummary`,
calculés à partir du même statut déjà collecté (aucune nouvelle donnée, aucune
migration), et fait afficher aux deux consommateurs front trois indications
séparées au lieu d'une, chacune masquée quand nulle. `non_finishers` reste en
place, inchangé, pour ne rompre aucun appelant existant (Principe IV).

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript strict / Next.js 16 App Router (frontend) — inchangé, aucune nouvelle dépendance.

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2 côté backend ; React Server Components côté frontend. Rien de nouveau.

**Storage**: PostgreSQL (Supabase) / SQLite dev — aucune migration : `dnf`/`dns`/`dsq` sont dérivés à la volée dans `stats_service.course_summary`, qui itère déjà la colonne `status` existante via `_STATUTS_NON_FINISHERS`.

**Testing**: `uv run pytest -m "not integration"` (backend, cas des trois statuts sur `course_summary`), `npm test` (frontend, rendu de `/courses/[id]` et de `resumeEpreuve`).

**Target Platform**: Web — API `/api/v1` (Render) + Next.js (Vercel), inchangé.

**Project Type**: Web application (backend + frontend), structure existante.

**Performance Goals**: Aucun changement mesurable attendu — le calcul décompose un `Counter` déjà itéré une fois par appel, sans requête ni boucle supplémentaire.

**Constraints**: Additif strict (Principe IV) — `non_finishers` ne change ni de nom ni de valeur ; aucun appelant existant de `CourseSummary` (page épreuve, `RaceFinishers`) ne doit perdre une information qu'il recevait hier.

**Scale/Scope**: Un service backend (`stats_service.course_summary`), un schéma (`CourseSummary`), deux sites de rendu frontend (`app/courses/[id]/page.tsx`, `components/results/RaceFinishers.tsx`). Pas de nouvel écran, pas de nouvelle route.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Passage explicite des 6 principes de `.specify/memory/constitution.md` (v1.1.0).
Statuts autorisés : ✅ conforme / ⚠️ justifié (ligne à créer dans Complexity
Tracking) / N/A (le principe ne s'applique pas à cette feature).

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Libellés d'écran (« Non-partants », « Disqualifiés ») en français ; noms de champs (`dnf`/`dns`/`dsq`, identiques aux codes déjà présents dans `_STATUTS_NON_FINISHERS`) en anglais technique. |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | Calcul dans `stats_service` (déjà la couche qui produit `CourseSummary`), aucun accès direct à la Session hors `participation_repository` existant. |
| III | TDD sans réseau (non-négociable) | ✅ | Tests backend sur `course_summary` avec des participations de statuts DNF/DNS/DSQ fixtures, sans réseau ; tests frontend sur des props `CourseSummary` construites en mémoire. |
| IV | Contrats API et CLI stables | ✅ | Champs additifs (`dnf`, `dns`, `dsq`) ; `non_finishers` conservé tel quel. Aucune CLI concernée. |
| V | Neutralité par défaut des paramètres transverses | N/A | Aucun paramètre transverse (`scope`, `federal_only`, `seasons`) impliqué — `course_summary` ne prend déjà aucun paramètre de filtre. |
| VI | Simplicité / YAGNI | ✅ | Trois compteurs supplémentaires dans la boucle existante, pas d'abstraction nouvelle ; `non_finishers` n'est pas recalculé à partir des trois (redondance assumée et minime, `non_finishers = dnf + dns + dsq` reste vrai par construction) plutôt que de risquer un calcul dérivé plus fragile côté front. |

Un principe en ⚠️ doit être justifié dans « Complexity Tracking » ci-dessous
avec l'alternative rejetée et la raison. Un principe violé sans justification
bloque le passage à `/speckit-tasks`.

## Project Structure

### Documentation (this feature)

```text
specs/20260815-112430-abandons-dnf-dns-dsq/
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
│   ├── schemas/course.py          # CourseSummary : + dnf, dns, dsq
│   └── services/stats_service.py  # course_summary() : décompose _STATUTS_NON_FINISHERS
└── tests/
    └── test_services/test_stats_service.py  # cas DNF/DNS/DSQ mêlés

frontend/
├── lib/types.ts                              # CourseSummary : + dnf, dns, dsq
├── app/courses/[id]/page.tsx                 # trois MetaPill au lieu d'une
├── components/results/RaceFinishers.tsx      # resumeEpreuve() : trois segments
└── tests (co-localisés, *.test.tsx)
```

**Structure Decision**: Web application existante (backend FastAPI + frontend
Next.js). Aucun nouveau module : la feature étend un service et un schéma déjà
en place côté backend, et met à jour deux sites de rendu déjà responsables de
cet agrégat côté frontend — pas de nouvelle couche, pas de nouveau composant
partagé (les deux affichages restent indépendants, comme aujourd'hui).

## Complexity Tracking

> Aucune violation de principe à justifier — toutes les cases de la Constitution
> Check sont ✅ ou N/A.
