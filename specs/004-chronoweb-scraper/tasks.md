# Tasks: Support de chronoweb.com comme fournisseur de résultats

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Branch**: `feat-scrapers-supporter-chronoweb.com-html-stati`

**Ground truth**: `docs/superpowers/specs/2026-07-29-chronoweb-sondage.md` — il
**prime** sur cette liste de tâches. Toute divergence constatée à
l'implémentation se tranche en re-sondant, pas en ajustant le test.

## Note sur les tests

Chaque tâche d'implémentation est précédée de sa tâche de test, qui doit
**échouer** avant d'être rendue verte : le principe III de la constitution (TDD
sans réseau) est déclaré NON-NÉGOCIABLE. Aucune tâche de test n'est optionnelle.

Tous les chemins sont relatifs à `backend/` sauf mention contraire.

---

## Phase 1 — Setup : fixtures HTML réduites

Les pages réelles pèsent jusqu'à 4,5 Mo : inversables dans le dépôt (research
R9). Les fixtures sont des extraits **verbatim** — on élague, on ne réécrit
jamais le markup, sous peine de perdre les pièges structurels (rangs superposés,
lignes multiples par dossard, `div.display_rank_cat.hidden`, attributs
`data-point` / `data-pointname` / `data-cat`). Cible : quelques ko chacune,
comme les fixtures existantes.

