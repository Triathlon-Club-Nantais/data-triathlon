# Implementation Plan: Persist par lot pour l'import de résultats

**Branch**: `20260828-131039-import-batch-persist` | **Date**: 2026-08-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/20260828-131039-import-batch-persist/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

`_Persister.add` (`backend/app/services/import_service.py`) résout
aujourd'hui chaque ligne importée par un aller-retour DB individuel :
résolution d'athlète (`get_by_identity`) sur le chemin dossard apparié
(`_reconcile`, inconditionnel) **et** sur le chemin dossard neuf/sans dossard
(`get_or_create_athlete`), puis un `db.flush()` par participation neuve.
`finalize()` recharge en plus une deuxième fois les participations de chaque
course, déjà chargées par `_index_course`. Sur un import de 1147 lignes
(Trégastel 2026), cela mesure 89 s en production (Render → Supabase) contre
2 s en local (SQLite).

Approche retenue (`research.md`) : à l'intérieur de `_Persister`, mettre en
attente par course les lignes qui ont besoin d'une résolution d'athlète,
résoudre par tranche (~500 lignes) via une requête unique
(`tuple_(lower(nom), lower(prenom)).in_(...)`, sachant que `birth_date` est
toujours `None` sur le chemin d'import), différer le `db.flush()` des
participations neuves à la fin de chaque tranche/course, et réutiliser la
liste chargée par `_index_course` dans `finalize()` au lieu de la
recharger. Aucun changement de schéma, aucun changement de contrat externe
(API SSE, CLI) — les compteurs et la granularité de progression restent
identiques.

## Technical Context

**Language/Version**: Python 3.13 (uv)

**Primary Dependencies**: SQLAlchemy 2.0 (sync ORM), FastAPI (endpoint SSE
appelant), Pydantic v2 (DTO inchangés par cette feature)

**Storage**: PostgreSQL (Supabase, production — où le goulot est mesuré) /
SQLite (dev, tests) — via `app/repositories/`

**Testing**: pytest (`backend/tests/test_services/test_import_service.py`),
marker `integration` non concerné (aucun réseau tiers impliqué, uniquement la
DB)

**Target Platform**: Backend Linux (Render)

**Project Type**: web-service — backend seul concerné, aucun changement front

**Performance Goals**: import de ~1147 lignes en quelques secondes en
production (actuellement 89 s) ; nombre de requêtes DB émises pendant la
persistance borné par le nombre de courses/tranches du scrape, pas par le
nombre de lignes (SC-001, SC-002)

**Constraints**: zéro changement de résultat métier observable (compteurs,
rapport qualité, contrat SSE/CLI — FR-004) ; la granularité de progression SSE
(yield tous les 20 items) doit rester intacte

**Scale/Scope**: un seul fichier de service concerné en profondeur
(`backend/app/services/import_service.py`, classe `_Persister`), lecture
seule sur `mapping.py`/`athlete_repository.py`/`participation_repository.py`
pour la requête de lot ; pas de migration, pas de nouvelle dépendance

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Passage explicite des 6 principes de `.specify/memory/constitution.md` (v1.1.0).
Statuts autorisés : ✅ conforme / ⚠️ justifié (ligne à créer dans Complexity
Tracking) / N/A (le principe ne s'applique pas à cette feature).

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Nouveaux identifiants (résolution par lot, file d'attente) en anglais technique ; commentaires « pourquoi » en français comme l'existant du fichier |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | La requête de lot (`tuple_(...).in_(...)`) et les créations groupées vivent dans `athlete_repository.py`/`participation_repository.py` (`get_by_identities_batch`, `create_batch` ×2), jamais inline dans `import_service.py` — `_Persister` reste un appelant de repository, comme aujourd'hui, sans jamais toucher `db`/`Session` directement (`tasks.md` Phase 2, corrigé suite à `/speckit-analyze` finding C1) |
| III | TDD sans réseau (non-négociable) | ✅ | Test rouge d'abord sur le comptage de requêtes (patron `test_course_merge.py`) et sur les cas de tranche, avant le refactor ; aucun réseau tiers impliqué |
| IV | Contrats API et CLI stables | ✅ | FR-004 : compteurs, rapport qualité, phases SSE et sortie CLI inchangés — refactor interne au service uniquement |
| V | Neutralité par défaut des paramètres transverses | N/A | Aucun paramètre transverse (`scope`, `federal_only`, `seasons`) touché par cette feature |
| VI | Simplicité / YAGNI | ✅ | Taille de tranche fixe (~500, cf. `research.md`), pas de configuration exposée ; flush différé plutôt qu'une nouvelle dépendance ou un ORM bypass (`bulk_insert_mappings` rejeté en recherche) |

Un principe en ⚠️ doit être justifié dans « Complexity Tracking » ci-dessous
avec l'alternative rejetée et la raison. Un principe violé sans justification
bloque le passage à `/speckit-tasks`.

## Project Structure

### Documentation (this feature)

```text
specs/20260828-131039-import-batch-persist/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

Pas de `contracts/` : aucun contrat externe (API/CLI) ne change — cf.
`data-model.md` § « Pas de contrats externes à documenter ».

### Source Code (repository root)

```text
backend/
├── app/
│   ├── services/
│   │   └── import_service.py       # _Persister — mise en lot (add/finalize)
│   ├── repositories/
│   │   └── athlete_repository.py   # nouvelle fonction : résolution par lot
│   └── services/
│       └── mapping.py              # inchangé (get_or_create_athlete, resolve_athlete restent les points d'entrée ligne à ligne pour les appelants hors _Persister)
└── tests/
    └── test_services/
        └── test_import_service.py  # tests de non-régression + comptage de requêtes
```

**Structure Decision** : projet web (backend + frontend), mais cette feature
ne touche que `backend/` — refactor interne à la couche `services/`, avec une
seule fonction nouvelle en couche `repositories/` (respect du Principe II :
seule cette couche touche `Session`). Aucun fichier `frontend/` concerné.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

Aucune violation — les six principes passent ✅ ou N/A (cf. Constitution
Check ci-dessus). Rien à consigner ici.
