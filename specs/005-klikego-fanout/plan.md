# Implementation Plan: Fan-out des heats Klikego

**Branch**: `feat/156-klikego-fanout-event` | **Date**: 2026-07-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/005-klikego-fanout/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Le fan-out concerne **Klikego uniquement** (sondage 2026-07-31 : Breizh Chrono boucle déjà). Objectif : quand `KlikegoProvider.scrape_event_all(url)` reçoit une URL — nue ou avec `?heat=X` — il énumère **tous** les heats du `<el-select name="heat">` de la page événement et boucle sur chacun, en avalant l'échec d'un heat sans faire tomber les autres. Le reste du pipeline (`import_service`, SSE, API, CLI, front) traite déjà N `ScrapedResult` couvrant N `event_type` distincts : c'est le contrat existant, hérité du pattern Breizh Chrono. Le seul ajout côté front est un récap listant les N courses créées en fin d'import (A2). Une échappatoire CLI (A3) permet d'importer un heat unique quand nécessaire — hors chemin nominal.

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript strict (frontend Next.js 16)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, httpx + BeautifulSoup/lxml, Typer (CLI) ; React + Tailwind + shadcn/ui côté front.

**Storage**: SQLite en dev, PostgreSQL (Supabase) en prod. **Aucune migration Alembic** : le fan-out ne change ni le schéma ni la sémantique de `Course.source_url` (qui reste l'URL de heat individuelle `…?heat=X`).

**Testing**: pytest côté backend (marker `not integration` par défaut, réseau interdit dans les tests unitaires — Principe III), Vitest + RTL côté front. Un HTML de fixture Mesquer (issue #153/#154) sera capturé pour tester l'énumération du `<el-select>` sans réseau.

**Target Platform**: Web (backend Render, front Vercel, DB Supabase).

**Project Type**: Web app en deux briques (`backend/`, `frontend/`).

**Performance Goals**: Un fan-out sur événement 8-heats équivaut à 8 imports séquentiels — la charge est linéaire au nombre de heats. Sur les gros événements (14-18 heats de Ha' Frenchman Carcans / Diaoulman Pontivy / Médoc Carcans), un import complet peut prendre plusieurs minutes ; le SSE reste réactif car chaque `saving` progresse participant par participant (contrat existant).

**Constraints**: 
- Neutralité par défaut (Principe V) : le fan-out **ne dépend d'aucun paramètre transverse** (`scope`, `federal_only` ne le concernent pas — ils filtrent en lecture, pas en écriture).
- Le SSE `done` est **étendu** de 5 clés rétro-compatibles (`heats_enumerated`, `heats_imported`, `heats_cached`, `heats_failed`, `failures`) — cf. `contracts/klikego-fanout.md` §C4. **Extension additive**, un consommateur qui ignore les champs inconnus continue de fonctionner : conforme au Principe IV (contrats API/CLI stables). Le bilan CLI (`rescrape-db`, `import-sheet`) est étendu de la même façon (`--json` porte les 5 clés, texte porte un bloc « Heats en erreur (détail) : »).
- Le comportement du cache TTL est déjà correct au niveau du heat (`Course.source_url = …?heat=X`) — deux imports successifs de la même URL nue rebouclent sur les heats mais chaque heat individuel est trouvé frais et n'est pas re-scrapé (cf. FR-005 / SC-005). **À vérifier** : l'énumération HTML de la liste des heats ne bénéficie **pas** du cache — chaque import fan-out coûte 1 GET de page événement supplémentaire.
- CLI `rescrape-db` : ajouter `--single-heat` (option ; nom exact validé au plan). Distinct de `--url` et `--urls-from` : c'est un **modificateur** de la boucle interne du scraper Klikego, pas un mode de sélection.

**Scale/Scope**: Sur le Sheet actuel (45 événements Klikego), un import de masse plein rescrape passe de ~43 heats à ~241 heats côté Klikego. Le batch `import-sheet` gérait déjà 785 URLs, aucun changement de dimension.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Passage explicite des 6 principes de `.specify/memory/constitution.md` (v1.0.0).
Statuts autorisés : ✅ conforme / ⚠️ justifié (ligne à créer dans Complexity
Tracking) / N/A (le principe ne s'applique pas à cette feature).

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Feature écrite en français (spec, plan, sondage) ; identifiants et messages de log en anglais ; `DomainError` reste en français côté message. |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | Fan-out contenu dans `scrapers/klikego.py` + `scrapers/registry.py` ; `import_service` transparent (aucun changement) ; API/front consomment le contrat SSE existant. |
| III | TDD sans réseau (non-négociable) | ✅ | Tests par capture HTML de la page événement Mesquer (fixture) : énumération `<el-select>`, isolation d'un heat en échec, dégénérescence mono-heat, `?heat=` ignoré. Aucun test unitaire ne fait de réseau ; l'`integration` reste réservé au ping réel. |
| IV | Contrats API et CLI stables | ✅ | SSE `done` **étendu** de 5 clés rétro-compatibles (`heats_enumerated`/`heats_imported`/`heats_cached`/`heats_failed`/`failures[]`) — un consommateur qui ignore les champs inconnus reste fonctionnel. `POST /scrape/import` inchangé. CLI `--single-heat` est un **ajout** d'option, pas une brisure ; `--json` de `rescrape-db`/`import-sheet` porte les mêmes 5 clés en additif. |
| V | Neutralité par défaut des paramètres transverses | ✅ | Aucun nouveau paramètre transverse. `--single-heat` est un modificateur CLI **explicite** et **hors chemin nominal**, jamais activé par défaut. |
| VI | Simplicité / YAGNI | ✅ | Le fan-out se contient dans le seul scraper Klikego (~30 lignes ajoutées) et un rendu de récap front (~15 lignes JSX). Aucun nouveau service, aucun nouvel endpoint, aucune migration DB, aucune notion d'« événement » côté catalogue. |

Un principe en ⚠️ doit être justifié dans « Complexity Tracking » ci-dessous
avec l'alternative rejetée et la raison. Un principe violé sans justification
bloque le passage à `/speckit-tasks`.

## Project Structure

### Documentation (this feature)

```text
specs/005-klikego-fanout/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (léger — aucune entité DB nouvelle)
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── klikego-fanout.md   # Contrat côté scraper + CLI + SSE
├── checklists/
│   └── requirements.md  # Créé par /speckit-specify
└── tasks.md             # Phase 2 (créé par /speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── scrapers/
│   │   ├── klikego.py       # + _enumerate_heats(html) et boucle fan-out dans scrape_event_all
│   │   ├── registry.py      # KlikegoProvider.scrape_event_all : passe l'URL entière à klikego.scrape_event_all, plus de pré-résolution de heat
│   │   └── (autres scrapers inchangés — Breizh Chrono a déjà son fan-out)
│   ├── services/
│   │   └── import_service.py   # inchangé (consomme déjà N ScrapedResult sur N event_type)
│   └── cli/
│       └── commands/rescrape_db.py   # + option --single-heat (modifie le scrape Klikego pour un heat désigné, sinon fan-out)
└── tests/
    ├── test_klikego.py      # + fixture HTML Mesquer, cas énumération + heat en échec + ?heat= ignoré
    └── (contract test « no-migration » implicite : pas d'alembic revision ajoutée)

frontend/
├── components/scrape/
│   └── ImportProgress.tsx   # + rendu du récap {courses.map((c) => <Link href={`/courses/${c.id}`}>{c.name}</Link>)}
└── (le reste inchangé — useImportStream porte déjà state.courses)
```

**Structure Decision**: Modification chirurgicale dans `scrapers/klikego.py` (le fan-out y vit, symétrique à `breizhchrono._fetch_all_heats`), option CLI dans `cli/commands/rescrape_db.py`, ajout de rendu dans `frontend/components/scrape/ImportProgress.tsx`. Aucun nouveau fichier de service, aucune migration, aucun nouvel endpoint.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

*(Aucune violation à justifier — tous les principes sont ✅.)*