- [ ] T001 Écrire le script d'extraction **jetable** (hors dépôt : dans le scratchpad de session, pas dans `scripts/`) qui télécharge les pages du panel et n'en garde que `h2.date`, `h2.name`, le `select.select_epreuve` entier, et pour chaque `div.results_epreuve` la ligne `div.table-row.head` suivie des seules lignes `a.table-row.body` sélectionnées ci-dessous, attributs `data-*` conservés — prérequis de T002 à T008
- [ ] T002 [P] Créer `tests/fixtures/chronoweb/event_triathlon.html` depuis Oléron 2024 (`event=323`) : les 3 épreuves du `select` (dont `1147` « Triathlon M » et `1148`), et sur l'épreuve 1147 les lignes des dossards 360 (3 passages : points 1/8/14, cumuls 00:24:24 / 01:31:34 / 02:13:26) et 347 (3 passages, transitions attendues 00:11:03 et 00:03:38), plus un **non-finisher** (passages aux points intermédiaires, aucun au point final) et un **finisher à point vélo manquant**. Garder aussi une ligne de catégorie `MASC`, `FEM` ou `MIXT` en épreuve individuelle (p. ex. dossard 422). Si `event=323` ne contient aucun finisher à point manquant, extraire ce cas depuis Oléron 2025 / épreuve 1291 (450 passages Natation, 439 Vélo, 445 Course) dans une fixture dédiée `event_point_manquant.html` et ajuster les tests T023 en conséquence — on ne fabrique pas un cas absent de la source
- [ ] T003 [P] Créer `tests/fixtures/chronoweb/event_duathlon.html` depuis Toulouse 2024 (`event=296`) : une épreuve au motif `Course → Vélo → Course` (2 dossards, 3 passages chacun), l'épreuve « S Relais » (2 lignes d'équipe dont `TRIPOTES TEAM GOLFECH RELAIS1`, catégorie `MIXT`) et un classement dérivé mono-point (« Challenge 1er Tour », point `Vélo` seul)
- [ ] T004 [P] Créer `tests/fixtures/chronoweb/event_aquathlon_relais.html` depuis La Verrerie 2025 (`event=334`) : « Aquathlon Team Relais », **8 points** alternant `Natation` et `Course`, deux équipes aux 8 passages complets (dont `CREUSOTRI`, catégorie `MASC`)
- [ ] T005 [P] Créer `tests/fixtures/chronoweb/event_mono_point.html` depuis ALEFPA Trail 2025 (`event=356`) : au moins deux épreuves (« 53 km », « 13 km ») à **un seul** point `Course`, 2 lignes chacune — aucune transition n'y est déductible
- [ ] T006 [P] Créer `tests/fixtures/chronoweb/event_sans_classement.html` depuis Chalain 2015 (`event=146`) : `h2.name` et `select.select_epreuve` présents, **aucune** ligne de passage
- [ ] T007 [P] Créer `tests/fixtures/chronoweb/event_inconnu.html` depuis `resultats_evenement.php?event=99999` : réponse 200 portant « Aucun évènement trouvé avec cet ID », **sans** `h2.name`
- [ ] T008 [P] Créer `tests/fixtures/chronoweb/catalogue.html` : extrait de `/resultats.php` limité à trois lignes — celle portant `resultats_evenement.php?event=323` (`div.table-cell.location` = « St Georges d'Oléron »), celle de `event=296`, et une ligne **sans** cellule `location` (cas de la ville absente)

---

## Phase 2 — Foundational : harnais de test, squelette du module, détection

**Bloquant pour toutes les user stories** : sans le client factice ni les
structures internes, aucune story n'est testable.

- [ ] T009 Écrire `tests/test_chronoweb.py` : docstring de module en anglais (principe I) datant et situant les fixtures, helper `_fixture(name)`, `FakeResponse`, et un `FakeClient` qui **route par URL** (`resultats_evenement.php` → fixture d'événement, `resultats.php` → catalogue) et **compte ses appels** — la garantie de cardinalité (FR-020) se vérifie sur ce compteur. Y adosser un premier test rouge de `_parse_event_meta` sur `event_triathlon.html` : nom « Triathlon d'Oléron 2024 », `event_date == date(2024, 10, 6)`, `city == ""` à ce stade
- [ ] T010 Créer `app/scrapers/chronoweb.py` : docstring de module (anglais), `PROVIDER_NAME`, `BASE_URL`, `HEADERS`, les dataclasses internes `EventMeta` / `RaceMeta` / `Passage` / `Runner` de [data-model.md](./data-model.md), et `_parse_event_meta` (`h2.name`, `h2.date` en `jj/mm/aaaa`) — rendre T009 vert
- [ ] T011 Test rouge de `_parse_races` dans `tests/test_chronoweb.py` : sur `event_triathlon.html`, 3 `RaceMeta` lues sur `select.select_epreuve > option[value]` (`race_id`, `label`), `event_type` résolu par `classify.classify_event_type(label, contexte=EventMeta.name)`, `is_relay` faux ; sur `event_duathlon.html`, « S Relais » ressort `is_relay` vrai ; sur `event_sans_classement.html`, les épreuves du `select` sans `div.results_epreuve` associé n'entraînent aucune exception
- [ ] T012 Implémenter `_parse_races` dans `app/scrapers/chronoweb.py` (dont la détection de relais par libellé — `relais` / `duo` / `team`, sans accent ni casse, research R6) — rendre T011 vert
- [ ] T013 Test rouge de détection dans `tests/test_registry.py` : `https://chronoweb.com/resultats_evenement.php?event=323` et le sous-domaine `www.` détectés `chronoweb` avec `is_supported` vrai ; `https://evil-chronoweb.com/x`, un jeton `chronoweb.com` porté en query d'un autre host, `https://timepulse.fr@chronoweb.com/x` et `https://[oops/x` traités selon la garde SSRF de #49 ; les 12 providers existants restent détectés à l'identique (non-régression, SC-006)
- [ ] T014 Ajouter `ChronoWebProvider(HostMatchedProvider)` (`name = "chronoweb"`, `_HOSTS = ("chronoweb.com",)`, délégation à `chronoweb.scrape_event_all`, **aucune** surcharge de `matches`) et son entrée dans `PROVIDERS` de `app/scrapers/registry.py`, avant `T2AreaProvider` — rendre T013 vert

**Checkpoint** : le fournisseur est détecté, le module se charge, les fixtures se lisent.

---

## Phase 3 — User Story 1 : importer un événement chronoweb depuis un lien collé (P1) 🎯 MVP

**Goal** : une URL de page de résultats chronoweb produit **toutes** les épreuves
de l'événement, chacune comme une course distincte, avec tous leurs participants,
leurs temps, leurs rangs du point final et leurs segments — transitions calculées
comprises.

**Independent test** : `registry.scrape_event_all(<url Oléron 2024>)` rend 854
participations réparties sur 3 `event_name` distincts, et le dossard 360
correspond ligne à ligne au site (02:13:26, rangs 1/1, 5 segments).

- [ ] T015 [US1] Test rouge de `canonical_url` dans `tests/test_chronoweb.py` : `resultats_evenement.php?event=323&epreuve=1147` et `…?event=323&epreuve=1148&cat=all&point=10` rendent tous deux `https://chronoweb.com/resultats_evenement.php?event=323` ; host `www.chronoweb.com` accepté ; aucun paramètre d'affichage conservé
- [ ] T016 [US1] Implémenter `canonical_url` dans `app/scrapers/chronoweb.py` — reconstruction par **allowlist** du seul paramètre `event` (research R5), jamais par soustraction des paramètres connus — rendre T015 vert
- [ ] T017 [US1] Test rouge de `_parse_passages` sur `event_triathlon.html` / épreuve 1147 : une `Passage` par ligne `a.table-row.body`, `point_id` lu sur `data-point`, `point_name` sur `data-pointname`, `cumulative` (2ᵉ cellule) et `segment` (6ᵉ cellule) distincts, `rank_overall` lu sur `div.display_rank_global` et `rank_category` sur `div.display_rank_cat` **séparément** — un test explicite doit constater que `get_text()` de la cellule `classement` rendrait « 11 » pour un 1ᵉʳ/1ᵉʳ, valeur que le parseur ne doit **jamais** produire —, `speed` (`div.table-cell.vmoyenne`), `rank_gain` (`div.table-cell.gain`), `category` (`data-cat`) ; une ligne dont le nombre de cellules diffère de 9 est **ignorée** avec un `logger.warning`, les autres restant importées ; un temps illisible laisse le segment vide sans lever
- [ ] T018 [US1] Implémenter `_parse_passages` (et la garde sur le nombre de cellules) — rendre T017 vert
- [ ] T019 [US1] Test rouge de `_group_runners` : le dossard 360 rend **un** `Runner` portant 3 `Passage` triés par `point_id` croissant (1, 8, 14) ; le nombre de `Runner` d'une épreuve est celui de ses dossards distincts, pas celui de ses lignes (FR-004, SC-002) ; un dossard sans ligne au point final reste un `Runner` ; le **point final** de l'épreuve est le `point_id` maximal observé sur l'ensemble de ses lignes, calculé par épreuve et non par participant
- [ ] T020 [US1] Implémenter `_group_runners` et la détermination du point final de l'épreuve — rendre T019 vert
- [ ] T021 [US1] Test rouge du report du point final : dossard 360 → `total_time == "02:13:26"`, `rank_overall == 1`, `rank_category == 1` ; le non-finisher de la fixture → `total_time == ""`, `rank_overall is None` **et** `rank_category is None`, ses rangs intermédiaires restant présents dans `raw_data["points"]` (FR-005) ; sur l'épreuve entière, aucun `rank_overall` n'apparaît deux fois (SC-003)
- [ ] T022 [US1] Implémenter le report du point final en `total_time` / `rank_overall` / `rank_category`, avec `utils.normalize_time` — rendre T021 vert
- [ ] T023 [US1] Test rouge des motifs reconnus et des transitions calculées : dossard 360 → `swim 00:24:24`, `t1 00:07:01`, `bike 01:00:09`, `t2 00:02:26`, `run 00:39:26` (SC-005 : la somme des 5 égale `total_time`) ; dossard 347 → `t1 00:11:03`, `t2 00:03:38` ; sur `event_mono_point.html`, seul `run_time` est rempli et aucune transition n'est produite ; sur le finisher à point vélo manquant, `bike_time == ""` **et** les deux transitions vides — une transition dont un point encadrant manque ne s'invente pas (FR-008)
- [ ] T024 [US1] Implémenter `_POINT_PATTERNS` (les 5 motifs mesurés de research R2, clés = suite ordonnée des `point_name`) et le remplissage des slots positionnels, transitions incluses : `cumul[i] − intervalle[i] − cumul[i−1]`, non enregistrée si nulle ou si un point encadrant manque — rendre T023 vert
- [ ] T025 [US1] Test rouge du motif duathlon sur `event_duathlon.html` (`Course → Vélo → Course`) : les slots `swim`/`t1`/`bike`/`t2`/`run` sont remplis par le scraper, et `services.mapping.build_splits` en rend les clés `course1` / `bike` / `course2` avec les deux transitions, **sans aucune clé de natation** (FR-010) ; sur le classement dérivé mono-point `Vélo`, seul `bike_time` est rempli
- [ ] T026 [US1] Ajuster `_POINT_PATTERNS` si nécessaire pour rendre T025 vert — aucune logique de discipline dans le scraper : le **motif** décide du remplissage (il est mesuré), `build_splits` de l'étiquetage (research R2, alternative rejetée)
- [ ] T027 [US1] Test rouge du repli générique sur `event_aquathlon_relais.html` (8 points) : `segments` porte **15** entrées — les 8 étapes sous les libellés publiés (`Natation` / `Course` alternés) et les 7 transitions « Changement » intercalées —, les 5 slots positionnels restant vides ; passé à `build_splits`, aucun temps n'est écrasé par la répétition d'un libellé (les collisions sont suffixées « (N) ») — SC-007
- [ ] T028 [US1] Implémenter le chemin `segments` : libellés de la source, transitions intercalées sous « Changement », aucun plafond de 5 (FR-009) — rendre T027 vert
- [ ] T029 [US1] Test rouge de `_gender_from_category` : les 5 règles de research R7 sur un échantillon représentatif des 81 codes du panel — `MSE`/`FV1`/`MCA`/`FPU` par **préfixe**, `SEM`/`V1F`/`M0F`/`M1M`/`JUF` par **suffixe** (`M0F` doit sortir `F`, pas `M`), `MASC` → `M`, `FEM` → `F`, `MIXT`/`DUOX`/`DUOM`/`DUOF` → `""`, code inconnu ou vide → `""`
- [ ] T030 [US1] Implémenter `_gender_from_category` — rendre T029 vert
- [ ] T031 [US1] Test rouge de la sortie `ScrapedResult` (`_build_result`) : `event_name` composé par `utils.qualify_event_name` (« Triathlon d'Oléron 2024 - Triathlon M »), `event_date` identique sur les 3 épreuves (FR-014), `event_type` de la `RaceMeta`, `athlete_name` / `athlete_firstname` par `utils.split_athlete_name` sur les trois casses du sondage (`MARIN Thomas`, `PRIOUX EMMANUEL`, `fayet pascaline`), `bib_number`, `category`, `gender`, `provider == "chronoweb"`, `source_url` canonique, et — vides par construction — `club == ""`, `status == ""`, `distance_km is None`, `rank_gender is None` ; `raw_data` porte `event_id`, `race_id`, `race_label` et `points[]` (un dict par passage : `point_id`, `name`, `cumulative`, `segment`, `rank_overall`, `rank_category`, `speed`, `rank_gain`). Sur l'épreuve « S Relais » de `event_duathlon.html` : `is_relay` vrai, `athlete_name == "TRIPOTES TEAM GOLFECH RELAIS1"` **entier** et `athlete_firstname == ""` (FR-012)
- [ ] T032 [US1] Implémenter `_build_result` — rendre T031 vert
- [ ] T033 [US1] Test rouge de `scrape_event_all` avec le `FakeClient` de T009 : une entrée par participant **et par épreuve**, jamais deux entrées de même `(event_name, bib_number)`, `source_url` canonique sur toutes, **exactement 2 appels HTTP** (classement puis catalogue) et **aucun** appel à `resultats_participant.php` (FR-019, FR-020) ; `raw_data["city"] == "St Georges d'Oléron"` ; catalogue en échec (HTTP 500, puis ligne `event=` absente) → import complet **sans** `city`, un `logger.warning`, et toujours 2 appels au plus (FR-015) ; deux invocations successives refont la requête catalogue — aucune mémoïsation, le fournisseur reste sans état (research R4)
- [ ] T034 [US1] Implémenter `scrape_event_all` et `_fetch_city` (lecture de la ligne `resultats_evenement.php?event=<id>` du catalogue puis de sa cellule `div.table-cell.location`, tout échec journalisé et ignoré) — rendre T033 vert

**Checkpoint** : un événement chronoweb s'importe entièrement depuis l'URL d'une
de ses épreuves. MVP livrable — il couvre 3 des 5 URLs distinctes du Sheet.

---

## Phase 4 — User Story 2 : importer les liens du Sheet quelle que soit leur forme (P2)

**Goal** : les fiches individuelles et les URLs porteuses de paramètres
d'affichage produisent le même import complet ; deux graphies du même événement
ne dupliquent rien.

**Independent test** : les 4 formes d'URL réellement présentes dans le Sheet pour
Oléron 2024 et Altriman 2025 rendent des résultats identiques et un `source_url`
identique.

- [ ] T035 [US2] Test rouge de `canonical_url` sur les formes du Sheet : `resultats_participant.php?event=347&epreuve=1234&bib=599` et `resultats_participant.php?event=347&epreuve=1235&bib=1563` rendent la **même** URL canonique `resultats_evenement.php?event=347` (FR-016) ; les 4 graphies d'Oléron 2024 du Sheet se réduisent à une seule URL canonique
- [ ] T036 [US2] Test rouge de bout en bout : `scrape_event_all(<url de fiche individuelle>)` interroge la page d'**événement** et jamais `resultats_participant.php` (assertion sur les URLs vues par le `FakeClient`), et rend l'événement entier ; deux invocations sur deux graphies du même événement rendent des listes identiques champ à champ (FR-002, US2 §3)
- [ ] T037 [US2] Étendre `canonical_url` à `resultats_participant.php` (troncature vers son événement) — le corps de `scrape_event_all` ne change pas, il consomme déjà l'URL canonique — rendre T035 et T036 verts

**Checkpoint** : les 4 URLs exploitables du Sheet aboutissent.

---

## Phase 5 — User Story 3 : comprendre pourquoi un lien chronoweb n'est pas importable (P3)

**Goal** : une URL chronoweb qui ne désigne pas des résultats consultables échoue
avec une cause nommée et actionnable, sans import partiel — et un événement
réellement vide n'est **pas** une erreur.

**Independent test** : l'URL d'archive du Sheet et un identifiant d'événement
inconnu produisent deux messages distincts, visibles dans « Épreuves en erreur
(détail) » des bilans CLI.

- [ ] T038 [US3] Test rouge du refus d'URL : `files/pdf/Resultats_Triathlon_dOlron_2025.zip` et `resultats_evenement.php` sans paramètre → `ValueError` dont le message **en français** nomme la forme attendue `resultats_evenement.php?event=<id>` ; **aucun appel HTTP émis** (compteur du `FakeClient` à 0) — le scraper ne doit jamais tenter de parser un binaire (FR-017)
- [ ] T039 [US3] Test rouge de la distinction introuvable / vide : `event_inconnu.html` (aucun `h2.name`) → `ValueError` « événement introuvable » ; `event_sans_classement.html` (`h2.name` présent, zéro ligne) → liste vide **sans** exception (FR-018)
- [ ] T040 [US3] Implémenter les deux gardes dans `app/scrapers/chronoweb.py` : absence de paramètre `event` rejetée **avant** tout appel réseau, absence de `h2.name` rejetée après le premier appel — rendre T038 et T039 verts

**Checkpoint** : les 5 URLs du Sheet sont traitées — 4 importées, 1 en erreur actionnable (SC-001).

---

## Phase 6 — Polish & vérifications transverses

- [ ] T041 [P] Ajouter l'entrée `chronoweb` à `LIVE_URLS` de `tests/test_integration_scrapers.py` (URL stable d'Oléron 2024, effectifs publiés : 3 épreuves / 854 participants) et vérifier `uv run pytest -m integration -k chronoweb`
- [ ] T042 [P] Ajouter `chronoweb: "ChronoWeb"` à `PROVIDER_LABELS` dans `frontend/lib/constants.ts` et vérifier `npm test` — le front ne liste jamais les providers, cette entrée n'est qu'un libellé commercial (son absence ne vaut pas « non supporté »)
- [ ] T043 [P] Documenter le fournisseur dans `AGENTS.md`, section « Fournisseurs supportés » : une ligne = un **passage** et non un participant, événement entier en une requête sans JS, temps total et rangs du **seul point final** (aucun rang intermédiaire promu), transitions **calculées** et non publiées, motif de points reconnu → slots / sinon libellés de la source, plafond de **2 requêtes** par import, absence de club (donc hors `scope=club`), de date de naissance et de distinction DNS/DSQ, canonicalisation par allowlist du seul `event`, refus de l'archive ZIP, distinction événement introuvable / sans classement, limites du classifieur partagé laissées hors périmètre, et renvoi au sondage
- [ ] T044 Lancer `uv run ruff check .` depuis `backend/` et corriger les écarts du nouveau module et des fichiers touchés
- [ ] T045 Lancer `uv run pytest -m "not integration"` depuis `backend/` : suite complète verte, aucune régression sur les 12 autres fournisseurs (SC-006)
- [ ] T046 Exécuter le [quickstart](./quickstart.md) §2 à §6 : détection, scrape à sec (854 participations, 3 `event_name`, dossard 360 vérifié champ à champ, `city`), import réel puis réimport **idempotent** (854 ajoutés puis 0 ajouté / 854 déjà en base), et les 5 formes d'URL du tableau §6 à la main
- [ ] T047 Vérifier le bout en bout **côté API** : `GET /scrape/detect` → `{provider: "chronoweb", supported: true}`, `POST /scrape/event/stream` → phases SSE jusqu'à `done` sur Oléron 2024, `POST /scrape/event` sur l'URL d'archive ZIP → **422** portant le message français verbatim de T038

---

## Dependencies

```text
Phase 1 (fixtures, T001-T008)  ──┐
                                 ├──> Phase 2 (T009-T014, bloquant)
                                 │        │
                                 │        ├──> Phase 3 US1 (T015-T034)  ← MVP
                                 │        │        │
                                 │        │        ├──> Phase 4 US2 (T035-T037)
                                 │        │        └──> Phase 5 US3 (T038-T040)
                                 │        │
                                 └────────┴──> Phase 6 (T041-T047)
```

- **T001 précède T002-T008** : le script d'extraction produit les fixtures.
- **Phase 2 est bloquante** : sans le `FakeClient` compteur ni `_parse_event_meta`
  / `_parse_races`, aucune story n'est testable.
- **US2 et US3 sont indépendantes entre elles** et ne dépendent que d'US1 :
  `canonical_url` et les gardes se branchent sur un `scrape_event_all` existant.
- **Ordre interne d'US1** : T015-T016 (URL) → T017-T018 (lignes) → T019-T022
  (regroupement et point final) → T023-T028 (segments) → T029-T032 (identité) →
  T033-T034 (orchestration). Chaque paire est test rouge puis vert.
- Phase 6 attend US1 au minimum ; T041, T046 et T047 supposent US2 et US3 faites
  pour couvrir les URLs réelles du Sheet et les refus.

## Parallel opportunities

- **T002 à T008** : 7 fixtures, fichiers distincts, aucune dépendance entre elles
  → toutes parallélisables une fois T001 écrit.
- **T041, T042, T043** : trois fichiers distincts
  (`tests/test_integration_scrapers.py`, `frontend/lib/constants.ts`,
  `AGENTS.md`) → parallélisables.
- **Aucun `[P]` dans les phases 2 à 5** : toutes les tâches touchent le **même**
  module (`app/scrapers/chronoweb.py`) et son fichier de tests, et la séquence
  test rouge → vert impose l'ordre. T013/T014 font exception par leurs fichiers
  (`tests/test_registry.py`, `registry.py`) mais restent une paire ordonnée.

## Implementation strategy

1. **MVP = Phase 1 + Phase 2 + Phase 3 (US1)** : un événement chronoweb s'importe
   entièrement depuis l'URL d'une de ses épreuves. Livrable tel quel — cela
   couvre 3 des 5 URLs distinctes du Sheet (les `resultats_evenement.php`) et les
   2 événements réellement pointés, soit 7 épreuves et 2 428 participants.
2. **Incrément 2 = US2** : les 2 fiches individuelles du Sheet (40 % des liens)
   aboutissent, et les graphies multiples cessent de compter double.
3. **Incrément 3 = US3** : l'URL d'archive ZIP devient une erreur actionnable au
   lieu d'un échec muet, et un événement sans classement publié cesse de
   ressembler à une panne.
4. **Phase 6** : intégration réseau, libellé front, documentation, lint,
   vérifications réelles de bout en bout.

Total : **47 tâches** — 1 outillage + 7 fixtures, 19 tests, 13 implémentations,
7 vérifications transverses.

## Traçabilité : exigences couvertes indirectement

Trois exigences n'ont **pas** de test unitaire dédié dans ce lot, et c'est
délibéré : leur logique appartient à du code existant, déjà couvert par ses
propres tests. Les dupliquer irait contre le principe VI.

| Exigence | Où elle vit | Vérification retenue |
| --- | --- | --- |
| Statut DNF des non-finishers (US1 §6, Edge Cases) | `services/mapping.derive_status` (finisher si temps total, sinon DNF) | T021 (`total_time == ""`, rangs `None`) + import réel du quickstart (T046) |
| Non-duplication au réimport (US1 §5, US2 §3) | `import_service._Persister` et les contraintes `UNIQUE(course_id, bib_number)` / `UNIQUE(name, event_date, event_type)` | réimport idempotent du quickstart (T046) : 0 ajouté, 854 déjà en base |
| Mojibake résiduel de la source (4 lignes / 31 642) | rien à coder — la page est servie et décodée en UTF-8, la graphie fausse vient de la saisie côté chronoweb | aucune tâche ; la réconciliation d'identité corrigera si un autre fournisseur publie la graphie juste |

Deux limites sont **hors périmètre** et documentées comme telles (spec
§Assumptions), sans tâche : les trois écarts du classifieur partagé mesurés sur le
panel (« 53 km » d'un trail classé `course-a-pied`, épreuve sans sport nommé
repliée sur `triathlon`, `Altriman` sans taille) et l'instabilité de
`Course.source_url` entre deux graphies d'une même URL.
