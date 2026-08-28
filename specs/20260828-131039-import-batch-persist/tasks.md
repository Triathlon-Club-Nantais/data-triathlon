---

description: "Task list for Persist par lot pour l'import de résultats (#706)"

---

# Tasks: Persist par lot pour l'import de résultats

**Input**: Design documents from `/specs/20260828-131039-import-batch-persist/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Le Principe III de la constitution v1.1.0 est non-négociable — TDD
sans réseau. US1 porte toute la nouvelle logique métier de cette feature :
ses tâches de test sont donc obligatoires et précèdent l'implémentation. US2
et US3 (`spec.md`) sont des effets attendus de la même correction, pas de la
logique métier nouvelle — pas de tâche de test dédiée pour elles ; leur
« Independent Test » est une vérification manuelle via `quickstart.md`, et
elles sont déjà couvertes indirectement par le comptage de requêtes de T007
et par la suite complète en T021.

**Organization**: Tasks are grouped by user story to enable independent
implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Web app existant : `backend/app/...`, `backend/tests/...` (voir
`plan.md` § Project Structure — aucun fichier `frontend/` concerné).

---

## Phase 1: Setup (Shared Infrastructure)

Aucune tâche : aucune dépendance nouvelle, aucun scaffolding — la feature
modifie un service et un repository déjà en place (`plan.md` § Technical
Context, Scale/Scope).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: les fonctions de repository que `_Persister` (US1) consommera
pour rester conforme au Principe II (« seule `app/repositories/` touche
`Session` ») : résolution d'athlètes par lot, création groupée d'athlètes
neufs, création groupée de participations neuves. Bloquant pour US1 — US2/US3
n'ajoutent pas de code, donc rien d'autre à bloquer.

**⚠️ CRITICAL**: US1 ne peut pas commencer avant que cette phase soit verte.

- [X] T001 Écrire le test rouge de `athlete_repository.get_by_identities_batch`
      (fonction nouvelle) dans
      `backend/tests/test_repositories/test_athlete_repository.py` : une
      requête pour un ensemble de paires `(nom, prénom)` retourne un
      `dict[(nom_lower, prenom_lower), Athlete]` couvrant toutes les paires
      existantes en base (insensible à la casse), omet les paires absentes,
      filtre sur `birth_date IS NULL` (`research.md` § Décision — identité
      athlète), et — condition de validation du choix technique de
      `research.md` § Décision — requête de résolution par lot — passe bien
      sur la fixture SQLite du projet (si `tuple_(...).in_(...)` échoue sur ce
      dialecte, le test l'objective ici avant d'aller plus loin).
- [X] T002 Implémenter `get_by_identities_batch(db, paires)` dans
      `backend/app/repositories/athlete_repository.py` (signature :
      `Sequence[tuple[str, str]]` en entrée, `dict[tuple[str, str], Athlete]`
      en sortie) pour faire passer T001. Dépend de T001.
- [X] T003 Écrire le test rouge de `athlete_repository.create_batch` (fonction
      nouvelle) dans `backend/tests/test_repositories/test_athlete_repository.py` :
      prend une liste de champs d'athlètes neufs, les ajoute en une seule
      opération (`db.add_all` + un seul `db.flush()`), et retourne les
      instances créées avec leur `id` peuplé — pour que `_Persister` (US1)
      n'ait jamais à appeler `db`/`Session` directement (Principe II).
- [X] T004 Implémenter `create_batch(db, athletes_fields)` dans
      `backend/app/repositories/athlete_repository.py` pour faire passer T003.
      Dépend de T003.
- [X] T005 [P] Écrire le test rouge de `participation_repository.create_batch`
      (fonction nouvelle) dans
      `backend/tests/test_repositories/test_participation_repository.py` :
      prend une liste de champs de participations neuves, les ajoute en une
      seule opération (`db.add_all` + un seul `db.flush()`), et retourne les
      instances créées — même contrat que T003, même raison (Principe II).
- [X] T006 [P] Implémenter `create_batch(db, participations_fields)` dans
      `backend/app/repositories/participation_repository.py` pour faire
      passer T005. Dépend de T005.

**Checkpoint**: les trois fonctions de repository (résolution par lot,
création groupée d'athlètes, création groupée de participations) sont
testées et vertes — US1 peut commencer sans jamais toucher `Session` depuis
`import_service.py`.

---

## Phase 3: User Story 1 - Import d'une épreuve volumineuse sans blocage (Priority: P1) 🎯 MVP

**Goal**: `_Persister.add`/`finalize` n'émettent plus un aller-retour DB par
ligne pour la résolution d'athlète ni pour l'écriture des participations
neuves, sans changer le résultat métier d'un import (FR-001 à FR-006).

**Independent Test**: importer un scrape de ~1000+ lignes réparties sur une
ou plusieurs courses et vérifier (a) que le nombre de requêtes DB émises
pendant `add`/`finalize` croît par paliers de taille de tranche et non
linéairement avec le nombre de lignes, et (b) que les compteurs et le rapport
qualité produits sont identiques à ceux de l'implémentation actuelle
(`quickstart.md` §§ 1-2).

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation** (Principe III, non-négociable).

- [X] T007 [P] [US1] Écrire le test rouge « le nombre de requêtes ne croît pas
      avec le volume », même patron que
      `test_course_merge.py::test_the_query_count_does_not_grow_with_the_number_of_results`
      (instrumentation `before_cursor_execute` sur l'engine), dans
      `backend/tests/test_services/test_import_service.py` : compare le
      nombre de requêtes émises par un import de ~10 lignes contre un import
      de ~1200 lignes (> 2 tranches) sur une même course, et vérifie
      explicitement que `finalize()` ne recharge plus une seconde fois les
      participations de la course (FR-003, FR-006).
- [X] T008 [P] [US1] Écrire le test rouge de non-régression des compteurs :
      un scrape mêlant lignes appariées par dossard existant (chemin
      `_reconcile`), lignes à dossard neuf et lignes sans dossard, sur un
      volume qui franchit une frontière de tranche (> 500 lignes), doit
      produire exactement les mêmes `imported`/`updated`/`skipped`/
      `reconciled` et les mêmes réassignations d'athlète que le comportement
      actuel ligne à ligne — dans
      `backend/tests/test_services/test_import_service.py` (FR-004).
- [X] T009 [P] [US1] Écrire le test rouge du cas de collision intra-lot :
      deux lignes du même scrape désignent le même athlète neuf (même
      `(nom, prénom)`, absent de la base avant l'import) — l'import ne doit
      créer **qu'une seule** fiche `Athlete`, la seconde ligne doit la
      retrouver, dans `backend/tests/test_services/test_import_service.py`
      (Edge Cases de `spec.md`).

### Implementation for User Story 1

- [X] T010 [US1] Ajouter la file d'attente de résolution par course et la
      constante de taille de tranche (~500, `research.md` § Taille de
      tranche) à `_Persister.__init__` dans
      `backend/app/services/import_service.py`. Dépend de T002, T004, T006.
- [X] T011 [US1] Router le chemin dossard apparié (`_reconcile`, aujourd'hui
      un appel inconditionnel à `mapping.resolve_athlete`) vers la file
      d'attente au lieu d'une résolution immédiate, dans
      `backend/app/services/import_service.py`. Dépend de T010.
- [X] T012 [US1] Router le chemin dossard neuf/sans dossard
      (`mapping.get_or_create_athlete`) vers la même file d'attente, dans
      `backend/app/services/import_service.py`. Dépend de T010.
- [X] T013 [US1] Implémenter le déclenchement du lot (file pleine, ou
      reliquat à `finalize()`) : appel à `athlete_repository.get_by_identities_batch`
      (T002) pour retrouver les athlètes existants, puis à
      `athlete_repository.create_batch` (T004) pour les athlètes manquants —
      jamais de `db.add`/`db.flush` direct dans `import_service.py` (Principe
      II) —, peuplement du cache de résolution
      `(nom_lower, prenom_lower) → Athlete` (`data-model.md` § Cache de
      résolution par tranche), dans `backend/app/services/import_service.py`.
      Dépend de T011, T012.
- [X] T014 [US1] Faire consommer par `_reconcile`/`_upsert`/la création de
      participation le cache de résolution en mémoire au lieu d'un appel
      direct à `mapping.resolve_athlete`/`get_or_create_athlete`, dans
      `backend/app/services/import_service.py`. Dépend de T013.
- [X] T015 [US1] Remplacer les appels ligne-à-ligne à
      `participation_repository.create` par un regroupement des participations
      neuves d'une tranche/course et un seul appel à
      `participation_repository.create_batch` (T006) — jamais de `db.flush`
      direct dans `import_service.py` (Principe II) —, dans
      `backend/app/services/import_service.py`. Dépend de T013.
- [X] T016 [US1] Réutiliser dans `finalize()` la liste de participations déjà
      chargée par `_index_course` au lieu d'un second appel à
      `participation_repository.list_for_course`, dans
      `backend/app/services/import_service.py`. Dépend de T010.
- [X] T017 [US1] Faire passer T007-T009 au vert et relancer
      `uv run pytest -m "not integration" backend/tests/test_services/test_import_service.py -v`
      jusqu'à zéro régression. Dépend de T014, T015, T016.

**Checkpoint**: User Story 1 est fonctionnelle et testable indépendamment —
c'est le MVP de la feature.

---

## Phase 4: User Story 2 - Fin d'import fiable, sans faux message d'erreur (Priority: P2)

**Goal**: constater que le raccourcissement de la persistance (US1) réduit la
fréquence des faux messages « Erreur » après commit réussi.

**Independent Test**: `quickstart.md` § 3 — mesurer en production le temps
d'un import de volume comparable à celui qui déclenchait le symptôme, sur
l'implémentation issue de US1.

- [ ] T018 [US2] Exécuter la mesure de `quickstart.md` § 3 (import Trégastel
      2026 ou volume comparable, environnement Render/Supabase) une fois US1
      mergée, et consigner le temps mesuré et l'absence (ou la présence
      résiduelle) du faux message « Erreur » dans
      `specs/20260828-131039-import-batch-persist/quickstart.md`. Pas de
      nouveau code — SC-004 est une mesure de suivi, pas une garantie de
      cette seule feature (`spec.md` § Assumptions).

**Checkpoint**: US1 et US2 fonctionnent — le gain de temps est confirmé en
production et son effet sur le faux « Erreur » est documenté.

---

## Phase 5: User Story 3 - Progression SSE qui va jusqu'au bout (Priority: P3)

**Goal**: constater que le raccourcissement de la persistance (US1) réduit la
fréquence des connexions SSE sans phase terminale.

**Independent Test**: `quickstart.md` § 4 — suivre une connexion SSE sur un
import de volume comparable à ceux qui expiraient avant le correctif.

- [ ] T019 [US3] Exécuter la vérification de `quickstart.md` § 4 (suivi SSE
      sur un import de volume comparable) une fois US1 mergée, et consigner
      si la connexion atteint bien une phase `done`/`error` dans
      `specs/20260828-131039-import-batch-persist/quickstart.md`. Pas de
      nouveau code — même statut de suivi que T018.

**Checkpoint**: les trois user stories sont vérifiées.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T020 [P] `uv run ruff check backend/app/services/import_service.py backend/app/repositories/athlete_repository.py backend/app/repositories/participation_repository.py`
- [X] T021 `uv run pytest -m "not integration"` (suite complète backend) —
      zéro régression hors du périmètre de cette feature.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: aucune tâche.
- **Foundational (Phase 2)**: T001-T006 — bloque Phase 3 (US1).
- **US1 (Phase 3)**: dépend de Phase 2. Porte tout le code de la feature.
- **US2 (Phase 4)** et **US3 (Phase 5)**: dépendent de US1 (rien à observer
  avant que la persistance soit effectivement raccourcie) ; indépendantes
  l'une de l'autre.
- **Polish (Phase 6)**: dépend de US1 (T017) au minimum ; T018/T019 (US2/US3)
  n'ajoutant pas de code, ne bloquent pas Phase 6.

### Within Foundational

- T001 avant T002 (repository résolution par lot).
- T003 avant T004 (repository création groupée d'athlètes) — même fichier de
  test que T001, pas de parallélisme entre les deux paires.
- T005 avant T006 (repository création groupée de participations) — fichier
  différent de T001-T004, parallélisable avec la paire athlète.

### Within User Story 1

- Tests (T007-T009) écrits et rouges avant l'implémentation (T010-T016).
- T010 dépend des trois fonctions de repository (T002, T004, T006) : la file
  d'attente et sa taille de tranche n'ont de sens qu'une fois les points de
  sortie du lot disponibles.
- T010 avant T011/T012 (la file d'attente doit exister avant d'y router les
  deux chemins de résolution).
- T011, T012 avant T013 (le lot ne peut se déclencher qu'une fois les deux
  chemins alimentent la même file).
- T013 avant T014 (le cache de résolution doit être peuplé avant d'être
  consommé).
- T013 avant T015 (la création groupée de participations a besoin des
  `athlete_id` résolus par le déclenchement du lot).
- T016 ne dépend que de T010 (indépendant de la chaîne de résolution
  d'athlète) — parallélisable avec T011-T015 si un second contributeur est
  disponible, mais listé en série ici car même fichier que T010-T015.

### Parallel Opportunities

- T001-T002 (résolution par lot) et T005-T006 (création groupée de
  participations) portent sur des fichiers différents : parallélisables entre
  elles. T003-T004 (création groupée d'athlètes) partage son fichier de test
  avec T001-T002 : séquentiel avec elles, mais parallélisable avec T005-T006.
- T007, T008, T009 (tests US1) portent sur le même fichier de test mais des
  cas indépendants : parallélisables entre elles si rédigées comme des
  fonctions de test distinctes n'entrant pas en conflit d'édition simultanée.
- T020 (lint) est indépendant de T021 (suite de tests) — parallélisable.

---

## Parallel Example: Foundational + User Story 1 tests

```bash
# Les paires (T001,T002) et (T005,T006) peuvent être menées en parallèle
# (fichiers différents) ; (T003,T004) suit (T001,T002) sur le même fichier :
Task: "Test + impl de get_by_identities_batch dans backend/app/repositories/athlete_repository.py"
Task: "Test + impl de create_batch (participations) dans backend/app/repositories/participation_repository.py"

