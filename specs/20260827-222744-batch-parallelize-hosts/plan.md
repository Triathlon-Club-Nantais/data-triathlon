# Implementation Plan: Parallélisation du batch d'import par hôte de chronométrage

**Branch**: `20260827-222744-batch-parallelize-hosts` | **Date**: 2026-08-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/20260827-222744-batch-parallelize-hosts/spec.md`

## Summary

`run_batch` (`backend/app/services/batch.py`) traite aujourd'hui toutes les
épreuves d'un lot strictement en séquence, avec 1s de politesse entre deux
scrapes — le facteur dominant de durée sur un lot couvrant des dizaines de
chronométreurs (145 épreuves → ~2h40 mesurées, issue #690). L'approche
retenue : regrouper les épreuves par **chronométreur** (au sens de la
résolution de provider déjà en place dans `app/scrapers/registry.py` — un
chronométreur peut publier sur plusieurs domaines, cf. Clarifications de
`spec.md`), garder chaque groupe strictement séquentiel avec le même délai de
politesse, et exécuter les groupes en concurrence via un
`concurrent.futures.ThreadPoolExecutor` borné. Chaque thread de groupe ouvre
sa propre `Session` SQLAlchemy (`session_scope()`, déjà pris en charge par le
pool existant). Le `ProgressReporter` et ses deux implémentations CLI
(`PlainReporter`, `RichReporter`) doivent porter une identité de groupe au
lieu d'un unique état « épreuve courante », et le Ctrl-C doit devenir un
signal coopératif vérifié entre deux épreuves de chaque groupe plutôt qu'une
`KeyboardInterrupt` reçue par un seul thread.

## Technical Context

**Language/Version**: Python 3.13 (inchangé)

**Primary Dependencies**: `concurrent.futures.ThreadPoolExecutor` (stdlib,
aucune nouvelle dépendance) ; SQLAlchemy 2.0 sync déjà en place
(`app/core/database.py` — `SessionLocal` est un `sessionmaker` sur un pool
`db_pool_size=15` / `max_overflow=10`, largement suffisant pour un plafond de
concurrence à un chiffre)

**Storage**: PostgreSQL (Supabase, prod) / SQLite (dev) — inchangé, aucune
migration : cette feature ne touche aucune table, seulement des structures en
mémoire (`BatchItem`, `BatchTotals`) et l'orchestration du batch

**Testing**: pytest (`uv run pytest -m "not integration"`), sans réseau réel
— `import_service.iter_import_event` reste monkeypatché comme aujourd'hui ; la
preuve de concurrence effective doit s'appuyer sur des primitives de
synchronisation (`threading.Event`/`Barrier`) plutôt que sur des `sleep()`
minutés, pour rester déterministe

**Target Platform**: Linux (poste de dev, runner GitHub Actions —
`.github/workflows/batch.yml`)

**Project Type**: Backend existant (CLI Typer + services) — aucune nouvelle
application, périmètre entièrement dans `backend/`

**Performance Goals**: SC-001 — au moins 50 % de réduction du temps mur sur un
lot de plusieurs dizaines de chronométreurs distincts, sans changer le volume
de requêtes envoyées à chaque chronométreur (SC-005)

**Constraints**: contrats CLI inchangés — stdout/stderr, schéma `--json`,
codes de sortie (0/1/2/130), bilan partiel sur Ctrl-C (Principe IV) ; aucune
régression de temps mur quand il n'y a qu'un seul chronométreur dans le lot
(SC-002)

**Scale/Scope**: lots allant jusqu'à plusieurs centaines d'épreuves réparties
sur des dizaines de chronométreurs distincts (cas mesuré : 483 épreuves,
issue #690)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Passage explicite des 6 principes de `.specify/memory/constitution.md` (v1.1.0).
Statuts autorisés : ✅ conforme / ⚠️ justifié (ligne à créer dans Complexity
Tracking) / N/A (le principe ne s'applique pas à cette feature).

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Nouveaux identifiants (`ThreadPoolExecutor`, groupement par hôte) en anglais ; rapports/aide CLI en français, comme aujourd'hui |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | L'orchestration de concurrence reste dans `app/services/batch.py` ; `app/cli/` ne gagne qu'une option Typer de plus, zéro logique métier ajoutée côté CLI |
| III | TDD sans réseau (non-négociable) | ✅ | Tests via monkeypatch de `iter_import_event`, synchronisation par `threading.Event`/`Barrier` plutôt que par `sleep()` minuté — aucun réseau réel, `-m "not integration"` reste vert |
| IV | Contrats API et CLI stables | ✅ | Schéma `--json`, codes de sortie, séparation stdout/stderr inchangés (FR-005) ; la nouvelle option de concurrence est additive |
| V | Neutralité par défaut des paramètres transverses | N/A | Principe scopé aux paramètres de lecture des endpoints (`scope`, `federal_only`) ; cette feature ne touche aucun endpoint de lecture |
| VI | Simplicité / YAGNI | ✅ | `ThreadPoolExecutor` stdlib retenu plutôt qu'une réécriture asyncio des 14 scrapers (I/O-bound, aucun bénéfice CPU) — voir research.md |

**Re-check post Phase 1** : `research.md` et `data-model.md` ne font émerger
aucune nouvelle dépendance, table ou endpoint — le statut de chaque principe
ci-dessus reste inchangé après la conception détaillée.

Un principe en ⚠️ doit être justifié dans « Complexity Tracking » ci-dessous
avec l'alternative rejetée et la raison. Un principe violé sans justification
bloque le passage à `/speckit-tasks`.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
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
│   ├── services/
│   │   ├── batch.py            # run_batch : regroupement par hôte + ThreadPoolExecutor
│   │   ├── progress.py         # Protocol ProgressReporter : identité de groupe
│   │   ├── bulk_import_service.py   # appelant de run_batch (import-sheet) — inchangé
│   │   └── rescrape_service.py      # appelant de run_batch (rescrape-db) — inchangé
│   ├── scrapers/
│   │   └── registry.py         # résolution URL → chronométreur, déjà en place (lecture seule)
│   └── cli/
│       ├── progress.py         # PlainReporter/RichReporter : un état par groupe
│       └── commands/
│           ├── import_sheet.py # + option --max-concurrent-hosts
│           └── rescrape_db.py  # + option --max-concurrent-hosts
└── tests/
    └── test_services/
        └── test_batch.py       # tests actuels (1 hôte) + nouveaux cas multi-hôtes
```

**Structure Decision**: Projet existant (backend Python + frontend Next.js
séparés, cf. `AGENTS.md`). Cette feature est **entièrement backend**, sans
migration de schéma ni endpoint HTTP nouveau : elle modifie l'orchestration
déjà en place dans `app/services/batch.py` et `app/services/progress.py`, et
ajoute une option Typer sur les deux commandes qui consomment `run_batch`.
Aucun nouveau dossier, aucune nouvelle couche.

## Complexity Tracking

Aucune violation de la Constitution Check — rien à justifier ici.
