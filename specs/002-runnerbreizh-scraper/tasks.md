# Tasks: Support de runnerbreizh.fr comme fournisseur de résultats

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Branch**: `tjarrier/feat-scrapers-supporter-runnerbreizh.fr-html-sta`

**Ground truth**: `docs/superpowers/specs/2026-07-27-runnerbreizh-sondage.md`

## Note sur les tests

Chaque tâche d'implémentation est précédée de sa tâche de test, qui doit
**échouer** avant d'être rendue verte : le principe III de la constitution (TDD
sans réseau) est déclaré NON-NÉGOCIABLE. La mention « Tests are OPTIONAL » que le
template portait a été retirée en amont (`483c2e4`, PR #120).

Tous les chemins sont relatifs à `backend/` sauf mention contraire.

---

## Phase 1 — Setup : fixtures HTML réduites

Extraits réels capturés le 27/07/2026, élagués de leurs attributs de style
volumineux, **structure intacte** : `table#titre-courses` pour le bandeau, puis
`table.tableau-courses` avec son unique `<tr>` d'en-tête (`td.courses-annees`)
suivi des lignes de données, 8 cellules chacune. 1 à 4 lignes suffisent par
fixture ; cible 2 à 6 ko, comme les fixtures existantes.

- [x] T001 [P] Créer `tests/fixtures/runnerbreizh_page1_triathlon.html` depuis la page 1 de `2025-09-0749quiberon` : bandeau, en-tête, 3 lignes dont une avec lien coureur (`<a class="M" … di=…>`) et une en `<span>`. Cette épreuve **ne porte pas** de mention « Chronométrée par » — la republication a sa fixture propre (T008b), on ne fabrique pas une mention absente de la source
- [x] T002 [P] Créer `tests/fixtures/runnerbreizh_page2_derniere.html` : dernière page partielle (2 lignes), même épreuve — sert au test de pagination
- [x] T003 [P] Créer `tests/fixtures/runnerbreizh_page_vide.html` : page au delà de la dernière (bandeau + en-tête seuls, 0 ligne), titre valide
- [x] T004 [P] Créer `tests/fixtures/runnerbreizh_page_introuvable.html` : `<title>` vide et 0 ligne (identifiant inconnu)
- [x] T005 [P] Créer `tests/fixtures/runnerbreizh_duathlon.html` depuis `2025-10-0527coueron` : 2 lignes, en-têtes trompeurs (« 1ère épreuve » = CàP1, « Vélo » = vélo, « CàP » = CàP2)
- [x] T006 [P] Créer `tests/fixtures/runnerbreizh_aquathlon.html` depuis `2026-07-047pleneuf-val-andre` : 2 lignes, **cellule vélo vide**
- [x] T007 [P] Créer `tests/fixtures/runnerbreizh_duo.html` depuis `2026-06-21111duosizun` : 4 lignes = 2 équipes, rangs et temps partagés, catégories `M+M`/`M+F`
- [x] T008 [P] Créer `tests/fixtures/runnerbreizh_lignes_anomales.html` : 2 lignes anonymes `?DOSSARD #9998` (catégorie `0 /M`) + 1 ligne `PROD?HOMME Anais` + 1 ligne à 7 cellules (hors format)
- [x] T008b [P] Créer `tests/fixtures/runnerbreizh_republication.html` depuis `2026-07-1925plouescat` : bandeau portant « Chronométrée par » + logo `BREIZHCHRONO`, en-tête, 1 ligne — seule fixture du lot où la mention existe réellement

---

## Phase 2 — Foundational : squelette, métadonnées, détection

**Bloquant pour toutes les user stories.**

- [x] T009 Écrire `tests/test_runnerbreizh.py` (en-tête de module + chargement des fixtures + `FakeResponse`/client factice comptant les appels, sur le modèle de `tests/test_t2area.py`), avec un premier test rouge de `_parse_title` : nom **sans** le suffixe `(1.5/38/10)`, date `2025-09-07`, ville, `distance_km=49.5`, discipline **résolue** par `classify.classify_event_type` (`triathlon-m`) — le `Type :` du titre n'étant qu'un repli. Y adosser l'assertion de SC-008 : `geocode_service.extract_city(event_name)` rend `"Quiberon"` sur le nom nettoyé, là où le nom intégral rendrait `"Quiberon M (1.5/38/10)"`
- [x] T010 Créer `app/scrapers/runnerbreizh.py` : docstring de module (anglais, cf. principe I), `PROVIDER_NAME`, `BASE_URL`, `HEADERS`, dataclass `EventMeta`, et `_parse_title` — rendre T009 vert
- [x] T011 Test rouge de `_result_rows` : sur la fixture page 1, rend exactement 3 lignes (bandeau et en-tête exclus) ; sur la fixture page vide, rend `[]`
- [x] T012 Implémenter `_result_rows` dans `app/scrapers/runnerbreizh.py` (sélection `table.tableau-courses`, exclusion des deux premières lignes, tolérance à l'absence de la table) — rendre T011 vert
- [x] T013 Test rouge de détection dans `tests/test_registry.py` : `www.runnerbreizh.fr` et l'apex détectés `runnerbreizh` ; `evil-runnerbreizh.fr`, un jeton `runnerbreizh.fr` en query, `https://timepulse.fr@runnerbreizh.fr/…` et `https://[oops/x` traités selon la garde SSRF de #49
- [x] T014 Ajouter `RunnerBreizhProvider(HostMatchedProvider)` (`name`, `_HOSTS`, délégation à `runnerbreizh.scrape_event_all`) et l'entrée dans `PROVIDERS` de `app/scrapers/registry.py`, avant `T2AreaProvider` — rendre T013 vert

---

## Phase 3 — User Story 1 : importer une épreuve complète (P1) 🎯 MVP

**Goal** : une URL de page de résultats runnerbreizh produit tous les
participants de l'épreuve, avec temps, rangs, catégorie, genre et segments
correctement étiquetés selon la discipline.

**Independent test** : `registry.scrape_event_all(<url page 1>)` rend autant de
`ScrapedResult` que de classés annoncés, et un participant vérifié à la main
correspond ligne à ligne.

- [x] T015 [US1] Test rouge de `_parse_segment_cell` : `<b>00:14:21</b><br/>P:11<br/>3.09%<br/>3.14 km/h` → temps, rang 11, écart, vitesse ; cellule vide → temps vide sans lever
- [x] T016 [US1] Implémenter `_parse_segment_cell` dans `app/scrapers/runnerbreizh.py` — rendre T015 vert
- [x] T017 [US1] Test rouge de `_parse_row` sur la fixture page 1 : nom/prénom via `split_athlete_name`, `total_time`, `rank_overall`, `rank_category`, `category`, `gender` déduit du suffixe, `swim_time`/`bike_time`/`run_time` remplis depuis les colonnes 2/3/5, `bib_number` et `club` vides, `provider`
- [x] T018 [US1] Implémenter `_parse_row` — rendre T017 vert
- [x] T019 [US1] Test rouge de `raw_data` : rangs par segment, écarts, vitesses, place avant CàP et son évolution, évolution du rang final, total de classés, identifiant coureur (`di`), page d'origine
- [x] T020 [US1] Compléter `_parse_row` pour peupler `raw_data` — rendre T019 vert
- [x] T021 [US1] Test rouge des lignes anomales (fixture T008) : ligne anonyme → `athlete_name == "?DOSSARD #9998"` et `athlete_firstname == ""` ; `PROD?HOMME Anais` conservé tel quel ; ligne à 7 cellules **ignorée** et journalisée, les autres importées
- [x] T022 [US1] Implémenter la détection du libellé anonyme et la garde sur le nombre de cellules (`logger.warning`) — rendre T021 vert
- [x] T023 [US1] Test rouge des disciplines : sur la fixture aquathlon, `bike_time == ""` ; en passant les résultats duathlon à `services.mapping.build_splits`, obtenir les clés `course1`/`bike`/`course2` et, pour l'aquathlon, `swim`/`run` sans clé vélo
- [x] T024 [US1] Ajuster `_parse_row` si nécessaire pour rendre T023 vert (aucune logique de libellé dans le scraper : la discipline vient de `event_type`)
- [x] T025 [US1] Test rouge du relais (fixture duo) : 4 résultats, deux paires partageant `total_time` et `rank_overall`, `is_relay` vrai — par le nom d'épreuve **et** par la catégorie `M+M`
- [x] T026 [US1] Implémenter la détection de relais (nom d'épreuve + catégorie de forme `X+Y`) — rendre T025 vert
- [x] T027 [US1] Test rouge de `scrape_event_all` multi-pages : client factice servant page 1 → page 2 partielle → page vide ; 5 résultats, **3 appels HTTP exactement**, aucun appel au delà de la première page vide ; vérifier aussi qu'un plafond de pages journalise et s'arrête
- [x] T028 [US1] Implémenter `scrape_event_all` (`_fetch`, boucle de pagination, plafond de sécurité, métadonnées lues une fois) — rendre T027 vert
- [x] T029 [US1] Test rouge de l'avertissement de republication : sur la fixture `runnerbreizh_republication.html` (mention « Chronométrée par BREIZHCHRONO »), un `logger.warning` est émis **une fois** ; sur la fixture page 1 de Quiberon, sans mention, aucun avertissement
- [x] T030 [US1] Implémenter la lecture de la mention de chronométreur et l'avertissement (aucune URL reconstruite) — rendre T029 vert

**Checkpoint** : à ce stade une épreuve s'importe entièrement depuis l'URL de sa
première page. MVP livrable.

---

## Phase 4 — User Story 2 : les liens réels du Sheet (P2)

**Goal** : un lien pointant une page intermédiaire, un tri ou un filtre de sexe
produit le même import complet, et la même épreuve sous deux formes ne crée
qu'une clé de cache.

**Independent test** : les 4 formes d'URL réellement présentes dans le Sheet pour
une même épreuve rendent des résultats identiques et un `source_url` identique.

- [x] T031 [US2] Test rouge de `canonical_url` : `&page=3`, `&tricourse=4`, `&Sexe=F`, combinaisons, et forme nue → toutes réduites à `…requetetriathlons.php?CourseFichierGpsNom=<clé>` ; clé contenant une apostrophe (`2026-07-05112lessables-d'olonne`) correctement encodée ; host `www` et apex acceptés
- [x] T032 [US2] Test rouge de bout en bout : `scrape_event_all(<url avec &page=3&Sexe=F>)` déclenche un premier appel sur la **page 1** et rend `source_url` canonique sur tous les résultats
- [x] T033 [US2] Implémenter `canonical_url` (reconstruction par allowlist du seul `CourseFichierGpsNom`) et son usage dans `scrape_event_all` — rendre T031 et T032 verts

---

## Phase 5 — User Story 3 : refus lisibles (P3)

**Goal** : une URL runnerbreizh qui ne désigne pas une épreuve échoue avec une
cause nommée, sans import partiel.

**Independent test** : une fiche coureur et un identifiant inconnu produisent deux
messages distincts, visibles dans « Épreuves en erreur (détail) » de la CLI.

- [x] T034 [US3] Test rouge du refus de la fiche coureur : `triathlons.php?CoureurNom=KUENTZ&CoureurPrenom=Olivier` → `ValueError` dont le message (français) nomme la forme `requetetriathlons.php?CourseFichierGpsNom=…` ; aucun appel HTTP émis
- [x] T035 [US3] Test rouge de l'épreuve introuvable : fixture à titre vide et 0 ligne → `ValueError` « épreuve introuvable » ; fixture page vide **à titre valide** → liste vide **sans** exception
- [x] T036 [US3] Implémenter les deux gardes (absence de `CourseFichierGpsNom` avant tout appel réseau ; titre vide + zéro ligne après le premier appel) — rendre T034 et T035 verts

---

## Phase 6 — Polish & vérifications transverses

- [x] T037 [P] Ajouter l'entrée `runnerbreizh` dans `LIVE_URLS` de `tests/test_integration_scrapers.py` (URL stable : `…CourseFichierGpsNom=2025-09-0749quiberon`) et vérifier `uv run pytest -m integration -k runnerbreizh`
- [x] T038 [P] Documenter le provider dans `AGENTS.md` (section « Fournisseurs supportés ») : pagination, absence de dossard **et** de club — donc participations hors périmètre `scope=club` —, refus de la fiche coureur, canonicalisation de l'URL, lignes anonymes importées, et renvoi vers le sondage
- [x] T039 Lancer `uv run ruff check .` et corriger les écarts du nouveau module et des fichiers touchés
- [x] T040 Lancer `uv run pytest -m "not integration"` : suite complète verte, aucune régression sur les 9 autres providers
- [x] T041 Exécuter le [quickstart](./quickstart.md) §3 à §6 : scrape à sec (322 participants pour Quiberon), import réel, réimport idempotent (0 ajouté), refus attendus en code 1, `club-labels` inchangé
- [x] T042 Vérifier le bout en bout **côté API** : `GET /scrape/detect` → `runnerbreizh`, `POST /scrape/event/stream` → 10 événements SSE (`scraping` → `saving` → `done`, 135 participants pour Nozay, départ forcé à `page=1`), `POST /scrape/event` sur une fiche coureur → **422** avec le message français verbatim. **Non vérifié** : le rendu visuel du front (`/ajouter`, `/carte`) — aucun navigateur disponible dans cet environnement, à contrôler à la main

---

## Dependencies

```text
Phase 1 (fixtures, T001-T008)  ──┐
                                 ├──> Phase 2 (T009-T014, bloquant)
                                 │        │
                                 │        ├──> Phase 3 US1 (T015-T030)  ← MVP
                                 │        │        │
                                 │        │        ├──> Phase 4 US2 (T031-T033)
                                 │        │        └──> Phase 5 US3 (T034-T036)
                                 │        │
                                 └────────┴──> Phase 6 (T037-T042)
```

- **Phase 2 est bloquante** : sans `_parse_title` ni `_result_rows`, aucune story
  n'est testable.
- **US2 et US3 sont indépendantes entre elles** et ne dépendent que de US1
  (`scrape_event_all` doit exister pour que la canonicalisation et les refus s'y
  branchent).
- Phase 6 attend US1 au minimum ; T037 et T041 supposent US2 et US3 faites pour
  couvrir les URLs réelles du Sheet et les refus.

## Parallel opportunities

- **T001 à T008** : 8 fixtures, fichiers distincts, aucune dépendance → toutes
  parallélisables.
- **T037 et T038** : fichiers distincts (`tests/test_integration_scrapers.py`,
  `AGENTS.md`) → parallélisables.
- À l'intérieur des phases 2 à 5, les tâches touchent le **même** module
  (`app/scrapers/runnerbreizh.py`) et son fichier de tests : pas de `[P]`, la
  séquence test rouge → vert impose l'ordre.

## Implementation strategy

1. **MVP = Phase 1 + Phase 2 + Phase 3 (US1)** : une épreuve s'importe
   entièrement depuis l'URL de sa première page. C'est déjà livrable — cela
   couvre 2 des 10 liens du Sheet (ceux sans `&page=`).
2. **Incrément 2 = US2** : les 8 liens restants portant `&page=N` fonctionnent.
   C'est le gros du volume réel.
3. **Incrément 3 = US3** : le 10e lien (fiche coureur) devient une erreur
   actionnable au lieu d'un échec muet.
4. **Phase 6** : documentation, lint, vérifications réelles.

Total : **42 tâches** — 8 fixtures, 14 tests, 14 implémentations, 6 vérifications.

## Traçabilité : exigences couvertes indirectement

Deux exigences n'ont **pas** de test unitaire dédié, et c'est délibéré : leur
logique appartient à du code existant, déjà couvert par ses propres tests. Les
dupliquer ici irait contre le principe VI.

| Exigence | Où elle vit | Vérification retenue |
| --- | --- | --- |
| FR-013 (idempotence sans dossard) | `import_service._Persister.add`, commit `b49e295` (119 lignes de tests ajoutées) | réimport réel du quickstart §4 (T041) |
| FR-015 (ne pas écraser `Athlete.club`) | `athlete_repository.resolve` (`if club and existing.club != club`) | `club-labels` inchangé après import (T041) |
