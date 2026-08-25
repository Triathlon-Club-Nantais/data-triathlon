# Implementation Plan: la page épreuve — répartitions honnêtes, synthèses navigables, temps douteux signalés

**Branch**: `feat/486-page-epreuve` | **Date**: 2026-08-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/20260825-114345-page-epreuve-syntheses/spec.md`

## Summary

Trois entrées de l'audit UI/UX sur un même écran, `/courses/[id]` : ses cartes de synthèse
mentent par omission (`RES-7`), présentent des temps impossibles sur le même ton que les
justes (`RES-10`), et ne mènent nulle part (`RES-11`).

L'approche technique tient en une phrase : **le serveur publie ce que l'écran ne peut pas
calculer, l'écran ne fait que le rendre visible.** Quatre champs additifs sur deux DTO de
lecture, deux paramètres de requête facultatifs, et le reste est du rendu.

Le sondage `docs/superpowers/specs/2026-08-25-ecart-inters-total-sondage.md` a réécrit la
partie `RES-10` avant tout code : le seuil de 2 % proposé par l'audit signalerait 8 % du
classement, dont 285 lignes d'une épreuve saine. Il est remplacé par un signal à deux
niveaux, calé sur mesure. **Ce sondage prime sur ce plan.**

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript 5 strict (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 sync, Pydantic v2 ; Next.js 16 App
Router, Tailwind, shadcn/ui, d3-scale (déjà présent, utilisé par `CategoryBars`)

**Storage**: PostgreSQL (Supabase) en prod, SQLite en dev. **Aucune migration Alembic** —
ce lot ne touche aucun modèle, uniquement des agrégats calculés à la lecture.

**Testing**: pytest (`-m "not integration"`, 4 workers), vitest (`npm test`), ruff, ESLint

**Target Platform**: navigateur (mobile compris — l'audit insiste sur le parent qui
consulte au téléphone), API Linux/Render

**Project Type**: application web à deux applications (`backend/` + `frontend/`)

**Performance Goals**: aucune requête supplémentaire. Les deux agrégats nouveaux se
calculent dans la boucle existante de `stats_service.course_summary`, qui lit déjà toutes
les lignes de l'épreuve ; les deux colonnes de fiabilité s'ajoutent à un `SELECT` déjà
groupé par `Course.id`.

**Constraints**: `/api/v1` est publiée et le Principe IV interdit de la modifier
silencieusement — **tout ajout est additif, tout défaut est neutre**. L'identité visuelle
(`--tcn-*`, Anton/Barlow) et la frontière `components/tcn/` vs `components/ui/` ne sont pas
rejugées (#325, rappelé par #460).

**Scale/Scope**: un écran public et sa liste amont. Base de dev sondée : 72 épreuves,
11 629 participations, 4 150 lignes évaluables pour la règle d'écart, 123 codes de
catégorie distincts, 1 393 clubs distincts.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Identifiants nouveaux en anglais (`split_gap_ratio`, `split_gap_median`, `clubs_total`, `club`, `category`) ; libellés, marqueurs et infobulles en français ; le sondage et la spec en français. |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | Les deux filtres s'ajoutent à `participation_repository` (seule couche à toucher `Session`) ; les deux agrégats à `stats_service`. Aucun calcul métier ne monte dans le router ni ne descend dans le front — c'est précisément l'objet de R2. |
| III | TDD sans réseau (non-négociable) | ✅ | Chaque tâche d'implémentation est précédée de son test. Aucun accès réseau : les fixtures existantes de `backend/tests/` et des composants suffisent. Le cas de la course 214 est figé en fixture (`SC-004`). |
| IV | Contrats API et CLI stables | ✅ | Quatre champs **ajoutés** à `CourseSummary`, `ParticipationOut` et `EventOut` ; deux paramètres de requête **facultatifs**. Aucun champ retiré, aucune sémantique inversée, aucun code de retour modifié. `SC-010` le vérifie. |
| V | Neutralité par défaut des paramètres transverses | ✅ | `club=None` et `category=None` ne filtrent rien. C'est l'écran qui les active en écrivant l'URL, jamais l'API. |
| VI | Simplicité / YAGNI | ⚠️ | Le schéma de segments par sport est dupliqué en Python. Voir Complexity Tracking. |

## Project Structure

### Documentation (this feature)

```text
specs/20260825-114345-page-epreuve-syntheses/
├── plan.md              # Ce fichier
├── spec.md              # Phase -1 (/speckit-specify)
├── research.md          # Phase 0 — six inconnues tranchées
├── data-model.md        # Phase 1 — les quatre champs et les deux règles
├── quickstart.md        # Phase 1 — comment vérifier que ça marche
├── contracts/
│   └── api-lecture.md   # Phase 1 — le delta de contrat /api/v1
├── checklists/
│   └── requirements.md  # Qualité de la spec
└── tasks.md             # Phase 2 (/speckit-tasks — PAS créé ici)
```

Point de vérité hors de ce dossier, et qui prime sur lui :
`docs/superpowers/specs/2026-08-25-ecart-inters-total-sondage.md`.

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/v1/courses.py                    # + params club/category sur GET /courses/{id}
│   ├── schemas/course.py                    # + clubs_total, split_gap_median (CourseSummary)
│   │                                        # + is_reliable, quality_issues (EventOut)
│   ├── schemas/participation.py             # + split_gap_ratio (ParticipationOut)
│   ├── services/stats_service.py            # calcul des deux agrégats + _event_row
│   ├── services/split_gap.py                # NOUVEAU — la règle d'écart, en un seul endroit
│   └── repositories/participation_repository.py  # filtres club/category, colonnes fiabilité
└── tests/
    ├── test_services/test_split_gap.py      # NOUVEAU — dont la fixture course 214
    ├── test_api/test_courses_api.py         # filtres, additivité du contrat
    └── fixtures/                            # ligne 214 figée

frontend/
├── app/(public_restricted)/courses/[id]/page.tsx   # marque épreuve, cartes, liens
├── components/charts/CategoryBars.tsx              # part « Autres », barres activables
├── components/results/RaceFinishers.tsx            # marqueur de ligne, repères, états vides
├── components/results/EventList.tsx                # marque de fiabilité en liste
├── components/courses/ClubBreakdown.tsx            # NOUVEAU — carte clubs extraite
├── lib/categories.ts                               # NOUVEAU — libellés de catégorie
├── lib/quality.ts                                  # phrases d'anomalie (existant, réutilisé)
└── lib/types.ts                                    # miroir TS des quatre champs
```

