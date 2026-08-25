---

description: "Tâches d'implémentation — la page épreuve (lot #486)"
---

# Tasks: la page épreuve — répartitions honnêtes, synthèses navigables, temps douteux signalés

**Input**: `specs/20260825-114345-page-epreuve-syntheses/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/api-lecture.md](./contracts/api-lecture.md),
[quickstart.md](./quickstart.md)

**Point de vérité, et il prime sur tout ce fichier** :
`docs/superpowers/specs/2026-08-25-ecart-inters-total-sondage.md`. Les seuils de `US1` en
viennent ; toute divergence se tranche en re-sondant, pas en arbitrant ici.

**Tests** : le Principe III de la constitution est **non-négociable** — TDD sans réseau.
Chaque story porte ses tâches de test, écrites **avant** l'implémentation et vérifiées
rouges. Aucune dérogation n'est demandée dans le §Complexity Tracking du plan.

## Format: `[ID] [P?] [Story] Description`

- **[P]** : parallélisable — fichier distinct, aucune dépendance sur une tâche incomplète
- **[Story]** : `US1`, `US2`, `US3`

## Path Conventions

Application web à deux applications : `backend/app/`, `backend/tests/`, `frontend/`.
Aucune migration Alembic dans ce lot.

---

## Phase 1: Setup

**Purpose**: le seul intrant que les trois stories partagent — un relevé, pas du code.

- [x] T001 Relever depuis `backend/triathlon.db` les codes de catégorie distincts avec leur fréquence, et les identifiants d'épreuve témoins (au moins une à médiane d'écart > 1 %, une à médiane nulle, une sans club renseigné, une à plus de 8 catégories), et consigner le relevé dans `specs/20260825-114345-page-epreuve-syntheses/releve-donnees.md`

**Checkpoint**: les trois stories ont leurs cas de test réels, pas inventés.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: le seul point de contention entre les trois stories.

**⚠️ CRITIQUE**: `frontend/lib/types.ts` est touché par les trois stories. Déclarer les
six champs d'un coup évite un conflit à trois sur un fichier de types.

- [x] T002 Déclarer les six champs publiés dans `frontend/lib/types.ts` — `split_gap_ratio` sur `Participation`, `clubs_total` et `split_gap_median` sur `CourseSummary`, `is_reliable` et `quality_issues` sur `EventOut` — tous optionnels/nullables, conformément à `contracts/api-lecture.md`

**Checkpoint**: fondation prête — les trois stories peuvent démarrer.

---

## Phase 3: User Story 1 - Le lecteur voit qu'un chiffre est douteux avant de s'y fier (Priority: P1) 🎯 MVP

**Goal**: l'écran dit ce qu'il sait — une marque « données douteuses » sur la page épreuve
et dans la liste, un signal d'épreuve quand les inters ne couvrent pas tout le parcours, et
un marqueur de ligne réservé aux lignes qui s'écartent de leurs voisines.

**Independent Test**: sur une épreuve à anomalies et une épreuve saine, sans que `US2` ni
`US3` existent. Se vérifie par le § `US1` de [quickstart.md](./quickstart.md).

### Tests for User Story 1

> **Écrire ces tests D'ABORD, vérifier qu'ils ÉCHOUENT avant toute implémentation**
> (Principe III, non-négociable).

- [x] T003 [P] [US1] Test de l'évaluabilité d'une ligne — les cinq conditions cumulatives de `data-model.md` § 2, chacune rendant `None` — dans `backend/tests/test_core/test_split_gap.py`
- [x] T004 [US1] Test de captation : figer la ligne de tête de la course 214 (31 s + 34 s + 19 min 18 s pour 01:06:18, soit 69,3 %) en fixture et vérifier qu'elle est évaluée et signalée, dans `backend/tests/test_core/test_split_gap.py` (dépend de T003)
- [x] T005 [US1] Test du signe : un écart positif (segment non publié) et un écart négatif se distinguent, dans `backend/tests/test_core/test_split_gap.py` (dépend de T003)
- [x] T006 [P] [US1] Test de la médiane d'épreuve — `split_gap_median` sur une épreuve à lignes évaluables, `None` sur une épreuve de relais et sur une épreuve sans splits — dans `backend/tests/test_services/test_participation_stats_service.py`
- [x] T007 [P] [US1] Test du croisement des deux tables de schémas de segments, dans `backend/tests/test_core/test_split_gap.py` : lire `frontend/lib/utils/splits.ts` depuis le test (chemin résolu par `Path(__file__).parents[3] / "frontend/lib/utils/splits.ts"`), en extraire les entrées `SCHEMAS` par expression régulière sur `key: "…"`, et asserter l'égalité **stricte** — mêmes noms de schéma, mêmes clés, même ordre — avec la table Python. Le test **échoue** si le fichier est introuvable : c'est la garde qui justifie la dérogation au Principe VI, elle ne se saute pas. Aucun accès réseau, aucune dépendance de production sur le front.
- [x] T008 [P] [US1] Test API : `split_gap_ratio` publié par participation et `split_gap_median` par synthèse, `null` quand non évaluable, dans `backend/tests/test_api/test_courses_api.py`
- [x] T009 [US1] Test API : `EventOut` porte `is_reliable` et `quality_issues`, y compris `null`, dans `backend/tests/test_api/test_courses_api.py` (même fichier que T008)
- [x] T010 [P] [US1] Test repository : la requête agrégée d'épreuves rend les deux colonnes de fiabilité **sans** placer `quality_issues` dans le `GROUP BY`, dans `backend/tests/test_repositories/test_participation_repository.py`
- [x] T011 [P] [US1] Test composant : l'en-tête de `/courses/[id]` porte la marque « données douteuses » sur une épreuve à anomalies, rien sur une épreuve saine, et le signal d'épreuve quand `split_gap_median` dépasse 1 %, dans `frontend/app/(public_restricted)/courses/[id]/page.test.tsx`
- [x] T012 [P] [US1] Test composant : une ligne s'écartant de plus de 5 % de la médiane porte le marqueur, une ligne conforme n'en porte pas, aucune ligne n'est marquée sous 10 lignes évaluables ou sous 60 s d'écart, **et les temps rendus valent exactement ceux fournis — marqueur présent ou non** (`FR-009` : le marqueur informe, il ne réécrit pas la donnée), dans `frontend/components/results/RaceFinishers.test.tsx`
- [x] T013 [P] [US1] Test composant : une ligne d'épreuve à anomalies porte la marque, avec le même vocabulaire que le profil athlète, dans `frontend/components/results/EventList.test.tsx`

### Implementation for User Story 1

- [x] T014 [US1] Créer `backend/app/services/split_gap.py` — les cinq schémas de segments par sport, la règle d'évaluabilité et le calcul de l'écart signé, avec la docstring qui nomme le sondage comme point de vérité (rend T003, T005, T007 verts)
- [x] T015 [US1] Calculer `split_gap_ratio` par ligne et `split_gap_median` par épreuve dans `backend/app/services/stats_service.py`, dans la boucle existante de `course_summary` (rend T006 vert)
- [x] T016 [P] [US1] Ajouter `split_gap_ratio: float | None` à `ParticipationOut` dans `backend/app/schemas/participation.py`
- [x] T017 [P] [US1] Ajouter `split_gap_median: float | None` à `CourseSummary` et `is_reliable` / `quality_issues` à `EventOut` dans `backend/app/schemas/course.py`
- [x] T018 [US1] Ajouter les deux colonnes de fiabilité au `SELECT` de `_grouped_events_query` — et **pas** au `GROUP BY`, la dépendance fonctionnelle à `Course.id` suffisant et PostgreSQL n'ayant pas d'opérateur d'égalité sur `json` — dans `backend/app/repositories/participation_repository.py` (rend T010 vert)
- [x] T019 [US1] Reporter les deux colonnes dans `_event_row` de `backend/app/services/stats_service.py` (rend T009 vert, dépend de T018)
- [x] T020 [P] [US1] Créer le composant de marque de fiabilité, réutilisant `describeQualityIssues` de `frontend/lib/quality.ts` et le patron `role="img"` + `title` + `aria-label` de `CelluleInter`, dans `frontend/components/results/ReliabilityMark.tsx`
- [x] T021 [US1] Rendre la marque et le signal d'épreuve dans l'en-tête de `frontend/app/(public_restricted)/courses/[id]/page.tsx` (rend T011 vert, dépend de T020)
- [x] T022 [US1] Poser le marqueur de ligne dans `frontend/components/results/RaceFinishers.tsx`, avec les trois gardes du sondage — écart à la médiane > 5 %, épreuve ≥ 10 lignes évaluables, ≥ 60 s (rend T012 vert)
- [x] T023 [US1] Rendre la marque sur les lignes de `frontend/components/results/EventList.tsx` (rend T013 vert, dépend de T020)

**Checkpoint**: `US1` est complète et vérifiable seule. Le produit dit quand douter.

---

## Phase 4: User Story 2 - Les répartitions disent ce qu'elles omettent (Priority: P2)

**Goal**: chaque carte de synthèse nomme sa portée et rend visible son reste.

**Independent Test**: sur une épreuve à plus de huit catégories, une à moins de huit, et
une sans club renseigné — sans que `US1` ni `US3` existent. § `US2` de
[quickstart.md](./quickstart.md).

### Tests for User Story 2

- [x] T024 [P] [US2] Test service : `clubs_total` compte les clubs **distincts** et vaut 0 sans club renseigné, dans `backend/tests/test_services/test_participation_stats_service.py`
- [x] T025 [P] [US2] Test API : `clubs_total` publié par la synthèse, dans `backend/tests/test_api/test_courses_api.py`
- [x] T026 [P] [US2] Test composant : la part « Autres (N) » apparaît quand le reste est positif, disparaît quand il est nul ou négatif, et l'ensemble totalise 100 %, dans `frontend/components/charts/CategoryBars.test.tsx`
- [x] T027 [P] [US2] Test composant : la description destinée aux lecteurs d'écran inclut la part « Autres », dans `frontend/components/charts/CategoryBars.test.tsx`
- [x] T028 [P] [US2] Test composant : le pied « et N autres clubs » n'apparaît que si la liste est tronquée, l'en-tête de colonnes disparaît sur liste vide, **et la description destinée aux lecteurs d'écran porte le nombre de clubs non listés** (seconde moitié de `FR-018`, la première étant couverte par T027), dans `frontend/components/courses/ClubBreakdown.test.tsx`

### Implementation for User Story 2

- [x] T029 [US2] Calculer `clubs_total` dans `backend/app/services/stats_service.py` depuis le `Counter` de clubs déjà construit (rend T024 vert)
- [x] T030 [US2] Ajouter `clubs_total: int` à `CourseSummary` dans `backend/app/schemas/course.py`, avec la docstring qui avertit de l'asymétrie d'unité avec `categories_total` — l'un compte des clubs, l'autre des participants (rend T025 vert)
- [x] T031 [US2] Ajouter la part « Autres (N) » calculée par différence, et l'inclure dans l'`aria-label`, dans `frontend/components/charts/CategoryBars.tsx` (rend T026, T027 verts)
- [x] T032 [US2] Extraire la carte « Top clubs » de `page.tsx:108-127` vers `frontend/components/courses/ClubBreakdown.tsx`, avec pied « et N autres clubs » et en-tête conditionnel (rend T028 vert)
- [x] T033 [US2] Brancher `ClubBreakdown` et corriger les titres des deux cartes pour qu'ils énoncent leur portée, dans `frontend/app/(public_restricted)/courses/[id]/page.tsx` (dépend de T032)

**Checkpoint**: `US1` et `US2` fonctionnent indépendamment. Plus aucun chiffre ne ment par omission.

---

## Phase 5: User Story 3 - Les synthèses mènent au classement, et leurs codes s'expliquent (Priority: P3)

**Goal**: chaque ligne de club et chaque part de catégorie ouvre le classement filtré, avec
un repère retirable ; et chaque code de catégorie donne son libellé complet.

**Independent Test**: partir d'une carte de synthèse et arriver sur un classement dont le
contenu correspond à la valeur activée. § `US3` de [quickstart.md](./quickstart.md).

### Tests for User Story 3

- [x] T034 [P] [US3] Test repository : `club` et `category` filtrent en **égalité exacte**, se cumulent entre eux, avec `q` et avec `club_only`, et le `total` porte sur la sélection, dans `backend/tests/test_repositories/test_participation_repository.py`
- [x] T035 [P] [US3] Test API : les deux paramètres facultatifs, leur défaut neutre, et une valeur inconnue rendant `total: 0` **sans** 404, dans `backend/tests/test_api/test_courses_api.py`
- [x] T036 [US3] Test d'additivité du contrat : les appels sans les nouveaux paramètres rendent des réponses inchangées aux clés d'origine, dans `backend/tests/test_api/test_courses_api.py` (même fichier que T035)
- [x] T037 [P] [US3] Test unitaire : la table de libellés couvre les codes de base, la règle de suffixe de genre, la règle de genre en mot préfixe, et rend le code brut hors table, dans `frontend/lib/__tests__/categories.test.ts`
- [x] T038 [P] [US3] Test composant : une part de catégorie est activable et mène à `?category=…`, et le libellé complet est atteignable au clavier — pas seulement au survol, dans `frontend/components/charts/CategoryBars.test.tsx`
- [x] T039 [P] [US3] Test composant : une ligne de club est activable et mène à `?club=…`, dans `frontend/components/courses/ClubBreakdown.test.tsx`
- [x] T040 [P] [US3] Test composant : les repères de club et de catégorie sont retirables **indépendamment** l'un de l'autre et de la recherche, la ligne d'état annonce la sélection face au total, et l'état d'absence nomme le filtre en cause sans parler de « recherche », dans `frontend/components/results/RaceFinishers.test.tsx`

### Implementation for User Story 3

- [x] T041 [US3] Ajouter les filtres `club` et `category` en égalité exacte à `list_page_for_course` dans `backend/app/repositories/participation_repository.py` (rend T034 vert)
- [x] T042 [US3] Exposer les deux paramètres facultatifs sur `GET /courses/{course_id}` dans `backend/app/api/v1/courses.py`, défaut `None` (rend T035, T036 verts, dépend de T041)
- [x] T043 [P] [US3] Créer `frontend/lib/categories.ts` — table de codes de base, règle de suffixe de genre, règle de genre en mot préfixe, séries masters, et repli sur le code brut, alimentée par le relevé de T001 (rend T037 vert)
- [x] T044 [US3] Rendre les parts de catégorie activables vers `?category=…` et exposer le libellé complet au doigt et au clavier, dans `frontend/components/charts/CategoryBars.tsx` (rend T038 vert, dépend de T043)
- [x] T045 [US3] Rendre les lignes de club activables vers `?club=…` dans `frontend/components/courses/ClubBreakdown.tsx` (rend T039 vert)
- [x] T046 [US3] Étendre les repères de sélection, la ligne d'état et les états d'absence de `frontend/components/results/RaceFinishers.tsx` aux deux nouveaux filtres, en prolongeant `libelleSelection` et le motif livré par le lot #485 plutôt qu'en le réécrivant (rend T040 vert)
- [x] T047 [US3] Transmettre `club` et `category` de l'URL à `apiServer.getCourse` dans `frontend/app/(public_restricted)/courses/[id]/page.tsx`, et étendre `CourseQuery` dans `frontend/lib/api/server.ts` (dépend de T042)

**Checkpoint**: les trois stories fonctionnent indépendamment.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T048 [P] Documenter les deux nouveaux paramètres de `GET /courses/{course_id}` et les six champs publiés dans `backend/app/api/AGENTS.md`
- [x] T049 [P] Vérifier le plancher de cible tactile (24 px) sur les nouveaux contrôles de `frontend/components/charts/CategoryBars.tsx`, `frontend/components/courses/ClubBreakdown.tsx` et `frontend/components/results/RaceFinishers.tsx`, et l'annonce du changement de sélection par `AnnonceStatut` dans ce dernier
- [x] T050 Rejouer le sondage **contre le module livré** : mesurer, en important `backend/app/services/split_gap.py` et non un prototype, le nombre de lignes signalées sur les 4 150 lignes évaluables de `backend/triathlon.db`, vérifier qu'il vaut **0** (`SC-005`), et consigner l'écart éventuel dans `docs/superpowers/specs/2026-08-25-ecart-inters-total-sondage.md`
- [x] T051 Dérouler `specs/20260825-114345-page-epreuve-syntheses/quickstart.md` de bout en bout sur les épreuves témoins relevées en T001
- [x] T052 Vérifier l'additivité du contrat : `git diff origin/main -- backend/tests/test_api/` ne montre **aucune assertion existante modifiée**
- [x] T053 Passer les cinq suites depuis `backend/` et `frontend/` : `uv run pytest -m "not integration"`, `uv run ruff check .`, `npm test`, `npm run lint`, `npm run build`
- [x] T054 Fin de branche selon `docs/WORKFLOW-IA.md` : `requesting-code-review`, puis le sous-agent `ui-ux-review` (la branche touche `frontend/`), puis `verification-before-completion`

**Ce que les deux revues ont trouvé, et que ni les tests ni la relecture n'avaient vu :**

| Revue | Constat | Gravité |
| --- | --- | --- |
| Code | La ligne du club menait à un classement **vide** — la synthèse fusionne les orthographes sous un libellé canonique qu'aucune ligne ne porte en base | haute |
| Code | `raid-multisport` a un gabarit vide : `all()` sur du vide vaut `True`, donc **100 % d'écart sur chaque ligne** | moyenne |
| Code | `SplitCoverageNote` ignorait la garde d'effectif, et affirmait un sens sur une médiane négative | moyenne |
| UI/UX | La croix des repères retombait sur un anneau de focus à **1,86:1** | bloquante |
| UI/UX | La barre « Autres » reprenait l'orange de la **plus grosse catégorie** (`8 % 8 = 0`) | à corriger |
| UI/UX | Élargir le libellé « Autres » raccourcissait sa piste de 16 à 25 % : une part de 29,9 % s'y dessinait à la longueur d'un 22 % | à corriger |

Et, hors revue, la contre-mesure de **T050** a révélé que le gabarit de segments du
premier jet divergeait de `mapping._SPLIT_KEYS_BY_SPORT` — ce qui a invalidé une partie du
sondage et fait tomber la dérogation au Principe VI.

**Vérification finale** — les cinq suites, sur la branche à jour :

| Suite | Résultat |
| --- | --- |
| `uv run pytest -m "not integration"` | 3949 ✓ |
| `uv run ruff check .` | ✓ |
| `uv run python scripts/sondage_ecart_inters.py` | 0/4150, verdict OK |
| `npm test` | 1677 ✓ (162 fichiers) |
| `npm run lint` / `npm run build` | ✓ / ✓ (TS strict) |

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (T001)** : aucune dépendance.
- **Foundational (T002)** : dépend de T001 pour rien de bloquant, mais **bloque les trois stories** — c'est le fichier de types partagé.
- **US1 (P1)**, **US2 (P2)**, **US3 (P3)** : démarrent toutes après T002, et sont mutuellement indépendantes.
- **Polish** : dépend des stories livrées.

### User Story Dependencies

Aucune story n'en attend une autre. Les deux seules adhérences sont **de fichier**, pas de
logique, et elles sont ordonnancées ici :

- `frontend/app/(public_restricted)/courses/[id]/page.tsx` est touché par T021 (`US1`), T033 (`US2`) et T047 (`US3`). Séquencer, ou livrer les stories l'une après l'autre.
- `frontend/components/courses/ClubBreakdown.tsx` est **créé** par T032 (`US2`) et étendu par T045 (`US3`). Si `US3` est livrée avant `US2`, T032 lui revient.
- `frontend/components/charts/CategoryBars.tsx` est touché par T031 (`US2`) et T044 (`US3`).
- `frontend/components/results/RaceFinishers.tsx` est touché par T022 (`US1`) et T046 (`US3`).

### Within Each User Story

Tests écrits et **rouges** avant l'implémentation (Principe III) → service → schéma →
repository → router → composants.

### Parallel Opportunities

- Les tests d'une même story marqués [P] s'écrivent en parallèle — sauf ceux qui partagent un fichier (T008/T009, T035/T036, T026/T027, T038, T039, T040).
- T016 et T017 (deux fichiers de schémas distincts) sont parallèles.
- Les trois stories sont parallélisables entre développeurs, sous réserve des quatre adhérences de fichier listées ci-dessus.

---

## Parallel Example: User Story 1

```bash
# Les tests backend de US1 qui ne partagent pas de fichier :
Task: "T003 évaluabilité dans backend/tests/test_core/test_split_gap.py"
Task: "T006 médiane dans backend/tests/test_services/test_participation_stats_service.py"
Task: "T008 contrat API dans backend/tests/test_api/test_courses_api.py"
Task: "T010 requête agrégée dans backend/tests/test_repositories/test_participation_repository.py"

