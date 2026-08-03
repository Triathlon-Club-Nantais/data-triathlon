# Implementation Plan: Pagination et recherche du classement d'une épreuve

**Branch**: `fix-course-mettre-en-place-une-pagination-pour-v` | **Date**: 2026-08-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/20260803-195212-course-pagination/spec.md`

## Summary

La page d'épreuve télécharge aujourd'hui l'intégralité du classement — plus de
2500 lignes sur `/courses/25` — pour en dériver, **en JavaScript**, six blocs de
statistiques et le tableau. On coupe cette dépendance en deux : le backend
calcule les agrégats et les expose sur une route de synthèse dédiée, et le
classement devient une tranche de 20 lignes ordonnée, filtrable et cherchable
côté serveur.

Le point non-évident du chantier n'est pas la pagination : c'est que **l'ordre
d'affichage vit en JavaScript** (`orderParticipations`) pendant que la requête
trie sur `rank_overall` seul. Invisible tant que tout arrivait d'un coup ; dès
qu'on découpe, la tranche N servie n'est plus la tranche N attendue. L'ordre
descend donc en SQL et devient la seule définition.

Deux points ont été arbitrés en dehors du code :

- la pagination est le **défaut**, assortie d'une échappatoire explicite
  `page_size=all` — le comportement d'hier reste atteignable, il n'est plus
  subi ;
- la recherche est rendue **insensible aux accents**, ce qu'aucun des deux
  moteurs ne fait nativement (mesuré, cf. `research.md` R2). C'est le seul
  élément de la feature qui ajoute une dépendance d'infrastructure.

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript 5 / Node (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2, Alembic ; Next.js 16.2 (App Router), React 19, Tailwind, shadcn/ui

**Storage**: PostgreSQL (Supabase) en production, SQLite en développement et en tests. Aucune table modifiée ; une migration, sans DDL de table (`CREATE EXTENSION unaccent`)

**Testing**: pytest (`-m "not integration"`, sans réseau), ruff ; Vitest + Testing Library, ESLint, `next build`

**Target Platform**: backend sur Render (conteneur Linux), frontend sur Vercel

**Project Type**: application web, deux briques (`backend/` + `frontend/`)

**Performance Goals**: la charge transportée au premier affichage d'une épreuve de 2500 participations passe de l'intégralité du classement à une synthèse et 20 lignes (SC-001). Aucun objectif de latence n'est fixé : la feature retire du travail, elle n'en ajoute pas sur le chemin nominal

**Constraints**: ordre du classement identique, ligne pour ligne, à celui d'aujourd'hui (SC-003) ; blocs de statistiques identiques valeur pour valeur (SC-002) ; agrégation portable SQLite / PostgreSQL

**Scale/Scope**: plus grosse épreuve connue ≈ 2500 participations ; 2 routes, 1 repository, 1 service, 1 schéma, 1 migration côté backend ; 1 page, 1 composant, 1 client d'API côté frontend

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Passage explicite des 6 principes de `.specify/memory/constitution.md` (v1.1.0).

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Identifiants, tests et docstrings techniques en anglais (`page_size`, `split_keys`, `course_summary`) ; libellés d'écran, messages d'erreur affichés et commentaires de règle métier en français. Aucun identifiant français ajouté. |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | Les deux nouvelles fonctions de requête vont dans `participation_repository` — seule couche qui touche la `Session`. L'agrégation va dans `stats_service`. Les routers valident et délèguent. Aucun flux inverse. |
| III | TDD sans réseau (non-négociable) | ✅ | Toute la logique ajoutée (ordre SQL, résolution de `page_size`, agrégation, déaccentuation) est testable hors réseau. Les tâches de test précèdent leurs tâches d'implémentation dans `tasks.md`. |
| IV | Contrats API et CLI stables | ⚠️ | `GET /courses/{id}` change de comportement par défaut. Justifié ci-dessous. |
| V | Neutralité par défaut des paramètres transverses | ✅ | `scope` et `q` sont absents par défaut, donc non filtrants. `page_size` n'est pas un paramètre transverse mais une taille de tranche, comme sur `/courses` (50) et `/courses/events` (30). |
| VI | Simplicité / YAGNI | ⚠️ | La déaccentuation ajoute une dépendance d'infrastructure. Justifiée ci-dessous. |

Un principe en ⚠️ doit être justifié dans « Complexity Tracking » ci-dessous
avec l'alternative rejetée et la raison.

### Re-vérification après Phase 1

Les artefacts de conception ne déplacent aucun statut. Deux points confirmés :

- la synthèse **ne prend aucun paramètre** (`contracts/courses-api.md`), ce qui
  clôt tout risque sur le Principe V — il n'y a pas de défaut à choisir ;
- aucun schéma existant n'est modifié (`data-model.md`), `ParticipationOut` est
  réutilisé tel quel : le Principe IV n'est engagé que sur la pagination, pas
  sur la forme des lignes.

## Project Structure

### Documentation (this feature)

```text
specs/20260803-195212-course-pagination/
├── plan.md              # Ce fichier
├── spec.md              # Exigences (30 FR, 7 SC)
├── research.md          # Phase 0 — 6 sujets, mesures à l'appui
├── data-model.md        # Phase 1 — champs lus, formes de sortie
├── quickstart.md        # Phase 1 — 10 scénarios de validation
├── contracts/
│   └── courses-api.md   # Phase 1 — les deux routes + le contrat d'URL
├── checklists/
│   └── requirements.md  # Qualité de la spec
└── tasks.md             # Phase 2 — produit par /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/
│   └── <rev>_create_unaccent_extension.py   # NOUVEAU — pas de DDL de table
├── app/
│   ├── api/v1/courses.py                    # MODIFIÉ — pagination + route summary
│   ├── core/
│   │   ├── database.py                      # MODIFIÉ — UDF `unaccent` sur SQLite
│   │   └── text.py                          # NOUVEAU — déaccentuation Python (une fonction)
│   ├── repositories/participation_repository.py  # MODIFIÉ — tranche ordonnée + lignes de synthèse
│   ├── schemas/course.py                    # MODIFIÉ — CourseParticipationPage, CourseSummary
│   └── services/stats_service.py            # MODIFIÉ — course_summary()
└── tests/
    ├── test_api/test_courses_api.py         # NOUVEAU
    ├── test_repositories/test_participation_repository.py  # MODIFIÉ — ordre, tranche, recherche
    └── test_services/test_stats_service.py  # MODIFIÉ — agrégats de synthèse

