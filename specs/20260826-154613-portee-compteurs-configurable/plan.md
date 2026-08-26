# Implementation Plan: Portée des compteurs configurable depuis le panel admin

**Branch**: `tjarrier/chore-admin-rendre-configurables-en-bdd-les-disc` | **Date**: 2026-08-26 | **Spec**: [spec.md](./spec.md)

**Issue**: [#95](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/95)

## Summary

Les deux ensembles qui décident de ce que l'application compte — les disciplines exclues des compteurs et les libellés reconnus comme libellés du club — passent de constantes Python à des lignes en base, éditables depuis le panel admin.

L'approche tient en une inversion. `core/club.py` et `core/discipline.py` gardent **la règle** (normalisation, égalité stricte, exclusion par défaut, clauses SQL) et perdent **les données** : celles-ci vivent dans un registre en mémoire, `core/counter_scope.py`, sans Session ni import de couche supérieure. C'est un service qui le **remplit** depuis la base — au démarrage de l'API, à l'entrée de la CLI, et après chaque écriture admin. Le sens du flux ne s'inverse jamais : `core/` n'appelle rien au-dessus de lui, il est appelé.

Le registre part des valeurs d'aujourd'hui. Une base neuve, une suite de tests, une CLI qui n'aurait pas chargé : le comportement est celui d'aujourd'hui, jamais un ensemble vide qui viderait silencieusement tous les compteurs du club.

Un seul stockage pour les deux listes (`counter_scope_entries`, discriminé par `kind`), un seul repository, un seul routeur admin, un seul écran. Les deux entrées ont la même forme — une chaîne dans un ensemble, avec sa provenance —, et les dédoubler à l'identique n'achèterait rien.

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript 5 / Next.js 16 App Router (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2, Alembic, Typer ; React 19, TanStack Query, Tailwind, shadcn/ui

**Storage**: PostgreSQL (Supabase) en production, SQLite en développement et en test. Une table nouvelle, `counter_scope_entries`, plus une migration Alembic qui l'amorce avec les valeurs aujourd'hui en dur.

**Testing**: pytest (`-m "not integration"`, aucun réseau), vitest côté front

**Target Platform**: API sur Render (un seul processus `uvicorn`, sans `--workers`), front sur Vercel

**Project Type**: application web, backend et frontend séparés

**Performance Goals**: aucune requête base par participation évaluée — le registre est lu en mémoire. Le classement d'une épreuve de 3 000 résultats ne se dégrade pas de plus de 5 % (SC-004).

**Constraints**:
- La normalisation des libellés **ne change pas** : l'index fonctionnel `ix_participations_club_normalized` (migration `e9cdbf3a4866`) fige l'expression SQL compilée au moment de sa construction. Toucher à `_normalise_sql` périmerait cet index en silence. La feature ne touche qu'à l'**ensemble** des libellés reconnus, jamais à la façon de les comparer — aucune migration de reconstruction d'index n'est donc requise, et c'est une frontière à ne pas franchir.
- Le verdict Python (`is_tcn`, `is_federal` — badge affiché, scrapers, DTO) et le verdict SQL (`tcn_clause`, `federal_clause` — compteurs, listes paginées) doivent rester d'accord pour **toute** configuration, pas seulement pour celle livrée.
- `ParticipationOut.is_tcn` est un champ calculé de DTO : il s'évalue **sans Session**. C'est cette contrainte qui interdit un chargement paresseux depuis la base et impose le registre en mémoire.

**Scale/Scope**: 9 disciplines exclues et 3 libellés de club aujourd'hui ; quelques dizaines d'entrées au grand maximum. Une poignée d'administrateurs, quelques modifications par an.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Passage explicite des 6 principes de `.specify/memory/constitution.md` (v1.1.1).

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Identifiants, colonnes, codes de pouvoir et noms de tests en anglais (`counter_scope_entries`, `CounterScopeEntry`, `counter_scope:manage`). Écran, libellés, messages d'erreur rendus à l'utilisateur et docstrings de règle métier en français. Les `DomainError` levées (libellé vide, doublon, liste vidée) sont sérialisées vers le front : messages **en français**, conformément à la clause « cas mixte ». |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | `core/` ne touche aucune Session et n'importe rien au-dessus de lui : le registre est **poussé** depuis `services/counter_scope.py`, qui lit via `repositories/counter_scope_repository.py`. La règle d'identification club reste dans `app/core/club.py` — un seul endroit, comme l'exige le principe. Le registre introduit toutefois de l'**état** dans `core/`, ce que la doctrine de `app/core/AGENTS.md` écarte pour `permissions.py` : consigné en Complexity Tracking. |
| III | TDD sans réseau (non-négociable) | ✅ | Test rouge d'abord à chaque étage. Le contrat existant (`tests/test_repositories/test_club_filter.py`) est étendu à une configuration **modifiée**, pas seulement à celle livrée. Aucun accès réseau. |
| IV | Contrats API et CLI stables | ✅ | Aucun endpoint `/api/v1` existant ne change de forme ni de sémantique. Trois routes nouvelles sous `/api/v1/admin/counter-scope`. `club-labels` garde sa charge `--json` inchangée. |
| V | Neutralité par défaut des paramètres transverses | ✅ | `federal_only` et `scope` gardent leur défaut neutre. La feature change ce que « fédéral » et « club » **désignent**, jamais quand le filtre s'applique. |
| VI | Simplicité / YAGNI | ✅ | Une table, un modèle, un repository, un service, un routeur, un écran. Pas de table de configuration générique clé/valeur, pas de propagation inter-processus, pas de recalcul de masse, pas d'historique de versions de configuration. |

## Project Structure

### Documentation (this feature)

```text
specs/20260826-154613-portee-compteurs-configurable/
├── plan.md              # Ce fichier
├── spec.md              # Spécification (/speckit-specify)
├── research.md          # Phase 0 — décisions et alternatives écartées
├── data-model.md        # Phase 1 — table, contraintes, amorçage
├── quickstart.md        # Phase 1 — comment vérifier de bout en bout
├── contracts/
│   └── admin-counter-scope.md   # Phase 1 — contrat des trois routes admin
├── checklists/
│   └── requirements.md  # Qualité de la spec
└── tasks.md             # Phase 2 (/speckit-tasks — pas créé ici)
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/
│   └── <rev>_counter_scope_entries.py        # table + amorçage des 12 valeurs
├── app/
│   ├── core/
│   │   ├── counter_scope.py                  # NOUVEAU — registre en mémoire, défauts, remplissage
│   │   ├── club.py                           # MODIFIÉ — lit le registre au lieu de TCN_CLUB_LABELS
│   │   ├── discipline.py                     # MODIFIÉ — lit le registre au lieu de NON_FEDERAL_TYPES
│   │   └── permissions.py                    # MODIFIÉ — P.COUNTER_SCOPE_MANAGE + FEATURE_COUNTER_SCOPE
│   ├── models/counter_scope_entry.py         # NOUVEAU
│   ├── repositories/counter_scope_repository.py  # NOUVEAU
│   ├── schemas/counter_scope.py              # NOUVEAU — DTO d'entrée et de sortie
│   ├── services/counter_scope.py             # NOUVEAU — chargement, validation, invalidation
│   ├── api/v1/admin_counter_scope.py         # NOUVEAU — GET / POST / DELETE
│   ├── api/v1/router.py                      # MODIFIÉ — montage derrière require_site_access
│   ├── main.py                               # MODIFIÉ — remplissage du registre au lifespan
│   ├── cli/__init__.py                       # MODIFIÉ — remplissage à l'entrée de la CLI
│   └── cli/commands/club_labels.py           # MODIFIÉ — se prononce selon la configuration
└── tests/
    ├── conftest.py                           # MODIFIÉ — fixture de remise à zéro du registre
    ├── club_corpus.py                        # CONSERVÉ — cas de référence, inchangé
    ├── test_repositories/test_club_filter.py # ÉTENDU — contrat éprouvé sur une config modifiée
    ├── test_core/test_counter_scope.py       # NOUVEAU
    ├── test_services/test_counter_scope.py   # NOUVEAU
    └── test_api/test_admin_counter_scope.py  # NOUVEAU

frontend/
├── app/admin/portee-compteurs/page.tsx       # NOUVEAU — écran
├── components/admin/CounterScopeCard.tsx     # NOUVEAU — une carte, montée deux fois
├── components/layout/nav.config.ts           # MODIFIÉ — entrée de navigation + pouvoir requis
└── lib/queries/admin.ts                      # MODIFIÉ — lecture et mutations

docs/
└── api/admin-donnees.md                      # MODIFIÉ — les trois routes nouvelles
```

**Structure Decision**: application web existante, backend `backend/` et frontend `frontend/`. Aucune arborescence nouvelle : la feature s'insère dans les dossiers en place, en suivant le patron déjà éprouvé par `site_access_config` (modèle → repository → service → routeur admin → carte front).

## Étapes d'implémentation

Chaque étape est livrable et vérifiable seule, dans cet ordre.

1. **Socle en base** — modèle `CounterScopeEntry`, migration Alembic, amorçage avec les 9 disciplines et 3 libellés d'aujourd'hui, repository. Vérifiable par `alembic upgrade head` sur une base vierge, puis lecture des 12 lignes.
2. **Registre et bascule des prédicats** — `core/counter_scope.py`, `core/club.py` et `core/discipline.py` qui le lisent, service de chargement. À ce stade le comportement est **strictement identique** : c'est ce que verrouille la suite existante, qui doit rester verte sans qu'une seule assertion change.
3. **Remplissage aux trois points d'entrée** — lifespan de l'API, entrée de la CLI, fixture de test. Vérifiable en modifiant une ligne en base à la main et en constatant l'effet sur `/api/v1/participations`.
4. **Écriture admin** — pouvoir, schémas, service de validation, trois routes, journal d'administration, invalidation du registre dans le même geste. C'est ici que se jouent FR-009 à FR-013.
5. **Écran d'administration** — carte réutilisée pour les deux listes, entrée de navigation, confirmation au retrait, explication de la règle. FR-014 à FR-017.
6. **Documentation et outillage** — `club-labels` aligné sur la configuration, `docs/api/admin-donnees.md`, `backend/AGENTS.md` et `backend/app/core/AGENTS.md` mis à jour là où ils décrivent les deux listes comme figées dans le code.

L'étape 2 est celle qui porte le risque : elle change ce que lisent les 29 sites d'appel des quatre prédicats, dans `app/`, sans devoir changer un seul comportement. La suite existante en est le juge.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| État mutable de processus dans `core/counter_scope.py`, là où `app/core/AGENTS.md` pose « aucun état » pour `permissions.py` | `ParticipationOut.is_tcn` est un champ calculé de DTO, évalué **sans Session** ; les scrapers appellent `is_tcn` ligne par ligne à l'intérieur d'un import. Une lecture base par appel est exclue (FR-006), et un passage de la configuration en paramètre toucherait les 29 sites d'appel. | Trois alternatives écartées, détaillées dans `research.md` §2 : (a) faire de la configuration un paramètre de `is_tcn`/`is_federal` — churn massif, et le DTO n'a personne pour la lui passer ; (b) placer le cache dans `services/` et le faire lire par `core/` — inverse le sens du flux, ce que le Principe II interdit frontalement ; (c) laisser `core/` ouvrir sa propre Session — nouvelle occurrence de Session hors `repositories/`, interdite par le Principe II. L'état poussé depuis le dessus est la seule forme qui garde toutes les flèches vers le bas. |
| Valeurs d'aujourd'hui conservées comme **défauts** du registre, en plus des lignes amorcées en base | Un registre non rempli — test, script, commande oubliée — rendrait un ensemble de libellés vide, donc zéro résultat du club et tous les compteurs du club à zéro, sans erreur ni avertissement. Le défaut fait que l'oubli dégrade vers le comportement d'aujourd'hui plutôt que vers le vide. | Lever une exception à la première lecture d'un registre vide a été écarté : `is_tcn` est appelé depuis un champ calculé de DTO, l'exception casserait le rendu d'une page de résultats pour un défaut de câblage. Un test vérifie que les défauts du code et les lignes amorcées par la migration coïncident, pour que les deux ne divergent pas. |
| Une table pour deux natures d'entrée, discriminée par `kind` | Les deux entrées ont exactement la même forme : une chaîne dans un ensemble, avec son auteur et sa date. Deux tables, deux modèles, deux repositories et deux routeurs pour la même forme est le doublon que le Principe VI écarte. | Deux tables distinctes rejetées : rien ne les distingue structurellement, et le jour où les formes divergeraient réellement, séparer une table de douze lignes est un geste sans risque. Une table de configuration générique clé/valeur également rejetée, à l'opposé : elle perdrait la contrainte d'unicité par nature et la validation par nature. |
