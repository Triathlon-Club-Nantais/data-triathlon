---

description: "Task list for epic #1146, one stable identity per real athlete"
---

# Tasks: Une identité stable par athlète réel

**Input**: Design documents from `specs/20261001-144131-athlete-identity/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Principe III (TDD sans réseau, non négociable). Dans chaque phase, les tâches de test passent **avant** l'implémentation et doivent être vues **rouges** avant d'écrire le code. Tests backend sous `backend/tests/`, lancés par `uv run pytest -m "not integration"` depuis `backend/` ; tests front par `npm test` depuis `frontend/`.

**Organization**: une phase par user story (ordre de priorité de la spec). Chaque phase correspond à une PR vers `epic/1146-athlete-identity`, avec `Refs #1146` et la sous-issue indiquée (tableau « PR » en fin de fichier, source de vérité du découpage).

## Format: `[ID] [P?] [Story] Description`

- **[P]** : parallélisable (fichiers différents, aucune dépendance sur une tâche non terminée)
- **[Story]** : user story de la spec (US1 à US6)
- Chemins relatifs à la racine du dépôt

---

## Phase 1: Setup

**Purpose**: base verte et repères avant toute modification.

- [X] T001 Vérifier que la base est verte dans le worktree : `uv run pytest -m "not integration"` et `uv run ruff check .` depuis `backend/`, `npm test` depuis `frontend/` ; noter tout test déjà rouge dans la description de la première PR
- [X] T002 Ouvrir l'issue d'amendement PATCH de la constitution (#1160), **à faire approuver avant la fusion de la PR 1**, (section « Additional Constraints », `Athlete (unique par nom/prénom/DDN)` devient « unique par clé normalisée et rang d'homonyme ») selon la procédure « Governance » de `.specify/memory/constitution.md` ; titre en anglais, corps en français, lien vers #1146

---

## Phase 2: Foundational (clé normalisée et contrainte, #907)

**Purpose**: la clé stockée, le rang d'homonyme et la contrainte unique dont dépendent toutes les stories.

**⚠️ CRITICAL**: aucune story ne commence avant la fin de cette phase.

### Tests (rouges d'abord)

- [X] T003 [P] Tests de `identity_key` dans `backend/tests/test_core/test_athlete_identity.py` : `Léo`→`leo`, `RONFLÉ`→`ronfle`, `Maëva`→`maeva`, `L'APPARTIEN`→`lappartien`, `LE GLOANIC`→`legloanic`, `Jean-marie`→`jeanmarie`, `Œuvray`→`oeuvray`, `Strauß`→`strauss`, `CIC 7`→`cic7`, `?DOSSARD #12`→`dossard12`, `Иванов`→`иванов`, `?`→`""`, `-`→`""`, `None`→`""` ; et `athlete_identity_keys(nom, prenom)` qui rend `(None, None)` si la clé du nom est vide, `(clé, "")` si le prénom est vide
- [X] T004 [P] Tests de migration dans `backend/tests/test_migrations.py` (motif « upgrade à `d49e03833de6`, insérer, upgrade, vérifier ») : clés rétro-remplies ; `LETORT Leo` (id bas) et `LETORT Léo` (id haut) reçoivent les rangs 0 et 1 ; une fiche `?` a des clés NULL ; l'ancienne contrainte `(nom, prenom, birth_date)` et `ix_athletes_identity` n'existent plus ; la nouvelle contrainte refuse un second rang 0 de même clé ; la règle figée dans la migration donne les mêmes clés que `identity_key` sur la liste de T003 ; downgrade refusé avec un message nommant les doublons quand deux fiches ont mêmes `nom, prenom, birth_date`
- [X] T005 [P] Tests repository dans `backend/tests/test_repositories/test_athlete_repository.py` : `create_batch`, `resolve`, `get_or_create` et `update_identity` écrivent les deux clés ; renommer une fiche recalcule ses clés

### Implémentation

- [X] T006 Créer `backend/app/core/athlete_identity.py` : `identity_key(text)` (NFKD, retrait des marques combinantes, `casefold`, `œ→oe`, `æ→ae`, filtre `str.isalnum`, alphanumériques Unicode) et `athlete_identity_keys(nom, prenom)` ; docstring en anglais citant #907 et la raison du calcul en Python (`unaccent` non immuable, `research.md` R1)
- [X] T007 Modifier `backend/app/models/athlete.py` : colonnes `last_name_key`, `first_name_key` (String, nullable), `homonym_rank` (Integer, NOT NULL, `server_default="0"`) ; `UniqueConstraint("last_name_key", "first_name_key", "homonym_rank", name="uq_athlete_identity")` à la place de l'ancienne ; retirer `ix_athletes_identity` ; ajouter les index d'expression `last_name_key || first_name_key` et `first_name_key || last_name_key` (`research.md` R4)
- [X] T008 Générer puis relire la migration `backend/alembic/versions/<rev>_athlete_identity_key.py` (`down_revision = "d49e03833de6"`, docstring française #907) : ajout des colonnes ; rétro-remplissage en Python par lots de 5 000 avec la règle **figée dans le fichier** (modèle `ccda2de245af_normalize_athlete_gender.py`) ; rangs par `id` croissant dans chaque groupe de même clé ; suppression de l'ancienne contrainte et de `ix_athletes_identity` (`batch_alter_table` pour SQLite) ; nouvelle contrainte et index ; downgrade avec contrôle `GROUP BY nom, prenom, birth_date HAVING count(*) > 1` qui lève `RuntimeError` (modèle `b2c3d4e5f6a7_course_identity_is_relay.py`)
- [X] T009 Les clés sont écrites par un écouteur d'ORM `before_insert`/`before_update` sur `Athlete` (`backend/app/models/athlete.py`, `_store_identity_keys`), qui couvre tous les chemins d'écriture (`create_batch`, `resolve`, `get_or_create`, `update_identity`, fixtures de test) ; l'appelant ne les fournit jamais
- [ ] T010 (SQLite fait ; PostgreSQL délégué au job CI `backend-postgres`, pas de serveur local) Vérifier `uv run alembic upgrade head`, `uv run alembic check`, `downgrade -1`, `upgrade head` sur SQLite, puis sur un PostgreSQL 16 jetable (`quickstart.md`) ; mesurer la durée du rétro-remplissage sur la base de démo de `scripts/reset_db.py`

- [X] T011 Appliquer l'amendement PATCH de `.specify/memory/constitution.md` dans la PR 1 (Sync Impact Report en tête, version incrémentée) ; la PR 1 n'est pas fusionnée tant que l'issue T002 n'est pas approuvée
- [ ] T012 Mesurer la durée de la migration sur une copie de la base de preview (volume de production) et la consigner dans la PR 1 ; au-delà de 5 minutes, revoir la taille des lots avant fusion (Render applique les migrations au démarrage)

**Checkpoint**: clés stockées, contrainte en place, constitution amendée, suite verte. Le comportement d'import n'a pas encore changé.

---

## Phase 3: User Story 1, une graphie différente ne crée plus de fiche (P1) 🎯 MVP

**Sous-issues**: #907 (résolution par clé), #908 (repli inversion et concaténation, point 1 de la demande)

**Goal**: à l'import, une graphie équivalente, inversée ou concaténée rejoint la fiche existante.

**Independent Test**: importer une épreuve contenant des personnes connues sous une autre graphie ; aucune fiche créée, résultats sur les fiches existantes (spec US1, scénarios 1 à 6).

### Tests (rouges d'abord)

- [X] T013 [P] [US1] Tests repository dans `backend/tests/test_repositories/test_athlete_repository.py` : `get_by_identity_keys_batch` ne rend que des fiches de rang 0, quelle que soit `birth_date` ; `find_fallback_matches` trouve l'inversion, la fiche dont la concaténation vaut un nom seul, et la fiche à prénom vide dont le nom vaut la concaténation de la ligne ; plusieurs fiches candidates → aucun résultat
- [X] T014 [P] [US1] Tests d'import dans `backend/tests/test_services/test_import_service.py` : `LETORT Leo` sur fiche `LETORT Léo`, `LEGLOANIC Fabien` sur `LE GLOANIC Fabien`, `L APPARTIEN Marie` sur `L'APPARTIEN Marie`, `MORIARTY Alexander` sur `ALEXANDER Moriarty`, `DUPONT JEAN` (prénom vide) sur `DUPONT Jean`, `DUPONT`/`Jean` sur une fiche `DUPONT JEAN` sans prénom → nombre de fiches inchangé et résultat sur la fiche existante ; `CIC 7` et `CIC 9` restent distinctes ; une identité directe existante (`MARTIN Thomas`) l'emporte sur l'inversion (`THOMAS Martin`) ; un nom concaténé ambigu crée une fiche et figure au rapport ; une ligne à clé vide (`-`) sans dossard est écartée et comptée, et son rescrape ne crée ni fiche ni participation ; avec dossard, elle devient « Anonyme <épreuve>-<dossard> » et son rescrape ne crée ni fiche ni réconciliation

### Implémentation

- [X] T015 [US1] Dans `backend/app/repositories/athlete_repository.py`, remplacer `get_by_identities_batch` par `get_by_identity_keys_batch(keys)` (filtre `homonym_rank == 0`, plus de clause `birth_date`, dictionnaire indexé par clé) et `get_by_identity` par `get_by_identity_keys` ; supprimer les anciennes fonctions et leurs appels (pas de compatibilité, `AGENTS.md`)
- [X] T016 [US1] Ajouter `find_fallback_matches(keys)` dans `backend/app/repositories/athlete_repository.py` (`research.md` R4) : une requête groupée sur l'inversion et les deux concaténations, ne rendant une correspondance que si elle est unique
- [X] T017 [US1] Dans `backend/app/services/import_service.py`, remplacer `_pair_key`/`_identity_key` par `athlete_identity_keys` ; `_resolve_pending` résout par clé, puis par `find_fallback_matches` pour les clés restées sans fiche, avant `create_batch` ; une ligne à clé vide sans dossard est écartée et comptée avec les noms masqués (#897) ; les équipiers de relais (`_oriented_teammates`) passent par les mêmes clés
- [X] T018 [US1] Ajouter au rapport d'import `ambiguous_identities` (lignes dont le repli a trouvé plusieurs fiches) dans `backend/app/services/import_service.py` et l'événement SSE `done` ; documenter la clé dans `docs/api/admin-donnees.md`
- [X] T019 [US1] Mettre à jour `admin_actions.set_teammates` (`backend/app/services/admin_actions.py`) pour la résolution par clé

**Checkpoint**: US1 livrable seule (PR 1 avec la phase 2). Le stock existant n'est pas encore fusionné.

---

## Phase 4: User Story 2, une correction d'administrateur survit aux imports (P1)

**Sous-issues**: #900, #896

**Goal**: date de naissance, renommage et réattribution admin résistent au rescrape et aux nouveaux imports.

**Independent Test**: spec US2, scénarios 1 à 4.

### Tests (rouges d'abord)

- [ ] T020 [P] [US2] Test de non-régression #900 dans `backend/tests/test_services/test_import_service.py` : import, `update_athlete(birth_date=1990-01-01)`, rescrape de la même épreuve, import d'une nouvelle épreuve → la fiche datée garde toutes ses participations et gagne la nouvelle ; aucune fiche NULL créée
- [ ] T021 [P] [US2] Tests #896 dans `backend/tests/test_services/test_rescrape_service.py` : réattribution **avec dossard** de A vers B puis rescrape → reste sur B ; **sans dossard** → reste sur B, une seule participation, A recréée vide puis purgée ou jamais recréée ; un résultat jamais corrigé dont le chronométreur corrige le nom est encore réconcilié
- [ ] T022 [P] [US2] Tests de migration dans `backend/tests/test_migrations.py` : `athlete_locked` à faux et `source_identity_key` rétro-remplie depuis la fiche de chaque participation
- [ ] T023 [P] [US2] Test dans `backend/tests/test_services/test_admin_actions.py` : `reassign_participation` pose `athlete_locked` ; `update_athlete` vérifie l'unicité sur la clé normalisée (renommer `Leo` en `Léo` vers une fiche existante → 409)

### Implémentation

- [ ] T024 [US2] Modifier `backend/app/models/participation.py` : `athlete_locked` (Boolean, NOT NULL, `server_default` faux), `source_identity_key` (String, nullable)
- [ ] T025 [US2] Migration `backend/alembic/versions/<rev>_participation_source_identity.py` (docstring #896) : colonnes, rétro-remplissage de `source_identity_key` par lots depuis les clés de la fiche (`"<last>|<first>"`), downgrade qui supprime les colonnes
- [ ] T026 [US2] Mesurer la durée de la migration T025 sur une copie de la base de preview et la consigner dans la PR 2 (même seuil que T012)
- [ ] T027 [US2] Dans `backend/app/services/import_service.py` : écrire `source_identity_key` à chaque création et mise à jour ; dans `add()`, une ligne appariée par dossard à une participation `athlete_locked` ne fait que `_upsert` (même branche que `teammate_links`) ; le multiset sans dossard (`_index_course`, `_without_bib`, `_credits`, `_match_without_bib`) est indexé par `source_identity_key` et l'appariement remonte avant la résolution d'identité
- [ ] T028 [US2] Dans `_reconcile_resolved` (`backend/app/services/import_service.py`) : ne déplacer une participation que si la clé scrapée diffère de la clé de sa fiche actuelle (règle `research.md` R5, étendue aux variantes en phase 7)
- [ ] T029 [US2] Dans `backend/app/services/admin_actions.py` : `reassign_participation` pose `athlete_locked` via `participation_repository.reassign` ; `update_athlete` vérifie l'unicité par `get_by_identity_keys` et ne compare plus `birth_date`
- [ ] T030 [US2] Mettre à jour la docstring de l'ancienne recherche par lot et `specs/20260828-131039-import-batch-persist/research.md` (décision « identité athlète ») pour renvoyer à #1146 et à l'abandon du filtre `birth_date IS NULL`

**Checkpoint**: corrections admin protégées (PR 2). US1 et US2 tiennent ensemble.

---

## Phase 5: User Story 3, deux imports simultanés ne créent jamais deux fiches (P2)

**Sous-issue**: #981

**Goal**: création idempotente garantie par la base.

**Independent Test**: spec US3, scénarios 1 à 3 (PostgreSQL pour 1 et 2).

### Tests (rouges d'abord)

- [ ] T031 [P] [US3] Créer `backend/tests/test_repositories/test_athlete_identity_concurrency.py` (sauté hors PostgreSQL, fixture à deux sessions sur le même bind, modèle `test_lock_repository.py`) : deux transactions créent 300 identités neuves communes (dont des graphies équivalentes) en parallèle → 300 fiches à la fin, aucune exception ; répété 10 fois
- [ ] T032 [P] [US3] Dans `backend/tests/test_repositories/test_athlete_identity_concurrency.py` : la résolution par `get_by_identity_keys_batch` prend `FOR KEY SHARE` ; une seconde session qui tente `SELECT … FOR UPDATE` sur la fiche résolue attend le commit de la première
- [ ] T033 [P] [US3] Test SQLite dans `backend/tests/test_repositories/test_athlete_repository.py` : `create_batch` sur une clé déjà présente rend la fiche existante sans erreur ni doublon

### Implémentation

- [ ] T034 [US3] Réécrire `create_batch` dans `backend/app/repositories/athlete_repository.py` : `insert(...).on_conflict_do_nothing(index_elements=[last_name_key, first_name_key, homonym_rank]).returning(Athlete.id)` choisi selon `bind.dialect.name` (`postgresql`/`sqlite`), puis relecture par clé des identités non retournées ; rendre des objets `Athlete` attachés à la session ; sur PostgreSQL, `get_by_identity_keys_batch` et `find_fallback_matches` prennent `FOR KEY SHARE` sur les fiches rendues (`research.md` R7)
- [ ] T035 [US3] Lancer `TEST_POSTGRES_URL=… uv run pytest tests/test_repositories -n 0` en local et vérifier que le job CI `backend-postgres` (`.github/workflows/ci.yml`) exécute le nouveau fichier

**Checkpoint**: concurrence garantie (PR 3).

---

## Phase 6: User Story 4, deux homonymes sur une même épreuve gardent deux fiches (P2)

**Sous-issue**: #967

**Goal**: un dossard neuf sur une fiche déjà présente sur l'épreuve individuelle crée une fiche d'homonyme ; revue seulement si le club est touché.

**Independent Test**: spec US4, scénarios 1 à 6.

### Tests (rouges d'abord)

- [ ] T036 [P] [US4] Tests d'import dans `backend/tests/test_services/test_import_service.py` : deux lignes `MARTIN Thomas` aux dossards distincts sur une épreuve individuelle → deux fiches (rangs 0 et 1), `homonyms_created` au rapport ; rescrape de l'épreuve → les deux fiches gardent leur participation ; nouvelle épreuve `MARTIN Thomas` sans conflit → fiche de rang 0 ; épreuve en relais → comportement inchangé ; dossard déjà présent dans la même tranche de lignes compté aussi ; une ligne `THOMAS Martin` dont le repli (inversion) trouve une fiche déjà présente sur l'épreuve avec un autre dossard crée la fiche principale `THOMAS Martin`, pas un homonyme
- [ ] T037 [P] [US4] Test repository dans `backend/tests/test_repositories/test_athlete_repository.py` : `create_homonym(nom, prenom, …)` prend `max(rank)+1` et retente sur conflit

### Implémentation

- [ ] T038 [US4] Ajouter `create_homonym` dans `backend/app/repositories/athlete_repository.py` (insertion au rang suivant, `ON CONFLICT DO NOTHING` puis nouvel essai, au plus 5)
- [ ] T039 [US4] Dans `backend/app/services/import_service.py` : `_index_course` tient `athlete_id → dossards` pour les épreuves non relais, complété au fil des lignes attribuées ; dans `_resolve_pending`, une ligne à dossard neuf dont la fiche résolue porte un autre dossard sur l'épreuve passe par `create_homonym` ; une correspondance obtenue par repli et en conflit est ignorée au profit de la création de la fiche principale de la clé directe (`research.md` R4) ; rapport `homonyms_created: [{course_id, bib, athlete_id, homonym_of}]` dans `persist_results` et l'événement SSE `done`
- [ ] T040 [US4] Documenter `homonyms_created` et la règle FR-008 dans `docs/api/admin-donnees.md` et `backend/app/models/AGENTS.md` (rang d'homonyme)

**Checkpoint**: homonymes séparés à l'import (PR 4). La revue des cas du club arrive avec la phase 7.

---

## Phase 7: User Story 5, un administrateur fusionne deux fiches (P2)

**Sous-issues**: #908 (points 2 et 3), #907 (point 3), #967 (point 3, revue)

**Goal**: fusion admin avec aperçu, refus nommés, variantes mémorisées ; revue d'identité.

**Independent Test**: spec US5, scénarios 1 à 7 ; revue des cas US4 scénarios 2, 3 et 5.

### Tests backend (rouges d'abord)

- [ ] T041 [P] [US5] Tests de migration dans `backend/tests/test_migrations.py` : tables `athlete_aliases` (unique sur la clé) et `ignored_athlete_pairs` (unique sur la paire), cascades
- [ ] T042 [P] [US5] Créer `backend/tests/test_services/test_athlete_merge.py` (fixture `db_session_fk`) : déplacement des participations, équipiers, bénévolat, validations (saison des deux côtés → une seule ligne), compte membre ; club verrouillé, genre et date de naissance repris si absents ; variante ajoutée et variantes de l'absorbée repointées ; conservée de rang 1 qui reprend le rang 0 ; refus `same_athlete`, `distinct_users`, `same_course_bibs`, `same_participation`, `distinct_birth_dates` sans aucune écriture ; une seule entrée `athlete.merge` sans `birth_date` ; `merge_impact` sans écriture
- [ ] T043 [P] [US5] Test PostgreSQL à deux sessions dans `backend/tests/test_repositories/test_athlete_identity_concurrency.py` : un import résout la fiche B, une fusion de B dans A démarre et attend, l'import insère une participation vers B et commite, la fusion reprend et déplace aussi cette participation ; dans l'ordre inverse, l'import qui résout après le commit de la fusion trouve A par la variante ; aucune violation de clé étrangère ; un import qui tient la fiche plus de 5 s fait répondre 409 à la fusion, sans écriture
- [ ] T044 [P] [US5] Tests d'import dans `backend/tests/test_services/test_import_service.py` : après fusion de `DUPOMT Jean` dans `DUPONT Jean`, une nouvelle épreuve `DUPOMT Jean` rejoint `DUPONT Jean` ; le rescrape de l'épreuve d'origine ne recrée pas `DUPOMT` et ne déplace pas la participation
- [ ] T045 [P] [US5] Créer `backend/tests/test_services/test_athlete_identity_review.py` : motifs `same_course_bibs` (seulement si la fiche relève du club), `club_homonym` (seulement si l'un relève du club, via `Athlete.club` ou `Participation.club`), `swapped`, `concatenated`, `alias_collision` ; paires écartées exclues ; ordre stable ; `ignore_pair` 400/404/409 et journal `athlete_identity.ignore`
- [ ] T046 [P] [US5] Tests API dans `backend/tests/test_api/test_admin_data_api.py` et nouveau `backend/tests/test_api/test_admin_athlete_identity_api.py` : routes de `contracts/admin-api.md`, 401 avant 403, `athletes:write` exigé, 409 de `PATCH /admin/athletes/{id}` avec `conflicting_athlete_id`

### Implémentation backend

- [ ] T047 [P] [US5] Créer `backend/app/models/athlete_alias.py` et `backend/app/models/ignored_athlete_pair.py` (`data-model.md`), les exporter dans `backend/app/models/__init__.py`
- [ ] T048 [US5] Migration `backend/alembic/versions/<rev>_athlete_aliases_and_review.py` (docstring #908) : création des deux tables, downgrade qui les supprime
- [ ] T049 [P] [US5] Créer `backend/app/repositories/athlete_alias_repository.py` (`get_by_keys_batch`, `add`, `repoint`, `collisions`) et `backend/app/repositories/ignored_athlete_pair_repository.py` (`create`, `exists`, `all_pairs`, paire normalisée low/high)
- [ ] T050 [US5] Ajouter les requêtes de fusion, chacune dans le repository de sa table : participations et équipiers dans `backend/app/repositories/participation_repository.py`, bénévolat dans `volunteer_action_repository.py`, validations (dédoublonnage par saison) dans `season_validation_repository.py`, comptes dans `user_repository.py`, verrou `FOR UPDATE` et détection des refus dans `athlete_repository.py` ; et dans `athlete_repository.py` et les requêtes de candidats de revue (groupes de même clé, `tcn_clause` de `app/core/club.py`)
- [ ] T051 [US5] Créer `backend/app/services/athlete_merge.py` (`merge_impact`, `merge_athletes`) sur le modèle de `backend/app/services/course_merge.py` : `SELECT … FOR UPDATE` sur les deux fiches (ordre d'id, `lock_timeout` de 5 s sur PostgreSQL, 409 au-delà) puis `lock_courses_or_409` sur leurs épreuves, lecture des références seulement après, refus en `DomainError` français, `flush` seulement, journal via `app/services/audit.record`
- [ ] T052 [US5] Dans `backend/app/services/import_service.py` : résolution étape 2 par `athlete_alias_repository.get_by_keys_batch` ; la règle de réconciliation (T028) tient compte des variantes de la fiche actuelle
- [ ] T053 [US5] Dans `backend/app/services/admin_actions.py` : `update_athlete` vérifie aussi les variantes et joint `conflicting_athlete_id` au 409 (champ additif de l'erreur sérialisée)
- [ ] T054 [US5] Créer `backend/app/services/athlete_identity_review.py` (`find_candidates`, `count`, `ignore_pair`) sur le modèle de `backend/app/services/course_duplicates.py`
- [ ] T055 [US5] Schémas dans `backend/app/schemas/admin.py` (`AthleteMergeRequest`, `AthleteMergeImpact`) et nouveau `backend/app/schemas/athlete_identity.py` (candidats, écart) ; routes `merge-impact` et `merge` dans `backend/app/api/v1/admin_data.py` ; nouveau routeur `backend/app/api/v1/admin_athlete_identity.py` enregistré avec les autres routeurs admin ; commit dans le routeur, `capture_event` comme les routes voisines

### Tests frontend (rouges d'abord)

- [ ] T056 [P] [US5] Créer `frontend/components/athletes/MergeAthleteDialog.test.tsx` : recherche de la seconde fiche, aperçu (`moves`, `blocking_label`), bouton désactivé si refus, confirmation, toast, invalidation des caches ; et étendre `frontend/components/athletes/AthleteAdminPanel.test.tsx` : commande absente sans `athletes:write`, 409 de renommage qui propose la fusion
- [ ] T057 [P] [US5] Créer `frontend/components/admin/AthleteIdentityReviewTable.test.tsx` : chargement, vide, erreur, une carte par candidat avec ses conflits, « Écarter » (absent pour `same_course_bibs`) et « Fusionner »

### Implémentation frontend

- [ ] T058 [US5] Ajouter à `frontend/lib/api/client.ts` `getAthleteMergeImpact`, `mergeAthletes`, `listAthleteIdentityReview`, `countAthleteIdentityReview`, `ignoreAthleteIdentityPair` ; hooks dans `frontend/lib/queries/admin.ts` et clés dans `frontend/lib/queries/keys.ts`
- [ ] T059 [US5] Créer `frontend/components/athletes/MergeAthleteDialog.tsx` (réutilise `AthleteSearchPicker`, modèle `frontend/components/admin/MergeCoursesDialog.tsx`) et le brancher dans `frontend/components/athletes/AthleteAdminPanel.tsx`, y compris depuis le 409 de renommage
- [ ] T060 [US5] Créer `frontend/components/admin/AthleteIdentityReviewTable.tsx` et `frontend/app/admin/identites/page.tsx` (modèle `frontend/app/admin/doublons/page.tsx`) ; entrée de navigation et badge dans `frontend/components/layout/nav.config.ts`, `frontend/lib/queries/nav-badges.ts`, `frontend/components/layout/AppNav.tsx` ; microcopie française

**Checkpoint**: fusion et revue opérationnelles (PR 5, scindable en backend puis frontend).

---

## Phase 8: User Story 6, reprise des doublons existants (P3)

**Sous-issues**: #906 (point 3), #907 (point 2), #908 (point 2), #900 (vérification de production)

**Goal**: renormaliser et fusionner le stock, simulation d'abord.

**Independent Test**: spec US6, scénarios 1 à 7.

### Tests (rouges d'abord)

- [ ] T061 [P] [US6] Créer `backend/tests/test_services/test_athlete_reconciliation.py` : renormalisation des trois formes « NOM, Prénom » (avec et sans jumeau, `source_identity_key` recalculée) ; groupes de même clé fusionnés dans le rang 0 ; groupe à dossards distincts sur une même épreuve laissé en revue ; paires inversées et concaténées fusionnées seulement si même club ou même genre (renseigné des deux côtés, deux clubs vides ne comptent pas) et jamais sur une même épreuve (Q3) ; fiche datée et homonyme non daté fusionnés ; fiches factices intactes ; simulation sans écriture et opérations identiques à l'application ; relance → aucune opération ; interruption simulée après N fusions puis relance → résultat identique à un passage complet
- [ ] T062 [P] [US6] Créer `backend/tests/test_cli/test_reconcile_athletes.py` (modèle `test_purge_timepulse_duplicates.py`, fixture `brancher_session`) : simulation code 0 et JSON seul sur stdout ; `--yes` sans `--by-email` → 2 ; compte inconnu → 2 ; application → fusions journalisées sous ce compte ; Ctrl-C → 130 avec rapport partiel

### Implémentation

- [ ] T063 [US6] Créer `backend/app/services/athlete_reconciliation.py` : `plan(db)` rend les opérations par famille (`contracts/cli-reconcile-athletes.md`) ; `apply(db, plan, user_id)` exécute chaque opération dans sa transaction via `athlete_merge.merge_athletes` ou un renommage repository ; requêtes de candidats dans `backend/app/repositories/athlete_repository.py`
- [ ] T064 [US6] Créer `backend/app/cli/commands/reconcile_athletes.py`, l'enregistrer dans `backend/app/cli/__init__.py` (`reconcile-athletes`), rendu texte dans `backend/app/cli/reports.py`, codes via `emit_outcome`
- [ ] T065 [US6] Documenter la commande dans `backend/app/cli/AGENTS.md` et la procédure de production dans `docs/ci-cd.md` (à côté de `purge-timepulse-duplicates` : pare-feu, simulation relue, application, relance de contrôle, requête SC-001 de #907)

**Checkpoint**: reprise prête (PR 6). Elle se lance en production après la PR parapluie.

---

## Phase 9: Polish & Cross-Cutting

- [ ] T066 [P] Mettre à jour `docs/modele-donnees.md` (identité, tableau des contraintes, variantes, rang d'homonyme) et `backend/app/models/AGENTS.md` (inventaire des références à `athletes.id`, nouvelles tables)
- [ ] T067 [P] Mettre à jour `docs/api/admin-donnees.md` : fusion, revue d'identité, 409 enrichi, `homonyms_created`, `ambiguous_identities`
- [ ] T068 Vérification complète selon `quickstart.md` : suites backend et front, `ruff`, `npm run lint`, `npm run build`, tests PostgreSQL, parcours bout en bout en dev
- [ ] T069 Essai de la reprise en simulation sur la base de preview (Supabase) et comparaison de ses chiffres aux mesures du 2026-09-24 des sous-issues ; écarts consignés dans la PR parapluie

---

## Dependencies & Execution Order

### Phases

- **Setup (1)** → **Foundational (2)** → bloque tout le reste.
- **US1 (3)** dépend de 2.
- **US2 (4)** dépend de 3 (résolution par clé, règle de réconciliation).
- **US3 (5)** dépend de 3 : T034 pose `FOR KEY SHARE` dans `get_by_identity_keys_batch` et `find_fallback_matches`, créées en phase 3. Seuls T031 et T033 (tests) peuvent s'écrire plus tôt.
- **US4 (6)** dépend de 4 (réconciliation par clé, sinon les fiches d'homonyme sont vidées au rescrape) et de 5 (`ON CONFLICT` pour `create_homonym`).
- **US5 (7)** dépend de 4 et 6 (refus `same_course_bibs`, variantes dans la réconciliation).
- **US6 (8)** dépend de 7 (réutilise la fusion).
- **Polish (9)** au fil des PR ; T069 après 8.

### Dans chaque phase

Tests rouges → modèles → migration → repositories → services → API → front. Les tâches [P] d'une même phase touchent des fichiers distincts.

### PR

| PR | Phases | Sous-issues | Base et cible |
| --- | --- | --- | --- |
| 1 | 2, 3 | #907, #908 (résolution) | `epic/1146-athlete-identity` |
| 2 | 4 | #900, #896 | idem |
| 3 | 5 | #981 | idem |
| 4 | 6 | #967 | idem |
| 5 | 7 | #908, #907, #967 (revue) | idem |
| 6 | 8 | #906 | idem |
| parapluie | 9 | `Closes #1146` et les sept sous-issues | `epic/1146-athlete-identity` → `main` |

## Parallel Examples

```text
Phase 2 : T003, T004, T005 ensemble (trois fichiers de test).
Phase 3 : T013 et T014 ensemble.
Phases 3 et 5 : T031 et T033 (tests de concurrence) peuvent s'écrire pendant la phase 3 ; T034 et T035 attendent sa fin.
Phase 7 : T041 à T046 ensemble, puis T047 et T049 ensemble ; côté front T056 et T057 ensemble.
Phase 8 : T061 et T062 ensemble.
```

## Implementation Strategy

1. **MVP** : phases 1 à 3. L'hémorragie s'arrête, aucune nouvelle fiche scindée par une graphie.
2. Phase 4 : les corrections admin tiennent ; prérequis de toute correction durable.
3. Phases 5 et 6 : la base garantit l'identité, les homonymes sont séparés.
4. Phase 7 : outil de correction pour les cas ambigus.
5. Phase 8 : reprise du stock en production, une seule fois, après déploiement de la PR parapluie.

Chaque PR laisse `epic/1146-athlete-identity` verte et déployable.