frontend/
├── app/courses/[id]/
│   ├── page.tsx                             # MODIFIÉ — searchParams, blocs depuis la synthèse
│   └── page.test.tsx                        # NOUVEAU
├── components/results/
│   ├── RaceFinishers.tsx                    # MODIFIÉ — perd tri et filtre locaux, gagne recherche + pagination
│   └── RaceFinishers.test.tsx               # MODIFIÉ — existe déjà
├── lib/api/
│   ├── server.ts                            # MODIFIÉ — getCourse(id, opts), getCourseSummary(id)
│   └── client.ts                            # MODIFIÉ — idem
├── lib/types.ts                             # MODIFIÉ — CourseDetail, CourseSummary
└── lib/utils/raceOrder.ts                   # MODIFIÉ — orderParticipations retiré, countOutcomes conservé
```

**Structure Decision** : deux briques existantes, aucune nouvelle. Un seul
fichier créé côté backend hors tests et migration (`core/text.py`, une fonction
de déaccentuation) : il est appelé à la fois par le listener SQLite de
`database.py` et par le repository pour déaccentuer le terme cherché, et
l'inscrire dans l'un des deux créerait une dépendance en travers des couches.

## Notes d'implémentation

Ce que le code seul ne dira pas.

### L'ordre en SQL est gardé par `CASE`, pas par `NULLS LAST`

SQLite place les `NULL` en tête en tri croissant, PostgreSQL en queue : un
`ORDER BY col` nu diverge entre développement et production. Les clés de tri
« valeur absente » sont donc des booléens 0/1, procédé déjà employé par
`list_for_course`. Expression complète : `research.md`, R1.

**Limite assumée** : le départage final par nom utilise la collation de la base,
là où le JavaScript utilisait `localeCompare`. L'écart n'est observable qu'entre
deux lignes partageant le groupe **et** le rang (ou le temps).

### `orderParticipations` doit disparaître, pas seulement cesser d'être appelée

La laisser en place garantit qu'un futur écran la rappellera sur une tranche
paginée, ce qui retrierait 20 lignes dans le vide — un bug silencieux. Le tri
est désormais une propriété de la requête. `countOutcomes` et `isNonFinisher`,
eux, restent : ils servent toujours.

### La synthèse ne prend aucun paramètre, et c'est structurant

Ni `q`, ni `scope`, ni pagination. C'est ce qui garantit qu'une recherche ne
fera pas tomber l'histogramme à une barre (FR-018). Le jour où quelqu'un
voudra une synthèse filtrée, ce sera une autre route ou un autre paramètre
explicite — jamais un glissement du défaut.

### Une seule requête pour la synthèse, agrégée en Python

Six colonnes lues, pas d'objets ORM, pas de `joinedload`. Ce n'est pas de la
paresse face à `GROUP BY` : l'histogramme n'a pas d'expression SQL portable
(les temps sont des chaînes `HH:MM:SS`), et `is_tcn` est une liste blanche
Python, pas un prédicat SQL simple. Détail : `research.md`, R4.

### La déaccentuation a deux implémentations, une seule est testée

SQLite reçoit une fonction Python enregistrée à la connexion ; PostgreSQL
utilise l'extension `unaccent`. La suite de tests tourne sur SQLite : le chemin
de production n'est couvert par aucun test. D'où l'étape 10 de `quickstart.md`,
qui est une **obligation** avant de clore la branche, pas une suggestion — sur
Supabase les extensions vivent conventionnellement dans le schéma `extensions`,
et un `search_path` incomplet fait échouer `unaccent(...)` en production alors
que tout passe en développement.

### La recherche n'a pas de debounce

C'est le patron du projet (`ResultsFilters.tsx`) : saisie locale, application
sur `Entrée`. Plus simple qu'un debounce, et une requête par recherche au lieu
d'une par frappe.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| **Principe IV** — `GET /courses/{id}` change de comportement par défaut (rendait tout, rend 20) sans ouvrir de `/api/v2` | C'est l'objet même de l'issue #163. Laisser le défaut sur « tout rendre » n'aurait résolu le problème que pour l'appelant qui pense à demander autre chose — or l'appelant à corriger, c'est nous. | **Défaut neutre** (paginer seulement sur demande) : le chemin lourd serait resté le défaut, donc le premier écran oublié l'aurait repris. **Ouvrir `/api/v2`** : le dépôt n'a aucune v2 amorcée ; en créer une pour une route obligerait à maintenir deux surfaces pour un changement dont le seul consommateur recensé est notre propre frontend. Le principe est **soldé, pas contourné** : `page_size=all` (FR-006) laisse le comportement d'hier accessible à qui le demande — rien de ce que la route rendait ne devient inatteignable, ce qui la distingue de la « modification silencieuse » que le principe vise. |
| **Principe VI** — la recherche insensible aux accents ajoute une extension PostgreSQL, une migration, une fonction Python et un listener | Arbitré explicitement le 2026-08-03 après mesure. Sur un club français, les noms accentués sont la norme (`LEMÉE`, `PLÉNEUF`) et la recherche est le seul moyen d'atteindre une ligne au-delà de la page 1. | **Aligner la spec sur l'existant** (casse seule, comme `/athletes?name=`) : coût nul, mais la recherche aurait manqué les noms accentués sans que rien ne le signale — le défaut le plus coûteux étant celui qui rend zéro résultat en silence. **Étendre à tout le site** : élargit le périmètre de #163 à toutes les recherches par nom ; à traiter dans son propre ticket. Le surcoût est borné : ~30 lignes, une migration sans DDL de table, aucun coût en performance (le filtre porte toujours sur une seule épreuve). |