**Structure Decision** : les deux applications existantes, sans nouveau module de premier
niveau. Deux fichiers naissent, et chacun pour une raison nommée. `app/services/split_gap.py`
isole la règle d'écart pour qu'elle ait **un seul** domicile (R2, et la leçon de #76).
`components/courses/ClubBreakdown.tsx` extrait la carte « Top clubs » aujourd'hui écrite
en JSX inline dans `page.tsx:108-127` : elle gagne un pied, un en-tête conditionnel et des
lignes activables, ce qui la rend intestable là où elle est.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Principe VI — le schéma de segments par sport (5 listes de clés) est dupliqué en Python alors qu'il existe déjà en TypeScript (`frontend/lib/utils/splits.ts`) | La règle d'écart doit vivre **d'un seul côté** (R2), et ce côté est le serveur : la médiane porte sur l'épreuve entière, hors de portée d'un écran qui reçoit vingt lignes. Sommer les inters exige de savoir lesquels sommer, donc le schéma suit la règle. | Laisser le front calculer l'écart de chaque ligne et le back seulement la médiane économisait la duplication — et recréait exactement #76 : deux implémentations de la même règle, chacune libre de sommer un ensemble de segments différent, jusqu'à ce qu'elles divergent en silence. La duplication retenue est **inerte** (cinq listes de constantes, aucune logique) et couverte par un test qui compare les deux tables. |

## Phase 1 — l'ordre de livraison

Trois tranches, alignées sur les trois histoires de la spec, chacune livrable seule.

**P1 — la fiabilité affichée** (`US1`, la seule à fort impact). Backend d'abord :
`services/split_gap.py` et ses tests, puis les trois champs publiés, puis les deux
colonnes de `EventOut`. Front ensuite : marque en tête de page, marqueur de ligne, marque
en liste. Se vérifie sans que P2 ni P3 existent.

**P2 — la franchise des répartitions** (`US2`). `clubs_total` au serveur, puis la part
« Autres », le pied « et N autres clubs », l'en-tête conditionnel et les titres de portée.
N'a besoin de rien de P1.

**P3 — les synthèses navigables** (`US3`, la seule à toucher les deux couches en
profondeur). Les deux filtres au repository puis au router, la table de libellés, et enfin
les cartes activables avec leurs repères. Se pose sur les repères de sélection déjà
livrés par le lot #485 — il les étend, il ne les réécrit pas.

L'ordre inverse serait tentant (P2 est le moins cher) mais `RES-10` est la seule entrée à
fort impact des trois, et c'est elle qui décide si le produit est crédible.
