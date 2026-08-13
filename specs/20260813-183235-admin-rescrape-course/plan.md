# Implementation Plan: Re-scrape à la demande d'une course depuis le back-office

**Branch**: `20260813-183235-admin-rescrape-course` | **Date**: 2026-08-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/20260813-183235-admin-rescrape-course/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Un administrateur déclenche, depuis la page publique d'une course (là où vit
déjà le panneau des sources, #284/#285), un re-scrape de la source active en
cours, et suit sa progression en temps réel. Techniquement : un nouvel
endpoint SSE `POST /admin/courses/{course_id}/rescrape`, gardé par
`courses:sources`, qui réutilise le générateur de progression déjà en place
pour l'import public (`import_service._scrape_all_streaming` /
`_Persister`), étendu d'un paramètre pour désarmer le cache TTL par heat (le
même besoin que la bascule de source, #285), et qui applique les mêmes gardes
que celle-ci (refus si zéro résultat ou épreuve divergente, purge des
orphelins) — mais avec une persistance en **upsert**, pas en remplacement
total : on rafraîchit la même source, on n'en substitue pas une autre.

## Technical Context

**Language/Version**: Python 3.13 (backend, inchangé) ; TypeScript strict /
Next.js 16 App Router (frontend, inchangé).

**Primary Dependencies**: FastAPI (`StreamingResponse`, patron déjà en place
dans `app/api/v1/scrape.py`) ; `app.services.import_service` (générateur de
scraping streamé) et `app.services.admin_actions` (gardes d'identité, purge
d'orphelins, journal) côté backend — aucune dépendance nouvelle. Côté front :
`lib/api/sse.ts` (lecteur SSE existant) et `@tanstack/react-query`
(`lib/queries/admin.ts`), même patron que `useSwitchCourseSource`.

**Storage**: PostgreSQL (Supabase) / SQLite dev — inchangé, **aucune
migration** : ni nouvelle colonne ni nouvelle table.

**Testing**: `uv run pytest -m "not integration"` (backend, mocks `httpx`
comme `test_scrape_api.py` / `test_admin_course_sources.py`) ; `npm test`
(Vitest + RTL) côté front.

**Target Platform**: service web Render (backend, process unique — cf.
`batch_runs.py`) ; Vercel (frontend).

**Project Type**: web (backend + frontend existants, aucune nouvelle app).

**Performance Goals**: aucun chiffre nouveau — le padding SSE de 2 Ko et la
cadence de `_scrape_all_streaming` (patron déjà mesuré pour l'import public)
sont réutilisés tels quels.

**Constraints**:
- Un seul re-scrape actif à la fois **par course** (FR-007) — verrou en
  mémoire, process unique du service web, pas de verrou distribué.
- Cache TTL totalement désarmé, y compris **par heat** d'un provider fan-out
  (FR-003) — le même besoin déjà résolu pour #285 via
  `scrape_for_replacement(use_cache_probe=False)`, mais absent du chemin
  streamé (`_scrape_all_streaming` ne l'expose pas encore).
- Persistance en **upsert** (comme l'import public), jamais en
  suppression-puis-réimport (ce qui distingue ce geste de la bascule de
  source #285, qui remplace un chronométreur par un autre).
- Refus explicite si zéro résultat ou épreuve divergente (FR-009), en
  réutilisant `admin_actions._require_same_event`, déjà écrit pour #285.

**Scale/Scope**: 1 endpoint backend, 1 générateur de service, extension de 2
signatures existantes (paramètre optionnel, défaut inchangé), 1 composant +
1 hook front. Aucun nouveau module de dépendance.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Passage explicite des 6 principes de `.specify/memory/constitution.md` (v1.1.1).
Statuts autorisés : ✅ conforme / ⚠️ justifié (ligne à créer dans Complexity
Tracking) / N/A (le principe ne s'applique pas à cette feature).

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Identifiants techniques nouveaux en anglais (`iter_rescrape_course`, `use_cache_probe`) ; messages `DomainError` (refus) en français. |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | Router mince (`admin_course_rescrape.py`) → service (`admin_actions.iter_rescrape_course`) → repositories existants. Aucune session touchée hors `app/repositories/`. |
| III | TDD sans réseau (non-négociable) | ✅ | Mocks `httpx.Client` (patron `test_admin_course_sources.py`) ; réseau réel isolé par le marker `integration`. |
| IV | Contrats API et CLI stables | ✅ | Nouvel endpoint, aucun contrat existant modifié. L'extension de `_scrape_all_streaming`/`iter_import_event` (nouveau paramètre `use_cache_probe: bool = True`) est une fonction interne de service, hors contrat public — défaut inchangé pour tout appelant existant. |
| V | Neutralité par défaut des paramètres transverses | ✅ | `use_cache_probe` par défaut `True` préserve le comportement actuel de l'import public ; seul l'appel admin le désarme explicitement, sur le même patron que `scrape_for_replacement`. |
| VI | Simplicité / YAGNI | ✅ | Aucune nouvelle abstraction : réutilisation directe de `_require_same_event`, `athlete_repository.only_on_course`/`delete_orphans_among`, `admin_action_log_repository`. Le verrou de concurrence est un verrou en mémoire (process unique documenté), pas un mécanisme distribué — marqué `ponytail:` dans le code. |

Aucune violation : la section « Complexity Tracking » reste vide.

## Project Structure

### Documentation (this feature)

```text
specs/20260813-183235-admin-rescrape-course/
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
│   ├── api/v1/
│   │   ├── admin_course_rescrape.py   # NOUVEAU — POST /admin/courses/{id}/rescrape (SSE)
│   │   └── router.py                  # monte le nouveau module
│   └── services/
│       ├── admin_actions.py           # + iter_rescrape_course (générateur), + verrou en mémoire
│       └── import_service.py          # _scrape_all_streaming / iter_import_event
│                                       # + paramètre use_cache_probe: bool = True
└── tests/
    ├── test_api/
    │   └── test_admin_course_rescrape.py   # NOUVEAU
    └── test_services/
        └── test_admin_actions.py           # + cas iter_rescrape_course

frontend/
├── lib/
│   ├── api/sse.ts          # + lecteur SSE pour le nouvel endpoint
│   └── queries/admin.ts    # + hook de déclenchement (patron useSwitchCourseSource)
├── hooks/
│   └── useRescrapeStream.ts    # NOUVEAU — patron de useImportStream.ts
├── components/courses/
│   └── CourseSourcesPanel.tsx  # + bouton « Re-scraper » et barre de progression
└── app/courses/[id]/
    └── page.tsx                 # inchangé en structure, consomme le composant mis à jour
```

**Structure Decision**: application web existante (option « backend +
frontend »), aucune nouvelle app ni nouveau projet. Le geste s'ajoute à la
page publique `courses/[id]` (là où vit déjà `CourseSourcesPanel`, #284/#285)
et non sur une page `/admin/courses/{id}` distincte — cette dernière n'existe
pas dans le code actuel (`app/admin/courses/page.tsx` est une **liste**, sans
route de détail), et le geste voisin (bascule de source) est déjà rendu sur
la page publique, gardé côté client par le pouvoir `courses:sources` (cf.
`research.md`, décision R4).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

Aucune violation — section sans objet.
