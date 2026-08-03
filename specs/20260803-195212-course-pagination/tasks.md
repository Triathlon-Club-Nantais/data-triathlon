# Tasks: Pagination et recherche du classement d'une épreuve

**Input**: Design documents from `specs/20260803-195212-course-pagination/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/courses-api.md](./contracts/courses-api.md), [quickstart.md](./quickstart.md)

**Tests** : Principe III de la constitution v1.1.0, **non-négociable**. Chaque
tâche de test précède la tâche d'implémentation qu'elle couvre, et **doit
échouer** avant elle. Aucune dérogation demandée pour cette feature.

**Organization**: tâches groupées par user story, chacune livrable et testable
indépendamment.

## Format: `[ID] [P?] [Story] Description`

- **[P]** : parallélisable (fichiers distincts, aucune dépendance sur une tâche
  non terminée)
- **[Story]** : US1, US2, US3 — renvoie aux user stories de `spec.md`

## Path Conventions

Application web à deux briques : `backend/app/`, `backend/tests/`,
`frontend/app/`, `frontend/components/`, `frontend/lib/`. Chemins exacts dans
`plan.md`, §Source Code.

---

## Phase 1: Setup

**Purpose**: aucune dépendance à installer, aucun projet à initialiser — la
feature vit entièrement dans du code existant. La seule préparation utile est de
capturer l'état d'avant, sans quoi SC-002 et SC-003 ne sont pas vérifiables
après coup.

- [X] T001 Capturer la référence d'avant-branche : sur une épreuve de plus de 100 participations comportant au moins un DNF, un DSQ et un DNS, enregistrer dans `/tmp/ref-ordre.json` la suite des `id` du classement **dans l'ordre affiché**, obtenue en appliquant `orderParticipations` de `frontend/lib/utils/raceOrder.ts` à la charge de `GET /api/v1/courses/<id>`. Faire aussi une capture d'écran des six blocs de statistiques. **Ne pas se contenter de la sortie brute de l'API** : elle est triée sur `rank_overall` seul (`participation_repository.list_for_course`) et n'est pas l'ordre de l'écran — s'y fier ferait échouer T044 sur toute épreuve comportant des abandons, sans qu'on sache si la faute vient de l'ordre SQL ou de la référence. Témoin de SC-002 et SC-003.

**Checkpoint**: référence capturée, on peut modifier sans perdre le point de comparaison.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: l'ordre d'affichage en base et les formes de sortie. Les trois user
stories en dépendent : sans ordre stable en SQL, aucune tranche n'a de sens.

**⚠️ CRITICAL**: aucune user story ne peut démarrer avant la fin de cette phase.

- [X] T002 [P] Écrire les tests de l'ordre d'affichage en base dans `backend/tests/test_repositories/test_participation_repository.py` : finishers par rang croissant puis non classés ; groupes `DNF` → `DSQ` → `DNS` ensuite ; dans un groupe de non-finishers, temps croissant puis temps absents (`NULL`, `""`, `00:00:00`) en fin ; départage par nom puis prénom. Ces tests **doivent échouer** avant T004.
- [X] T003 [P] Écrire le test de non-régression sur les `NULL` dans `backend/tests/test_repositories/test_participation_repository.py` : **parmi les finishers**, une participation sans `rank_overall` passe après toutes celles qui en ont un — la restriction au groupe compte, un DNF sans rang passant lui avant un finisher sans rang. C'est la divergence SQLite (`NULL` en tête) / PostgreSQL (`NULL` en queue) que les clés booléennes ferment (`research.md`, R1).
- [X] T004 Implémenter la clause d'ordre d'affichage dans `backend/app/repositories/participation_repository.py` : une fonction privée rendant la liste des expressions `ORDER BY` décrite dans `research.md` §R1, avec des clés booléennes `0/1` et non `NULLS LAST`. **Ne pas modifier `list_for_course`** : ses deux appelants (`import_service._index_course`, `import_service.finalize` → `quality.analyze`) sont sur le chemin d'import et n'ont pas à voir leur ordre changer.
- [X] T005 [P] Créer les schémas de sortie dans `backend/app/schemas/course.py` : `CourseParticipationPage` (`course`, **`participations`** — surtout pas `items`, la clé actuelle de la route ne change pas —, `total`, `page`, `page_size: int | None`), `CourseSummary` et ses sous-modèles `CategoryCount`, `ClubCount`, `Histogram`. Champs et types exacts : `data-model.md`, §Formes de sortie.
- [X] T006 [P] Déclarer les types correspondants dans `frontend/lib/types.ts` : `CourseSummary`, `CategoryCount`, `ClubCount`, `Histogram`, et l'enveloppe paginée de `CourseDetail` (`participations`, `total`, `page`, `page_size`).

**Checkpoint**: l'ordre est en base, les formes de sortie existent des deux côtés. Les user stories peuvent démarrer.

---

## Phase 3: User Story 1 — Consulter une grosse épreuve sans en télécharger tout le classement (Priority: P1) 🎯 MVP

**Goal**: la page affiche ses six blocs de statistiques et les 20 premières
lignes, sans transporter le classement entier.

**Independent Test**: ouvrir `/courses/<id>` d'une épreuve de plus de 100
participations ; les six blocs affichent les mêmes valeurs que la capture de
T001, le tableau montre 20 lignes, et le document rendu ne contient plus toutes
les participations.

### Tests (à écrire en premier, doivent échouer)

- [X] T007 [P] [US1] Écrire les tests de la synthèse dans `backend/tests/test_services/test_stats_service.py` : invariant `total == finishers + non_finishers + unknown` ; `tcn_count` issu de `core/club.is_tcn` ; `male`/`female` ne comptant que les lignes genrées ; `categories` bornée à 8 et décroissante ; `clubs` bornée à 9, décroissante, portant `is_tcn` ; `split_keys` couvrant les clés vues sur **au moins une** participation, dans l'ordre d'apparition. **Plus le test de FR-022** : la lecture rend des tuples et non des instances de `Participation`, et une seule requête est émise — sans quoi un `joinedload` réintroduit un jour ferait retomber la synthèse dans le coût que la feature supprime, sans que rien ne le signale.
- [X] T008 [P] [US1] Écrire les tests de l'histogramme dans `backend/tests/test_services/test_stats_service.py` : mêmes tranches de 300 s et même `start_sec` que `buildHistogram` de `frontend/app/courses/[id]/page.tsx` ; plafond de 60 tranches ; `None` quand aucun temps n'est exploitable ; `00:00:00` et `""` ne comptent pas.
- [X] T009 [P] [US1] Écrire les tests de la synthèse sur épreuve vide dans `backend/tests/test_services/test_stats_service.py` : compteurs à zéro, listes vides, `histogram` à `None`, aucune division par zéro.
- [X] T010 [P] [US1] Créer `backend/tests/test_api/test_courses_api.py` avec les tests de contrat de `GET /courses/{id}/summary` : `200` sur épreuve existante, `404` sur épreuve inconnue, forme de réponse conforme à `contracts/courses-api.md`, et **aucun paramètre accepté** (la synthèse ne dépend d'aucune sélection).

### Implémentation

- [X] T011 [US1] Ajouter dans `backend/app/repositories/participation_repository.py` la lecture des colonnes de synthèse : une requête unique rendant les tuples `(status, club, category, total_time, splits, athlete.gender)`, **sans hydrater d'objet ORM ni de relation** (`data-model.md`, §Synthèse d'épreuve).
- [X] T012 [US1] Implémenter `course_summary()` dans `backend/app/services/stats_service.py` : agrégation Python des tuples de T011. Réutiliser `core/club.is_tcn` pour le drapeau club et le compteur TCN — ne jamais le réimplémenter (#76). Transposer à l'identique le découpage de l'histogramme et les limites 8 catégories / 9 clubs depuis `frontend/app/courses/[id]/page.tsx`.
- [X] T013 [US1] Ajouter la route `GET /courses/{course_id}/summary` dans `backend/app/api/v1/courses.py` : validation, `NotFoundError` si l'épreuve n'existe pas, délégation à `stats_service.course_summary`. Aucun paramètre de requête.
- [X] T014 [P] [US1] Ajouter `getCourseSummary(id)` dans `frontend/lib/api/server.ts` et dans `frontend/lib/api/client.ts`.
- [X] T015 [US1] Créer `frontend/app/courses/[id]/page.test.tsx` : les six blocs se rendent depuis une synthèse fournie, et une synthèse vide ne produit ni `NaN` ni histogramme.
- [X] T016 [US1] Réécrire `frontend/app/courses/[id]/page.tsx` : deux appels serveur (synthèse + classement), les six blocs alimentés par la synthèse. Supprimer les calculs JS devenus morts — `buildHistogram`, les boucles de répartition genre / catégories / clubs, le `parseSeconds` local. Conserver `Histogram`, `Legend` et `formatTickLabel`, qui restent des composants de rendu.
- [X] T017 [US1] Adapter `frontend/components/results/RaceFinishers.tsx` : recevoir `summary` et n'utiliser que lui pour le pied de tableau (FR-030), le compteur TCN et les colonnes de temps intermédiaires via `split_keys` (FR-028) — plus jamais les lignes de la page courante.
- [X] T018 [US1] Mettre à jour `frontend/components/results/RaceFinishers.test.tsx` pour la nouvelle interface : les tests de pied de tableau existants (« 3 partants · 1 finisher · 2 abandons ») doivent continuer de passer, alimentés par `summary` au lieu de la liste complète.

**Checkpoint**: la page est fonctionnelle avec ses statistiques et ses 20 premières lignes. C'est le MVP livrable.

---

## Phase 4: User Story 2 — Parcourir le classement page par page (Priority: P1)

**Goal**: atteindre n'importe quelle page du classement, par une adresse
partageable.

**Independent Test**: ouvrir `/courses/<id>?page=3` directement ; les lignes
affichées poursuivent celles de la page 2, sans doublon ni trou, et la
concaténation de toutes les pages redonne la référence de T001.

### Tests (à écrire en premier, doivent échouer)

- [X] T019 [P] [US2] Écrire les tests de tranche dans `backend/tests/test_repositories/test_participation_repository.py` : la concaténation de toutes les tranches égale la liste complète, ligne pour ligne (SC-003) ; aucune ligne en double ni manquante aux bornes ; une page au-delà du dernier rend une tranche vide et un `total` exact.
- [X] T020 [P] [US2] Écrire les tests de résolution de `page_size` dans `backend/tests/test_api/test_courses_api.py` : `20` par défaut ; un entier entre 1 et 200 accepté ; `all` rendant une page unique avec `page_size: null` et autant de lignes que `total` ; `0`, `-1`, `9999` et `tout` rendant `422` (FR-007).
- [X] T021 [P] [US2] Écrire les tests de contrat de `GET /courses/{id}` paginé dans `backend/tests/test_api/test_courses_api.py` : présence de `total`, `page`, `page_size` aux côtés de `course` et `participations` ; clé `participations` **conservée** (et non renommée `items`).

### Implémentation

- [X] T022 [US2] Ajouter dans `backend/app/repositories/participation_repository.py` la fonction de tranche : filtres (`course_id`, plus tard `q` et `scope`), ordre d'affichage de T004, `total` compté sur la sélection, `offset`/`limit` — et aucun découpage quand la taille demandée est « tout ».
- [X] T023 [US2] Rendre `GET /courses/{course_id}` paginé dans `backend/app/api/v1/courses.py` : paramètres `page` (`int ≥ 1`) et `page_size` (`int | Literal["all"]`, défaut `20`), résolveur vérifiant `1 ≤ n ≤ 200` et levant une erreur d'usage sinon, réponse conforme à `contracts/courses-api.md`.
- [X] T024 [P] [US2] Étendre `getCourse` dans `frontend/lib/api/server.ts` et `frontend/lib/api/client.ts` pour accepter `{ page, page_size, q, scope }`, en réutilisant le `toQuery` existant.
- [X] T025 [US2] Lire `searchParams` dans `frontend/app/courses/[id]/page.tsx` (`Promise<Record<string, string | undefined>>` puis `await`, patron de `app/dashboard/page.tsx`) et passer `page` à l'appel de classement. Une valeur absente, non numérique ou `< 1` vaut 1, sans erreur.
- [X] T026 [US2] Ajouter les contrôles de pagination dans `frontend/components/results/RaceFinishers.tsx` : des `<Link>` « Précédent » / « Suivant » et l'indication « page N sur M », préservant les autres paramètres d'URL. Aucun contrôle rendu quand la sélection tient en une page (FR-027).
- [X] T027 [US2] Compléter `frontend/components/results/RaceFinishers.test.tsx` : les liens portent bien `?page=`, « Précédent » est absent ou inactif en page 1, « Suivant » l'est en dernière page, et aucun contrôle n'apparaît sous une page pleine.

**Checkpoint**: tout le classement est atteignable, par une adresse partageable.

---

## Phase 5: User Story 3 — Retrouver un athlète par son nom (Priority: P2)

**Goal**: atteindre une ligne par son nom, où qu'elle soit dans le classement,
accents ou non.

**Independent Test**: chercher « lemee » sur une épreuve où figure « LEMÉE » en
page 40 ; la ligne ressort, et les six blocs de statistiques n'ont pas bougé.

**⚠️ Cette phase ajoute une dépendance d'infrastructure** (extension PostgreSQL).
Justification et alternatives écartées : `plan.md`, §Complexity Tracking.

### Tests (à écrire en premier, doivent échouer)

- [X] T028 [P] [US3] Écrire les tests de déaccentuation dans `backend/tests/test_core/test_text.py` (fichier à créer) : `LEMÉE` → `LEMEE`, `Pléneuf-Val-André` → `Pleneuf-Val-Andre`, chaîne vide et `None` traités sans erreur, caractères non latins laissés intacts.
- [X] T029 [P] [US3] Écrire les tests de recherche dans `backend/tests/test_repositories/test_participation_repository.py` : `q="guen"` trouve « Le Guen » ; `q="lemee"` **et** `q="LEMÉE"` trouvent la même ligne et rendent le même `total` ; la correspondance porte sur le nom **ou** le prénom, en sous-chaîne ; `q=""` et `q="   "` équivalent à l'absence de recherche (FR-015) ; `q` et `scope=club` se composent (FR-016). **Et le test de la borne négative** (FR-014) : un terme qui ne correspond qu'à un libellé de club, à un dossard ou à une catégorie rend **zéro** ligne — une exigence négative non testée dérive au premier champ ajouté au filtre.
- [X] T030 [P] [US3] Écrire le test de portée de la synthèse dans `backend/tests/test_api/test_courses_api.py` : la synthèse est **identique** avec et sans `q`, avec et sans `scope` — c'est FR-018, le garde-fou contre l'histogramme qui tombe à une barre.

### Implémentation

- [X] T031 [P] [US3] Créer `backend/app/core/text.py` avec la fonction de déaccentuation : `unicodedata.normalize("NFD", …)` puis retrait des marques combinantes. Fichier séparé parce qu'il est appelé à la fois par `core/database.py` et par le repository — l'inscrire dans l'un des deux créerait une dépendance en travers des couches.
- [X] T032 [US3] Enregistrer la fonction SQLite `unaccent` dans `backend/app/core/database.py`, aux côtés de `_unicode_lower` et selon le même patron (`create_function(..., deterministic=True)`, sous garde `isinstance(dbapi_connection, sqlite3.Connection)`).
- [X] T033 [US3] Créer la migration Alembic `CREATE EXTENSION IF NOT EXISTS unaccent` dans `backend/alembic/versions/`. Aucune DDL de table. Le `downgrade` ne doit **pas** supprimer l'extension : d'autres objets pourraient en dépendre, et une extension laissée en place est inoffensive.
- [X] T034 [US3] Ajouter le filtre de recherche à la fonction de tranche de T022 dans `backend/app/repositories/participation_repository.py` : `func.unaccent(func.lower(...))` sur `Athlete.nom` **ou** `Athlete.prenom`, avec le terme déaccentué en Python. Une valeur vide ou composée d'espaces n'ajoute aucun filtre.
- [X] T035 [US3] Exposer `q` et `scope` sur `GET /courses/{course_id}` dans `backend/app/api/v1/courses.py`, en réutilisant `core.club.is_club_scope` comme les autres routes de lecture. Défauts neutres (Principe V).
- [X] T036 [US3] Ajouter le champ de recherche dans `frontend/components/results/RaceFinishers.tsx`, sur le patron de `frontend/components/results/ResultsFilters.tsx` : saisie en état local, application sur `Entrée`, **pas de debounce**. Le filtre club existant passe de `useState` à `?scope=club` via `SCOPE_PARAM` / `SCOPE_CLUB` de `frontend/lib/scope.ts`.
- [X] T037 [US3] Faire retomber la pagination à la page 1 à tout changement de `q` ou de `scope`, dans `frontend/components/results/RaceFinishers.tsx` (FR-025) — sans quoi une recherche à trois résultats atterrit sur une page vide.
- [X] T038 [US3] Compléter `frontend/components/results/RaceFinishers.test.tsx` : une recherche pousse `?q=` dans l'URL et supprime `page` ; basculer le filtre club pousse `?scope=club` et supprime `page` de même.

**Checkpoint**: les trois user stories sont livrées.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T039 Supprimer `orderParticipations` de `frontend/lib/utils/raceOrder.ts` et tous ses appels. La retirer **vraiment** : la laisser en place garantit qu'un futur écran la rappellera sur une tranche de 20 lignes et retriera dans le vide, sans erreur visible. `countOutcomes`, `isFinisher` et `isNonFinisher` restent — ils servent toujours.
- [X] T040 [P] Vérifier qu'aucun appelant ne dépend plus de la liste complète : `grep -rn "getCourse" frontend/` et revue des usages de `CourseDetail` dans `frontend/lib/types.ts`.
- [X] T041 [P] Documenter la feature dans `AGENTS.md` : une entrée disant que le classement d'une épreuve est paginé par défaut, que `page_size=all` est l'échappatoire, que l'ordre d'affichage est désormais une propriété de la requête et non du navigateur, et que la recherche par nom est la seule du projet à être insensible aux accents.
- [X] T042 Dérouler `quickstart.md` §1 à §9 sur la base de dev, consigner l'écart de taille de charge mesuré au §9 (SC-001), et vérifier au §8.4 qu'une ligne s'atteint en deux actions — saisir le nom, lire le résultat (SC-004).
- [ ] T043 **Vérification PostgreSQL — REPORTÉE le 2026-08-03, décision de l'utilisateur.** Dérouler `quickstart.md` §10 sur la base Supabase : `unaccent` installée, son schéma, et sa résolution depuis le rôle applicatif. Aucun test de la suite ne couvre ce chemin (`research.md`, R2). **Risque assumé** : si `unaccent` n'est pas résoluble depuis le `search_path` du rôle applicatif, la recherche par nom rend une erreur en production alors qu'elle passe en développement — le reste de la page (pagination, synthèse, blocs) n'est pas concerné, seule la recherche tomberait. Atténuation constatée : la migration `pg_trgm` (`a1b2c3d4e5f6`) fait déjà un `CREATE EXTENSION` conditionnel du même patron et est passée, donc le rôle a le droit de création ; seul le `search_path` reste à confirmer. **À faire au premier déploiement**, pas avant la fusion.
- [X] T044 Comparer à la référence `/tmp/ref-ordre.json` capturée en T001 : la concaténation des pages doit lui être identique ligne pour ligne (SC-003), et les six blocs identiques valeur pour valeur à la capture d'écran (SC-002). **Un écart limité à des lignes ex æquo** — même groupe **et** même rang (ou même temps), départagées par un nom accentué — n'est pas un échec : c'est la déviation documentée dans `plan.md` §Notes et dans les Assumptions de `spec.md`, la collation de la base ne plaçant pas les caractères accentués comme `localeCompare`. Tout autre écart en est un.
- [X] T045 Suite complète : `cd backend && uv run pytest -m "not integration" && uv run ruff check .` puis `cd frontend && npm test && npm run lint && npm run build` (SC-006).

---

## Dependencies

```text
Phase 1 (T001)
   ↓