# Les tests frontend de US1, trois fichiers distincts :
Task: "T011 marque d'en-tête dans frontend/app/(public_restricted)/courses/[id]/page.test.tsx"
Task: "T012 marqueur de ligne dans frontend/components/results/RaceFinishers.test.tsx"
Task: "T013 marque en liste dans frontend/components/results/EventList.test.tsx"
```

---

## Implementation Strategy

### MVP (User Story 1 seule)

1. T001 → T002 → Phase 3 entière.
2. **S'ARRÊTER ET VALIDER** : dérouler le § `US1` de `quickstart.md`.
3. `RES-10` est la seule des trois entrées à **fort impact**, et celle qui décide si le
   produit est crédible. Livrée seule, elle vaut déjà la branche.

### Livraison incrémentale

`US1` → valider → `US2` → valider → `US3` → valider. Chaque story ajoute sans casser la
précédente. L'ordre inverse serait moins cher (`US2` est la plus légère) mais retarderait
la seule entrée à fort impact.

---

## Notes

- **Le sondage prime sur ce fichier.** Les seuils de T014 et T022 (1 %, 5 %, 10 lignes, 60 s) en viennent. Ne pas les ajuster ici : les re-mesurer là-bas.
- **Zéro fausse alerte n'est pas la captation.** T004 est le seul test qui prouve que la règle capte quelque chose — la base de dev ne contient aucune ligne fausse au sens de `RES-10`. Ne pas le supprimer parce qu'il est le seul de son espèce : c'est précisément pour cela qu'il existe.
- **Le 0/4 150 du sondage a été mesuré sur un prototype, pas sur le module livré.** T050 est ce qui rattache `SC-005` au code réellement écrit ; sans lui, le chiffre qui porte tout le lot n'est vérifié nulle part.
- **T007 est la garde de la seule dérogation du Constitution Check.** Le §Complexity Tracking justifie la duplication du schéma de segments **par ce test**. Un T007 sauté ou affaibli rouvre la dérogation.
- Aucune migration Alembic : les six champs sont calculés à la lecture.
- L'identité visuelle et la frontière `components/tcn/` vs `components/ui/` ne sont pas rejugées (#325, #460).
- Un commit par tâche ou par groupe cohérent, en Conventional Commits.
