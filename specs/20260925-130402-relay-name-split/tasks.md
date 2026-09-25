---

description: "Tasks : découper à l'import les relais qui nomment leurs équipiers (#895)"
---

# Tasks: Découper à l'import les relais qui nomment leurs équipiers

**Input**: Design documents from `specs/20260925-130402-relay-name-split/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/relay-teammates-rule.md, quickstart.md

**Tests**: Principe III (TDD sans réseau, non négociable). Chaque tâche d'implémentation
est précédée d'une tâche de test qui **doit échouer** avant l'implémentation. Tous les tests
sont sans réseau (`ScrapedResult` construits ou fixtures fichiers).

**Organization**: une phase par user story de `spec.md`. Toutes les commandes se lancent
depuis `backend/`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallélisable (fichier différent, aucune dépendance sur une tâche non finie)
- **[Story]**: US1 à US4 (`spec.md`)

## Rappels transverses

- Condition d'application : `scraped.is_relay` seulement (research R4).
- Valeur publiée reconstituée : `" ".join(filter(None, [athlete_name, athlete_firstname]))`,
  la même formule que la clé `_team_key` du rescrape (`import_service.py:694`).
- Tests en anglais pour les identifiants neufs (Principe I) ; les tests existants de
  `test_import_service.py` gardent leur style.

---

## Phase 1: Setup

**Purpose**: établir la ligne de base de la branche.

- [X] T001 Lancer `uv sync` puis `uv run pytest -m "not integration" -q` depuis `backend/` et noter les échecs préexistants (attendu : seul `test_cors_origins_defaut`) dans la description de PR à venir ; aucun code touché.

---

## Phase 2: Foundational (bloquant pour toutes les stories)

**Purpose**: la règle pure et la création en lot des compositions.

- [X] T002 [P] Écrire les tests de `split_relay_teammates` dans `backend/tests/test_scrapers_utils.py` : un `pytest.mark.parametrize` avec **chaque ligne** du tableau d'exemples de `specs/20260925-130402-relay-name-split/contracts/relay-teammates-rule.md` (valeur d'entrée → sortie attendue, `None` compris), plus : `QUILLET/BRILLANT CAMPBELL/ROUSSEAU Guillaume/Alex/Jean Philippe` → 3 paires dont `("BRILLANT CAMPBELL", "Alex")` ; 9 équipiers → `None` ; `DUPONT Jéan / DUPONT Jean` → `None` (doublon sans accents) ; `LEGEARD/LEGEARD/LEGEARD Anne/Paul/Marc` → 3 paires. Vérifier qu'ils échouent (fonction absente).
- [X] T003 Implémenter `split_relay_teammates(published: str) -> list[tuple[str, str]] | None` dans `backend/app/scrapers/utils.py`, juste après `split_athlete_name`, en suivant pas à pas la section « Règle » du contrat (listes parallèles via `split_athlete_name`, puis segments ; au moins deux lettres par nom et prénom ; 2 à 8 équipiers ; doublons comparés avec `deaccent` déjà utilisé dans le projet, cf. `app/services/admin_actions.py`). Docstring technique en anglais ; un commentaire français court par règle métier non évidente (suffixe « . » de klikego, lecture « NOM PRÉNOM » des segments tout majuscules). T002 au vert.
- [X] T004 [P] Écrire dans `backend/tests/test_repositories/test_participation_repository.py` un test de `create_batch` : deux participations dont une avec la clé `teammate_ids=[a.id, b.id]` → la première a `teammates == [a, b]` (positions 0 et 1), la seconde aucune composition ; les champs sans `teammate_ids` fonctionnent comme avant. Vérifier l'échec.
- [X] T005 Faire accepter à `create_batch` (`backend/app/repositories/participation_repository.py`) une clé optionnelle `teammate_ids` par dict : retirée des champs, convertie en `ParticipationTeammate(athlete_id=…, position=…)` sur `teammate_links`, le tout dans l'unique `db.flush()` existant. T004 au vert, `uv run pytest tests/test_repositories/test_participation_repository.py`.

**Checkpoint**: règle et création en lot prêtes ; `_Persister` pas encore touché.

---

## Phase 3: User Story 1 - Un relais aux équipiers nommés apparaît sur la fiche de chacun dès l'import (Priority: P1) 🎯 MVP

**Goal**: une ligne relais découpable crée un résultat composé (porteur = équipier 1, `team_name`, composition) et aucune fiche d'équipe.

**Independent Test**: importer une épreuve relais avec `CANNIOU/OLIVIER` + `Cedric/Leclerc` ; deux fiches de personnes portent le résultat, aucune fiche ne porte le nom d'équipe.

### Tests for User Story 1

- [X] T006 [US1] Dans `backend/tests/test_services/test_import_service.py`, nouvelle section « Relais nommés découpés à l'import (#895) » : test d'un import neuf, forme timepulse (`_result("7", "CANNIOU/OLIVIER", "Cedric/Leclerc", is_relay=True, event_type="triathlon-s")`) → une participation, `athlete_id` = fiche `CANNIOU Cedric`, `teammates` = [`CANNIOU Cedric`, `OLIVIER Leclerc`] dans cet ordre, `team_name == "CANNIOU/OLIVIER Cedric/Leclerc"`, `get_by_identity(db, "CANNIOU/OLIVIER", "Cedric/Leclerc", None) is None`, compteur `imported == 1`.
- [X] T007 [US1] Même fichier : forme klikego sans dossard (`_result("", "MASSONNEAU PIERRE", "/ BESANCON FABIEN .", …)`) avec une fiche `MASSONNEAU Pierre` (club « TRI CLUB ») créée avant l'import → le résultat réutilise cette fiche (aucun doublon, comparaison sans casse), la fiche `BESANCON FABIEN` est créée avec nom et prénom seuls (`gender == ""`, `club is None`), le club de `MASSONNEAU` n'est pas écrasé par le club de l'équipe.
- [X] T008 [US1] Même fichier : deux lignes relais découpables dans le même lot, dont une avec dossard et une sans, plus une ligne individuelle ordinaire sur une autre épreuve → les deux relais sont composés, la ligne individuelle est inchangée ; forcer `_TRANCHE_SIZE` à 1 par `monkeypatch` dans une variante pour couvrir la résolution en plusieurs tranches.
- [X] T009 [P] [US1] Dans `backend/tests/test_oktime.py` : à partir de la fixture `oktime_lacanau_48555.json`, obtenir les `ScrapedResult` de la course « Relais L & Duo » par la fonction de parsing existante utilisée dans ce fichier, les persister avec `import_service.persist_results(db_session, url, results)`, et vérifier que la ligne `GUILLON RÉMI / CHARPENTIER EMMANUEL` est composée de `("GUILLON", "RÉMI")` et `("CHARPENTIER", "EMMANUEL")`.
- [X] T010 [P] [US1] Dans `backend/tests/test_chronoplace.py` : même démarche avec `EPREUVE_566` → `MENARDAIS FERDINAND / COMPAIN LENA` composée ; `LE BOZEC HENRI / BABINET SYLVAIN` reste une fiche d'équipe sans composition.

### Implementation for User Story 1

- [X] T011 [US1] Dans `backend/app/services/import_service.py` : ajouter `teammates: tuple[tuple[str, str], ...] | None = None` à `_PendingResolution` ; dans `_Persister.add()`, **après** les deux chemins existants de #997 (dossard apparié à un relais composé, relais sans dossard retrouvé par `_teams_without_bib`), calculer `split_relay_teammates` (importée par nom, `from app.scrapers.utils import split_relay_teammates`, pour que T017 puisse la remplacer) sur la valeur reconstituée quand `scraped.is_relay`, et le passer à `_enqueue` (nouveau paramètre). Une ligne découpée sur le chemin dossard ne passe pas par `_reconcile_blocked`.
- [X] T012 [US1] Dans `_resolve_pending()` : ajouter les paires des équipiers à la recherche `get_by_identities_batch` ; créer par `create_batch` les équipiers manquants avec `{"nom", "prenom", "gender": "", "birth_date": None, "club": None}` ; **ne pas** créer l'identité d'équipe d'une ligne découpée ; ne pas synchroniser le club d'un équipier ; pour une ligne découpée sans participation existante, construire les champs par `mapping.participation_fields(..., athlete_id=<équipier 1>)`, poser `team_name` = valeur reconstituée et `teammate_ids`. T006 à T010 au vert.

**Checkpoint**: US1 livrable seule (MVP).

---

## Phase 4: User Story 2 - Un nom de groupe reste une fiche d'équipe attribuable à la main (Priority: P1)

**Goal**: toute ligne non découpable, ou dont un équipier est déjà sur l'épreuve, suit le chemin d'aujourd'hui.

**Independent Test**: importer une épreuve relais mêlant `TEAM GV .`, `LES BARBAPAPAS | Alex et Margot`, `LE BRAS LUC / LE PAGE GUULLAUME .` : trois fiches d'équipe, aucune composition, `team_name` vide.

### Tests for User Story 2

- [X] T013 [US2] Dans `backend/tests/test_services/test_import_service.py` : les trois lignes ci-dessus → trois fiches d'équipe à leur nom publié, `teammates == []`, `team_name is None` ; puis `admin_actions.set_teammates` sur l'une d'elles fonctionne comme dans les tests #894 existants.
- [X] T014 [US2] Même fichier : garde FR-010. (a) `DUPONT Jean` a déjà un résultat individuel sur la course relais, puis une ligne `DUPONT Jean / MARTIN Paul` arrive → la ligne n'est pas découpée (fiche d'équipe comme aujourd'hui) et l'import réussit ; (b) deux lignes du **même lot** partagent `MARTIN Paul` → la première est composée, la seconde retombe sur une fiche d'équipe.
- [X] T015 [P] [US2] Dans `backend/tests/test_chronoweb.py` et `backend/tests/test_sporthive.py` : persister les relais des fixtures `chronoweb/event_aquathlon_relais.html` (`CREUSOTRI`, `FRATERIES POZZEBON/SKLADZIEN`) et `sporthive_relay.json` (`LA COUSINADE`…) par `persist_results` → aucune composition, fiches d'équipe à leur nom publié.

### Implementation for User Story 2

- [X] T016 [US2] Dans `_resolve_pending()` (`backend/app/services/import_service.py`), garde FR-010 décidée **après** la recherche `get_by_identities_batch` et **avant** de constituer `to_create` (une ligne refusée doit pouvoir créer son identité d'équipe), sur deux ensembles :
  1. **ids** des athlètes déjà présents sur la course : porteurs de `self._participations[course_id]` et équipiers de leurs `teammate_links` ; un équipier retrouvé dans `found` dont l'id y figure refuse la ligne ;
  2. **clés d'identité** normalisées (`_identity_key`, nom et prénom en minuscules) déjà réservées par une ligne composée plus tôt **dans le même lot ou une tranche précédente** (ensemble par course, tenu sur le `_Persister`) ; un équipier, connu ou **neuf**, dont la clé y figure refuse la ligne.
  Une ligne acceptée réserve les clés et les ids de ses équipiers ; une ligne refusée suit le chemin d'aujourd'hui (identité d'équipe recherchée ou créée). T013 à T015 au vert, dont T014(b) avec un `MARTIN Paul` absent de la base.

**Checkpoint**: US1 + US2 : découpage sûr.

---

## Phase 5: User Story 3 - Un nom de personne hors relais n'est jamais cassé (Priority: P1)

**Goal**: aucun effet hors relais.

**Independent Test**: import individuel avec `/`, `&`, `et`, `-` : fiches identiques à avant.

### Tests for User Story 3

- [X] T017 [US3] Dans `backend/tests/test_services/test_import_service.py` : épreuve **non relais** avec `CHAIGNEAU BENJAMIN` / `/ LENOIR-LEDOUX CHRISTELLE .`, `LES PATATALO` / `Gaelle et Laure`, `DUBOIS-HERRY` / `Anne-Sophie` → fiches créées à leur nom publié exact, aucune composition, `team_name is None` ; `monkeypatch` de `import_service.split_relay_teammates` qui lève une erreur, pour prouver qu'elle n'est jamais appelée hors relais.
- [X] T018 [US3] Même fichier : relais `PINSON/ROCHEFORT-CUNIN` / `Eric/Emmanuel` → équipier `("ROCHEFORT-CUNIN", "Emmanuel")`, tiret conservé.

### Implementation for User Story 3

- [X] T019 [US3] Vérifier que T017 et T018 passent sans code nouveau (garde `scraped.is_relay` de T011) ; sinon corriger `add()` dans `backend/app/services/import_service.py`, jamais la règle.

**Checkpoint**: invariant #63 couvert.

---

## Phase 6: User Story 4 - Un rescrape découpe les relais encore portés par une fiche d'équipe (Priority: P2)

**Goal**: reprise épreuve par épreuve, idempotente, sans jamais retoucher une composition posée.

**Independent Test**: fiche d'équipe `MASSONNEAU PIERRE / BESANCON FABIEN .` déjà en base, rescrape → composée, fiche d'équipe supprimée ; second rescrape → aucun changement.

### Tests for User Story 4

- [X] T020 [US4] Dans `backend/tests/test_services/test_import_service.py` : helper qui fabrique l'état « importé avant #895 » en créant directement, par `athlete_repository` et `participation_repository`, la fiche d'équipe (`nom="MASSONNEAU PIERRE"`, `prenom="/ BESANCON FABIEN ."`) et sa participation relais sur la course, avec ou sans dossard (`parametrize` `"7"` / `""`) ; rescrape de la même ligne → la participation (même `id`) est composée, porteur `MASSONNEAU PIERRE`, `team_name` posé, la fiche d'équipe n'existe plus, rapport : `updated == 1`, `imported == 0`.
- [X] T021 [US4] Même fichier : la fiche d'équipe porte **aussi** un résultat sur une autre épreuve → après rescrape, elle subsiste avec ce seul résultat.
- [X] T022 [US4] Même fichier : idempotence. Importer une ligne découpable (avec et sans dossard), rescraper deux fois → mêmes participations (ids), même composition, aucune fiche créée au second passage, rapport sans `imported`.
- [X] T023 [US4] Même fichier : composition manuelle intacte. Import de `DUPONT Jean / MARTIN Paul` (composée automatiquement), puis `admin_actions.set_teammates` vers [Paul, Jean, une troisième fiche], puis rescrape → composition exactement celle de l'administrateur.

### Implementation for User Story 4

- [X] T024 [US4] Dans `_resolve_pending()` (`backend/app/services/import_service.py`) : pour une ligne découpée **avec** participation existante sans composition (chemin dossard), ou **sans** dossard dont l'identité d'équipe est retrouvée (`found`, sans création) et appariée par `_match_without_bib` : `participation_repository.replace_teammates`, porteur réassigné à l'équipier 1 (`participation.athlete`), puis `_upsert` avec un `ScrapedResult` dont `team_name` est la valeur reconstituée (`dataclasses.replace`), et l'ancienne fiche d'équipe ajoutée aux candidats de purge. En fin de `_resolve_pending`, un seul `athlete_repository.delete_orphans_among(self.db, candidats)`. Pas d'entrée `Reassignment` (contrat gelé, research R6). T020 à T023 au vert.
- [X] T025 [US4] Adapter la section « Relais attribué à ses équipiers (#894) » de `backend/tests/test_services/test_import_service.py` (helper `_relais_attribue` et tests qui suivent) : ces lignes (`DUPONT Jean / MARTIN Paul`, `DUPONT JEAN / MARTIN` + `PAUL`) sont désormais composées dès l'import. Garder l'intention de chaque test (le rescrape ne défait pas une composition posée) : soit un nom d'équipe non découpable (`LES INCONNUS`) pour les tests qui visent une composition purement manuelle, soit une assertion explicite que l'import a déjà composé. Aucune assertion supprimée sans remplaçant.

**Checkpoint**: toutes les stories fonctionnelles.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T026 [P] Ajouter une ligne dans `backend/app/scrapers/AGENTS.md` : un relais aux équipiers nommés (`/`, nom et prénom par segment) est découpé à l'import par `split_relay_teammates`, pas par les scrapers ; renvoi vers le contrat et le sondage.
- [X] T027 [P] Dans `docs/modele-donnees.md` : une composition de relais peut être posée par l'import (#895) ou à la main (#894) ; même table, même règle de porteur.
- [X] T027b Mesurer SC-001 et SC-002 : script au scratchpad de la session (hors dépôt) qui ouvre `backend/triathlon.db` en lecture seule (`sqlite3.connect("file:triathlon.db?mode=ro", uri=True)`), applique `split_relay_teammates` à `" ".join(filter(None, [nom, prenom]))` de chaque participation relais (`courses.is_relay = 1`) et compte par fournisseur les lignes découpées et non découpées. Attendu, d'après le sondage : 180 découpées (36 timepulse, 144 klikego), 861 non découpées, aucune ligne breizhchrono ni wiclax découpée. Tout écart se tranche en relisant le sondage, pas en ajustant la règle à l'aveugle. Consigner les chiffres dans la PR.
- [X] T028 `uv run pytest -m "not integration"` et `uv run ruff check .` depuis `backend/` : tout vert hors l'échec préexistant noté en T001.
- [ ] T029 Dérouler `specs/20260925-130402-relay-name-split/quickstart.md` §2 sur la base de dev (après `uv run alembic upgrade head`) et consigner le résultat dans la PR.
- [ ] T030 Rédiger la description de PR (cible `epic/889-relais`, `Refs #889`, `Closes #895` à reporter dans la PR parapluie) en signalant l'écart assumé avec l'issue : raceresult et chronoweb sans relais aux équipiers nommés mesurés (FR-011), production non mesurée.