Phase 2 — Foundational (T002 → T004, T005, T006)
   ↓
   ├─→ Phase 3 — US1 (T007 → T018)          MVP livrable seul
   ├─→ Phase 4 — US2 (T019 → T027)          dépend de T004 ; T022 est étendue par T034
   └─→ Phase 5 — US3 (T028 → T038)          dépend de T022 (US2)
                                             ↓
                                          Phase 6 — Polish (T039 → T045)
```

**Dépendances entre stories** : US1 est indépendante. US2 dépend seulement de la
phase Foundational. **US3 dépend de US2** — sa recherche s'ajoute à la fonction
de tranche créée en T022 ; l'implémenter d'abord obligerait à écrire deux fois
la même requête.

**Dépendances internes notables** :

- T004 (ordre SQL) bloque T019, T022 et toute vérification de SC-003.
- T012 (synthèse) bloque T016 et T017 : la page ne peut pas afficher ce qui
  n'est pas calculé.
- T031 (déaccentuation) bloque T032 et T034, qui l'appellent tous deux.
- T033 (migration) doit être appliquée avant tout test de recherche exécuté
  sur PostgreSQL — sans effet sur SQLite.

## Parallel Execution Examples

**Phase 2** — trois tâches sur trois fichiers distincts :

```text
T002  backend/tests/test_repositories/test_participation_repository.py
T005  backend/app/schemas/course.py
T006  frontend/lib/types.ts
```

**Phase 3, tests** — quatre tâches, deux fichiers :

```text
T007, T008, T009  backend/tests/test_services/test_stats_service.py   (séquentiel entre elles)
T010              backend/tests/test_api/test_courses_api.py          (parallèle aux trois autres)
```

**Phase 5, tests** — trois fichiers distincts :

```text
T028  backend/tests/test_core/test_text.py
T029  backend/tests/test_repositories/test_participation_repository.py
T030  backend/tests/test_api/test_courses_api.py
```

**À ne pas paralléliser** : T022 et T034 touchent la même fonction ; T016, T017,
T026, T036 et T037 touchent tous `RaceFinishers.tsx` ou `page.tsx`.

## Implementation Strategy

**MVP = Phase 1 + Phase 2 + Phase 3 (US1)**, soit T001 à T018. À ce stade la
page affiche ses statistiques et ses 20 premières lignes sans transporter le
classement entier : SC-001 et SC-002 sont atteints. Mais le classement s'arrête
au rang 20, ce qui est une régression fonctionnelle — **le MVP est livrable en
revue, pas en production**.

**Le premier incrément déployable est Phase 4 incluse** (US2) : la pagination
rend tout le classement à nouveau atteignable.

**Phase 5 (US3) est un vrai incrément séparé**, et le seul qui touche à
l'infrastructure. Si la vérification PostgreSQL de T043 devait bloquer, les
phases 1 à 4 restent déployables telles quelles — la recherche est la seule
chose qui manquerait.
