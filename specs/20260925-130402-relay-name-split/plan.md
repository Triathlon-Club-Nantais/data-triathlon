# Implementation Plan: Découper à l'import les relais qui nomment leurs équipiers

**Branch**: `895-relay-name-split` | **Date**: 2026-09-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/20260925-130402-relay-name-split/spec.md`

**Sondage** : `docs/superpowers/specs/2026-09-25-relais-noms-equipiers-sondage.md` (prime).

## Summary

Une ligne de relais qui nomme chaque équipier par un nom et un prénom, séparés par `/`,
est découpée à l'import : le résultat est rattaché à chaque équipier par la composition
de #894 (`participation_teammates`), sans fiche au nom de l'équipe. Une fonction pure,
`split_relay_teammates` (`app/scrapers/utils.py`), décide tout ou rien par ligne à partir
de la valeur publiée reconstituée (`nom + prénom`). `_Persister`
(`app/services/import_service.py`) l'applique aux lignes relais, dans sa résolution par
lot, à l'import comme au rescrape. Aucun scraper, aucun schéma, aucun contrat d'API ne
change.

## Technical Context

**Language/Version**: Python 3.13 (backend seul)

**Primary Dependencies**: SQLAlchemy 2.0 (sync), aucune nouvelle dépendance

**Storage**: PostgreSQL (prod), SQLite (dev) ; tables existantes `participations`,
`participation_teammates`, `athletes`. Aucune migration.

**Testing**: pytest sans réseau, fixtures existantes de `backend/tests/fixtures`

**Target Platform**: backend FastAPI (Render), CLI `rescrape-db` / `import-sheet`

**Project Type**: web-service (le front de #894 affiche déjà `team_name` et les équipiers)

**Performance Goals**: conserver la résolution par lot de #706 : pas de requête par ligne
ajoutée ; les liaisons d'équipiers des participations neuves sont créées dans le même
`flush` que les participations.

**Constraints**: tout ou rien par ligne ; jamais de découpage hors relais ; idempotence
au rescrape ; composition manuelle jamais retouchée.

**Scale/Scope**: base de dev : 180 lignes découpables sur 1 041 relais ; oktime, 347
lignes de ce type sur le panel de son design. Production non mesurée.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Passage explicite des 6 principes de `.specify/memory/constitution.md` (v1.2.0).

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Identifiants et tests en anglais (`split_relay_teammates`, `teammate_ids`) ; commentaires de règle métier en français ; `import_service.py` reste français dans le patch (fix ciblé, règle de transition). |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | Règle pure dans `scrapers/utils.py` ; orchestration dans `_Persister` ; création des liaisons dans `participation_repository.create_batch`, recherche et purge dans `athlete_repository`. Aucune requête construite en service. |
| III | TDD sans réseau (non-négociable) | ✅ | Tests de la règle d'abord (valeurs réelles), puis tests `_Persister` et scraper → import sur fixtures fichiers. Aucun appel réseau. |
| IV | Contrats API et CLI stables | ✅ | Aucun champ ajouté ni retiré ; `Reassignment` (gelé) non utilisé pour le découpage ; compteurs du rapport CLI de mêmes clés. |
| V | Neutralité par défaut des paramètres transverses | N/A | Aucun paramètre de lecture touché. |
| VI | Simplicité / YAGNI | ✅ | Un point d'application pour 14 fournisseurs, pas de convention par fournisseur (aucune donnée ne l'exige, research R1 et R3), `/` seul. |

**Re-check post-design** : inchangé, aucune ligne en Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/20260925-130402-relay-name-split/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── relay-teammates-rule.md
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── scrapers/utils.py                     # + split_relay_teammates (règle pure)
│   ├── services/import_service.py            # _PendingResolution.teammates, add(), _resolve_pending()
│   └── repositories/participation_repository.py  # create_batch : clé teammate_ids
└── tests/
    ├── test_scrapers_utils.py                # règle sur valeurs réelles du sondage
    ├── test_services/test_import_service.py  # import, rescrape, reprise, gardes
    ├── test_repositories/test_participation_repository.py  # create_batch + teammate_ids
    ├── test_oktime.py / test_chronoplace.py  # fixture → import découpé
    └── test_chronoweb.py / test_sporthive.py # fixture → import non découpé

backend/app/scrapers/AGENTS.md                # une ligne : les relais nommés se découpent à l'import
docs/modele-donnees.md                        # une composition peut venir de l'import
```

**Structure Decision**: backend seul. Le front de #894 affiche déjà le nom d'équipe et
les équipiers d'un résultat composé ; il n'a pas à distinguer une composition posée à
l'import d'une composition posée à la main.

## Design

Détail et alternatives : `research.md` (R1 à R8). Règle : `contracts/relay-teammates-rule.md`.
États : `data-model.md`.

1. **Règle** (`split_relay_teammates`) : listes parallèles (timepulse) ou segments
   `NOM Prénom` / `NOM PRÉNOM` à deux jetons (klikego, oktime, chronoplace) ; tout le reste
   rend `None`.
2. **`add()`** : les chemins de #997 (dossard apparié à un relais composé, relais sans
   dossard retrouvé par nom d'équipe) restent en tête et inchangés. Sinon, pour
   `scraped.is_relay`, calcul des équipiers proposés, portés par `_PendingResolution`.
   Une ligne découpée n'est jamais soumise à `_reconcile_blocked` (l'identité d'équipe
   n'est pas réconciliée).
3. **`_resolve_pending()`** : recherche par lot des identités d'équipe **et** des
   équipiers ; création par lot des équipiers manquants (nom, prénom seuls), jamais de
   l'identité d'équipe d'une ligne découpée ; garde FR-010 sur un index mémoire des
   athlètes déjà présents sur la course (porteurs et équipiers, tenu à jour dans le lot) ;
   reprise d'un résultat existant (`replace_teammates` + porteur + `team_name`) ou
   création (`create_batch` avec `teammate_ids`) ; purge par lot des anciennes fiches
   d'équipe (`delete_orphans_among`).
4. **Retour au chemin d'aujourd'hui** quand la garde FR-010 refuse : la ligne est
   traitée exactement comme une ligne non découpée (identité d'équipe résolue ou créée).

## Risques

- **Ordre « PRÉNOM NOM » en majuscules** chez un fournisseur non mesuré : équipiers au
  nom et au prénom inversés. Aucune occurrence mesurée ; la règle est documentée pour
  qu'un sondage ultérieur la corrige.
- **Production non mesurée** : les volumes découpés en prod sont inconnus (accès refusé
  pendant le sondage). Le premier rescrape d'une épreuve klikego ou oktime en prod
  découpera ses relais nommés et purgera les fiches d'équipe vidées.
- **Relais « Prénom NOM » découpés par `split_athlete_name`** (raceresult sans `&`,
  t2area) : la reconstitution est réordonnée, la règle les rejette. Ils restent des fiches
  d'équipe, comme aujourd'hui.

## Complexity Tracking

Aucune violation.