# Une fois T001-T006 verts, les trois tests rouges de US1 peuvent être rédigés en parallèle :
Task: "Test rouge comptage de requêtes dans backend/tests/test_services/test_import_service.py"
Task: "Test rouge non-régression des compteurs (franchissement de tranche) dans backend/tests/test_services/test_import_service.py"
Task: "Test rouge collision intra-lot dans backend/tests/test_services/test_import_service.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Compléter Phase 2 (Foundational) — T001 à T006.
2. Compléter Phase 3 (US1) — T007 à T017.
3. **STOP et VALIDER** : `quickstart.md` §§ 1-2 (suite unitaire + comptage de
   requêtes), puis §3 en production (T018, qui appartient formellement à US2
   mais constitue la validation ultime du MVP).
4. Merger — c'est la correction de #706.

### Incremental Delivery

1. Foundational → US1 (MVP, le gain de performance mesuré par SC-001/SC-002).
2. US2 et US3 : pas de nouveau déploiement — deux tâches d'observation
   post-déploiement (T018, T019) qui documentent l'effet de US1 sur les
   symptômes en cascade, à exécuter dans les jours suivant le merge de US1.

---

## Notes

- [P] tasks = fichiers différents ou cas de test indépendants sans conflit
  d'édition simultanée.
- Toute création d'`Athlete`/`Participation` par `_Persister` passe par une
  fonction de repository (`get_by_identities_batch`, `create_batch` ×2) —
  jamais de `db.add`/`db.flush` direct dans `import_service.py` (Principe II
  de la constitution ; corrigé suite à `/speckit-analyze`, finding C1).
- US2/US3 n'ont pas de tâche de test dédiée : elles ne portent aucune
  logique métier nouvelle (Principe III ne s'applique qu'à la logique métier
  nouvelle) — leur vérification est un suivi manuel post-déploiement.
- Vérifier que T007-T009 échouent avant de commencer T010.
- S'arrêter au checkpoint de Phase 3 pour valider le MVP avant de considérer
  US2/US3.