---

## Dependencies & Execution Order

### Phase Dependencies

- Phase 1 → Phase 2 → Phases 3 à 6 → Phase 7.
- Phase 2 bloque tout : T003 (règle) avant T011 ; T005 (`create_batch`) avant T012.

### User Story Dependencies

- **US1** : dépend de la Phase 2 seulement.
- **US2** : dépend de US1 (T016 modifie le chemin posé en T012).
- **US3** : dépend de T011 (garde `is_relay`) ; tests écrivables dès la Phase 2.
- **US4** : dépend de US1 et US2 (même fonction `_resolve_pending`) ; T025 après T024.

### Within Each User Story

- Tests écrits et vus en échec avant l'implémentation.
- `import_service.py` et `test_import_service.py` sont partagés par toutes les stories :
  leurs tâches sont séquentielles.

### Parallel Opportunities

- T002 ∥ T004 (fichiers distincts).
- T009 ∥ T010 (US1, fichiers fournisseurs distincts), T015 ∥ tâches US2 de `test_import_service.py`.
- T026 ∥ T027 ∥ T027b.

---

## Parallel Example: User Story 1

```bash
# Après T006-T008 (test_import_service.py, séquentiels) :
Task: "T009 [US1] oktime fixture → import découpé, backend/tests/test_oktime.py"
Task: "T010 [US1] chronoplace fixture → import découpé, backend/tests/test_chronoplace.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 puis Phase 2.
2. Phase 3 (US1) : les relais nommés s'importent composés.
3. **Stop** : ne pas livrer seul. US2 (garde FR-010) et US3 sont des gardes de sûreté, P1
   comme US1 ; la PR contient au minimum US1 + US2 + US3.

### Incremental Delivery

1. US1 + US2 + US3 → découpage sûr à l'import.
2. US4 → reprise au rescrape.
3. Phase 7 → docs, vérification, PR vers `epic/889-relais`.

---

## Notes

- Un commit par tâche d'implémentation au vert est possible mais **non imposé** (choix de
  l'utilisateur à `/speckit-implement`).
- Aucune migration, aucun changement de front ni d'API.
