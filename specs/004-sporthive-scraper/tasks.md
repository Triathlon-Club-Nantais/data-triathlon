# Tasks: Support de MYLAPS Sporthive comme fournisseur de résultats

**Input**: Design documents from `/specs/004-sporthive-scraper/`

**Prerequisites**: `plan.md`, `spec.md` (user stories), `research.md` (D1–D15),
`data-model.md`, `contracts/provider-contract.md`, `quickstart.md`

**Tests**: obligatoires. Le principe III de la constitution v1.0.0 est
**non-négociable** — TDD sans réseau. Chaque tâche d'implémentation est précédée
d'un test rouge, et aucun test unitaire n'atteint le réseau (monkeypatch de
`httpx.Client`, fixtures JSON). Aucune dérogation n'est demandée : `plan.md`
§Complexity Tracking est vide.

**Source de vérité technique** :
`docs/superpowers/specs/2026-07-29-sporthive-sondage.md` — il prime sur ces
tâches en cas de divergence factuelle.

## Format: `[ID] [P?] [Story] Description`

- **[P]** : parallélisable — **fichier différent** et aucune dépendance sur une
  tâche incomplète.
- **[Story]** : US1 / US2 / US3, la user story servie.
- Chemins relatifs à la racine du dépôt.

## Avertissement sur le parallélisme — divergence assumée avec `plan.md`

`plan.md` §Découpage annonce les étapes 4, 5 et 6 « indépendantes et
parallélisables `[P]` ». C'est vrai **logiquement** (fonctions disjointes), mais
faux **matériellement** : elles éditent toutes `backend/app/scrapers/sporthive.py`,
et leurs tests éditent tous `backend/tests/test_sporthive.py`. Deux agents lancés
en parallèle sur ces tâches se marcheraient dessus.

Les `[P]` ci-dessous sont donc posés au sens strict du format : seules les
**fixtures** (un fichier chacune), `registry.py`, `test_registry.py` et la
documentation en portent. Le corps du scraper se fait en séquence. Échappatoire si
le parallélisme devient nécessaire : découper `test_sporthive.py` par thème
(`test_sporthive_mapping.py`, `_segments`, `_meta`) — hors périmètre ici, le
projet tenant un fichier de test par provider.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: poser le module, le harnais de test sans réseau et les fixtures. Le
projet existe déjà : ni init, ni dépendance nouvelle (`httpx` suffit), ni
migration.

- [X] T001 Créer le squelette `backend/app/scrapers/sporthive.py` : docstring technique en anglais, constantes `_API_BASE = "https://eventresults-api.speedhive.com/sporthive"`, `_PAGE_SIZE = 10`, `_MAX_PAGES = 1000`, et la signature `def scrape_event_all(url: str) -> list[ScrapedResult]` levant `NotImplementedError`
- [X] T002 [P] Créer le harnais `backend/tests/test_sporthive.py` : helper de monkeypatch de `httpx.Client` rendant des charges JSON par URL appelée, et compteur d'appels par route (il servira à prouver l'**absence** de requête en T013), sur le modèle de `backend/tests/test_klikego.py`
- [X] T003 [P] Créer les fixtures d'événement dans `backend/tests/fixtures/` : `sporthive_event.json` (`eventName`, `date` ISO, `eventType`, `location`, `countryCode`), `sporthive_races.json` (les 6 courses du Sheet avec `id`, `activeRaceId`, `raceName`, `classificationsCount`, `distanceInMeter`), `sporthive_races_empty.json` (une course à `classificationsCount: 0`)
- [X] T004 [P] Créer les fixtures de classement dans `backend/tests/fixtures/` : `sporthive_participants_p0.json` (10 lignes, `last: false`), `sporthive_participants_p1.json` (dernière page partielle, `last: true`), `sporthive_kids.json` (4 legs, une seule transition), `sporthive_monosport.json` (1 leg, `sportName: null`)
- [X] T005 [P] Créer les fixtures de cas limites dans `backend/tests/fixtures/` : `sporthive_statuses.json` (`validity` `DNF`/`DNS`/`DQ`, `dns`/`dsq` à `false`, leg fantôme `00:00:00` au split `Start`), `sporthive_relay.json` (lignes d'équipe, `teamName` libre), `sporthive_no_time_ranked.json` (ni `chipTimeOfParticipant`, ni `gunTimeOfParticipant`, ni `validity`, mais `overallPosition` non nul)

**Checkpoint**: le module existe, les tests peuvent tourner sans réseau, les
charges réelles sont capturées.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: lecture d'URL, détection au registre et client paginé. Les trois
user stories en dépendent — US1 pour importer, US3 pour refuser proprement.

**⚠️ CRITIQUE**: aucune user story ne démarre avant la fin de cette phase.

- [X] T006 Test rouge de `_parse_url` dans `backend/tests/test_sporthive.py` : les 8 cas du tableau « Lecture d'URL » de `contracts/provider-contract.md` (dont `/events/s/{id}`, `/en/events/{id}`, `/bib/{b}/split`, et `ValueError` sur `/events/abc` et `/profile`) — les trois profondeurs événement / course / dossard désignent le même événement (FR-002)
- [X] T007 Implémenter `_parse_url` et son motif unique dans `backend/app/scrapers/sporthive.py` — `/(?:<lang>/)?events/(?:s/)?(?P<event_id>\d+)(?:/.*)?` (D3). Le segment `races/{n}` est lu puis **jeté** : aucun chemin de code ne doit pouvoir le transmettre à l'API (D1, FR-004)
- [X] T008 [P] Test rouge de détection dans `backend/tests/test_registry.py` : ajouter `"sporthive.com"` à `_JETONS_PROVIDERS` (les 6 gabarits de contournement de #49 s'appliquent alors automatiquement) et ajouter les cas nominaux du contrat, dont `results.sporthive.com` accepté par sous-domaine, `evil-sporthive.com` refusé, `https://[oops/x` non-match **sans exception**, et `eventresults-api.speedhive.com` **non** détecté
- [X] T009 [P] Implémenter `SporthiveProvider(HostMatchedProvider)` avec `name = "sporthive"` et `_HOSTS = ("sporthive.com",)` dans `backend/app/scrapers/registry.py`, inséré dans `PROVIDERS` avant `T2AreaProvider` — **aucun `matches` à écrire**, la règle « host exact ou vrai sous-domaine » reste dans `registry._host_match` (D2, FR-001, FR-023 : `is_supported` et `/scrape/detect` en dérivent, aucune liste tenue séparément)
- [X] T010 Test rouge du client paginé dans `backend/tests/test_sporthive.py` : arrêt sur `last: true`, arrêt sur `content` vide, `size=10` sur chaque appel, et `ValueError` quand `_MAX_PAGES` est atteint (portée **événement**, D4, FR-009)
- [X] T011 Implémenter `_fetch_json`, `_fetch_event`, `_fetch_races` et `_iter_participants` dans `backend/app/scrapers/sporthive.py` : parcours intégral du classement en respectant la tranche maximale imposée par la source (FR-007), pagination `page`/`size=10`, jamais `count`/`offset` (silencieusement ignorés par le serveur), plafond dur (FR-009), et propagation des erreurs HTTP 5xx telles quelles

**Checkpoint**: une URL Sporthive est reconnue, lue, et son classement peut être
parcouru — sans qu'aucune règle métier ne soit encore appliquée.

---

## Phase 3: User Story 1 - Importer une épreuve Sporthive depuis un lien collé (Priority: P1) 🎯 MVP

**Goal**: coller l'URL du Sheet crée les 6 épreuves de l'événement avec leurs
955 participants, temps, rangs et segments.

**Independent Test**: `rescrape-db --url <URL du Sheet>` rend « 6 épreuves
ciblées, 955 participants ajoutés, aucune erreur », et un participant vérifié à la
main a les bons temps, rangs et segments.

### Tests for User Story 1

> **Écrire ces tests d'abord et vérifier qu'ils échouent** (principe III, non négociable).

- [ ] T012 [US1] Test rouge de la garde de complétude dans `backend/tests/test_sporthive.py` : une course tronquée sur 6 → **5** `ScrapedResult` rendus, **aucune** exception propagée, un `logger.warning` portant intitulé, `activeRaceId` et les deux décomptes ; un `classificationsCount` dépassé → import accepté, surplus journalisé (D4, FR-008, FR-008a)
- [ ] T013 [US1] Test rouge des courses vides dans `backend/tests/test_sporthive.py` : sur `sporthive_races_empty.json`, la course est absente du résultat **et aucune requête `participants` n'est émise pour elle** — assertion sur le compteur d'appels du harnais T002 (D14, FR-008b)
- [ ] T014 [US1] Test rouge du mapping des scalaires dans `backend/tests/test_sporthive.py` : `"00:57:33.2510000"` → `"00:57:33"`, `"00:00:00"` → `""`, priorité chip puis gun, `overallPosition: 0` → `None`, `gender: "U"` → `""`, `validity` `DNF`/`DNS`/`DQ` → statuts, booléens `dns`/`dsq` jamais lus, et le cas `sporthive_no_time_ranked.json` → `finisher` **explicite** (D5, D6, D12 ; FR-010, FR-011 chip prioritaire, FR-012 fractions écartées, FR-013 durée nulle = absence, FR-014 statut du seul champ renseigné, FR-014a repli sur le rang, FR-015 rang nul = absence)
- [ ] T015 [US1] Test rouge des segments dans `backend/tests/test_sporthive.py` : 5 legs → 5 segments dont deux `transition`, 4 legs → `course à pied` en dernier (**jamais** en `t2`), 1 leg avec `sportName: null` → `course à pied` depuis `type`, leg fantôme → **aucun** segment (D7, D8, FR-016, FR-017)
- [ ] T016 [US1] Test rouge des métadonnées d'épreuve dans `backend/tests/test_sporthive.py` : les 5 lignes du tableau « Classification » du contrat (dont `Senior Men` → `course-a-pied`, **jamais** `triathlon`), nom qualifié par `qualify_event_name`, date depuis l'ISO sans parsing FR, `distanceInMeter / 1000`, `is_relay` sur l'intitulé, et `raw_data["city"]` / `raw_data["country"]` verbatim (D9, D10, D15 ; FR-006 une épreuve distincte par course, FR-018 relais, FR-020 date réelle, FR-021 discipline et taille depuis l'intitulé, FR-022 kilométrage, FR-022a lieu et pays en données brutes)

### Implementation for User Story 1

- [ ] T017 [US1] Implémenter l'exception privée `_IncompleteRanking` et la garde de complétude dans `backend/app/scrapers/sporthive.py` : comparaison **plancher** (`lus < classificationsCount` → écart de la course), saut sans requête des courses à `classificationsCount` nul, et les deux journaux (`logger.warning` / `logger.info`, en anglais). Le tri des défaillances se fait sur le **type** d'exception, jamais sur son message
- [ ] T018 [US1] Implémenter les helpers scalaires dans `backend/app/scrapers/sporthive.py` : `_time` (troncature de la fraction **avant** `normalize_time`, `00:00:00` → `""`), `_rank` (`0` → `None`), le statut par `derive_status_from_label` complété du repli sur le rang avec `STATUS_FINISHER` / `STATUS_DNF` importés de `scrapers/base.py`, et l'identité par `split_athlete_name` sauf relais
- [ ] T019 [US1] Implémenter `_segments` dans `backend/app/scrapers/sporthive.py` : un segment par entrée de `legs` dans l'ordre publié, libellés depuis la table fermée sur `leg["type"]` (`natation` / `transition` / `vélo` / `course à pied`), `sportName` **jamais** lu, `type` inconnu rendu verbatim, segments à durée vide écartés
- [ ] T020 [US1] Implémenter les métadonnées d'épreuve dans `backend/app/scrapers/sporthive.py` : `qualify_event_name(eventName, raceName)`, `classify_event_type(raceName, contexte=f"{eventName} {eventType}")`, distance en km, `is_relay` par motif d'intitulé sans accents, et `raw_data["city"]` / `raw_data["country"]`
- [ ] T021 [US1] Implémenter `scrape_event_all` dans `backend/app/scrapers/sporthive.py` : lecture d'URL, `_fetch_event`, `_fetch_races`, boucle sur **toutes** les courses de l'événement indépendamment de celle pointée par l'URL (FR-005), rattrapant `_IncompleteRanking`, et assemblage des `ScrapedResult` avec `source_url` = l'URL **demandée** (clé du cache TTL, jamais reconstruite)

**Checkpoint**: US1 fonctionne de bout en bout — l'URL du Sheet s'importe. Un
événement dont toutes les courses seraient écartées rendrait encore une liste
vide sans erreur : c'est US3 qui referme ce cas.

---

## Phase 4: User Story 2 - Voir les membres du club apparaître dans le périmètre club (Priority: P2)

**Goal**: les participations portent le club déclaré par la source, ce qui fait
entrer les membres du TCN dans le tableau de bord, la page club et les stats.

**Independent Test**: importer l'épreuve du Sheet, filtrer sur `scope=club`, et
constater les 29 participations « TRI CLUB NANTAIS ».

**Note de périmètre honnête** : cette story n'a presque **pas** de code propre.
Le scraper ne fait que renseigner `club` ; tout le reste (reconnaissance TCN,
filtrage) est déjà porté par `core/club.py` et l'API de lecture. Ses tâches sont
donc un test de bout en bout et une **garde** contre la réimplémentation — c'est
précisément la faute de #76.

- [ ] T022 [US2] Test rouge du club dans `backend/tests/test_sporthive.py` : `teamName: "TRI CLUB NANTAIS"` → `club` renseigné et reconnu par `core.club.is_tcn`, `teamName: null` → `club = ""`, et un libellé voisin (`ASPTT NANTES TRI`) **non** reconnu (FR-019)
- [ ] T023 [US2] Renseigner `club` depuis `teamName` dans le mapping de `backend/app/scrapers/sporthive.py` (`None` → `""`) — à compléter si T018 ne l'a pas déjà couvert
- [ ] T024 [US2] Test de non-réimplémentation dans `backend/tests/test_sporthive.py` : le module `sporthive.py` ne contient **aucun** libellé de club en dur ni aucune logique d'appartenance — assertion sur le source du module, sur le modèle de la garde de #76. Contrairement à `t2area.py`, ce scraper n'a **aucune** raison de connaître le TCN

**Checkpoint**: US1 et US2 fonctionnent, chacune vérifiable seule.

---

## Phase 5: User Story 3 - Comprendre pourquoi un lien Sporthive n'est pas importable (Priority: P3)

**Goal**: un lien qui ne peut pas être importé rend une cause explicite — jamais
un échec muet, jamais l'import silencieux d'une épreuve étrangère, jamais un
succès à zéro course.

**Independent Test**: soumettre une URL sans identifiant d'événement, une URL dont
l'identifiant est inconnu de la source, et un événement dont toutes les courses
sont écartées ; chacune rend un message nommant la cause.

### Tests for User Story 3

- [ ] T025 [US3] Test rouge des refus de lecture dans `backend/tests/test_sporthive.py` : URL sans identifiant → `ValueError` **nommant la forme attendue** (FR-003), et `GET /events/{id}` en 404 → `ValueError` « événement introuvable », rien de persisté
- [ ] T026 [US3] Test rouge du refus à zéro course dans `backend/tests/test_sporthive.py` : toutes les courses tronquées, toutes à `classificationsCount: 0`, et un événement sans aucune course → `ValueError` en **français** dans les trois cas ; jamais une liste vide rendue (D14, FR-008c)
- [ ] T027 [US3] Test rouge de non-régression sur l'ordinal de course dans `backend/tests/test_sporthive.py` : verrouiller qu'aucune requête n'est émise vers `/races/1` — sur la source réelle, cet appel répond 200 et rend une épreuve de 2015, c'est le risque d'import silencieux d'une épreuve étrangère (D1, FR-004)

### Implementation for User Story 3

- [ ] T028 [US3] Implémenter la traduction des refus dans `backend/app/scrapers/sporthive.py` : message de forme attendue sur URL illisible, 404 → « événement introuvable », et `ValueError` finale si la liste de `ScrapedResult` est vide. Ces messages sont en **français** : ils traversent `ScraperError` et sont réaffichés verbatim par le front (principe I, cas mixte `DomainError`)
- [ ] T029 [US3] Vérifier — sans écrire de code — que les échecs Sporthive figurent au détail des épreuves en erreur des bilans CLI (FR-024) et que le cache de fraîcheur court-circuite un second import (FR-025) : `uv run python -m app.cli rescrape-db --url <URL fautive> --json | jq '.failures'`, puis relancer l'import de l'URL valide et constater `cached`

**Checkpoint**: les trois user stories sont indépendamment vérifiables.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T030 [P] Ajouter le test réseau réel dans `backend/tests/test_integration_scrapers.py` (marker `integration`) : l'événement du Sheet rend 6 courses et 955 participations, chaque course égalant le nombre de classés annoncé (SC-002) et aucune participation n'atterrissant sous une épreuve étrangère à l'événement désigné (SC-004) — c'est aussi lui qui casse en premier si MYLAPS déplace son API (D13)
- [ ] T031 [P] Documenter le fournisseur dans `AGENTS.md` §Fournisseurs supportés : les trois profondeurs d'URL, le plafond de 10, l'ordinal `races/{n}`, `validity` contre les booléens morts, les deux portées d'échec, et le statut tranché sur le rang
- [ ] T032 Exécuter les points de contrôle de `specs/004-sporthive-scraper/quickstart.md` : le lien du Sheet importé sans intervention et le membre du club visible en périmètre club (SC-001), les non-classés à leur statut réel dont aucun finisher (SC-003), les 5 segments d'un triathlon et les 4 d'une course d'enfants (SC-005), un lien non importable qui nomme sa cause sans interrompre le lot (SC-006), et la requête « Sporthive : classés marqués DNF (doit être 0) » (SC-008)
- [ ] T033 Vérifier la suite complète : `cd backend && uv run pytest -m "not integration"` et `uv run ruff check .` verts — les tests du fournisseur s'exécutent sans aucun accès réseau (SC-007, principe III : une PR n'entre pas sans)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** : aucune dépendance.
- **Foundational (Phase 2)** : dépend de Phase 1 — **bloque** les trois stories.
- **US1 (Phase 3)** : dépend de Phase 2. C'est le MVP.
- **US2 (Phase 4)** : dépend de Phase 2 ; en pratique T023 se greffe sur le
  mapping de T018, donc à faire après US1 plutôt qu'en parallèle.
- **US3 (Phase 5)** : dépend de Phase 2 pour T025, et de **T021** pour T026 (le
  refus à zéro course s'insère dans l'assemblage).
- **Polish (Phase 6)** : dépend de US1 au minimum ; T030 exige le réseau.

### Divergence avec le découpage de `plan.md`

`plan.md` note que l'étape 7 (assemblage) dépend désormais de l'étape 3 (garde de
complétude). C'est repris ici : **T021 dépend de T017**. En revanche, les tâches
T017 à T021 ne sont pas parallélisables entre elles, contrairement à ce que la
lecture optimiste du plan suggère — même fichier (cf. l'avertissement en tête).

### Within Each User Story

- Le test rouge précède **toujours** l'implémentation, et on vérifie qu'il échoue.
- Helpers avant assemblage : T017–T020 avant T021.
- Story complète avant de passer à la priorité suivante.

### Parallel Opportunities

Réelles (fichiers distincts, aucune dépendance) :

- **T003, T004, T005** — trois lots de fixtures, aucun fichier partagé.
- **T008 + T009** — `test_registry.py` et `registry.py`, indépendants du corps du
  scraper.
- **T030 + T031** — test d'intégration et documentation.

Tout le reste est séquentiel : `sporthive.py` et `test_sporthive.py` sont chacun
un fichier unique.

---

## Parallel Example: Phase 1

```bash
# Les trois lots de fixtures, en parallèle :
Task: "T003 fixtures d'événement dans backend/tests/fixtures/"
Task: "T004 fixtures de classement dans backend/tests/fixtures/"
Task: "T005 fixtures de cas limites dans backend/tests/fixtures/"
```

## Parallel Example: Phase 2

```bash
# Détection au registre, hors du corps du scraper :
Task: "T008 jeton sporthive.com + cas de détection dans backend/tests/test_registry.py"
Task: "T009 SporthiveProvider + entrée PROVIDERS dans backend/app/scrapers/registry.py"
```

---

## Implementation Strategy

### MVP (US1 seule)

1. Phase 1 — Setup.
2. Phase 2 — Foundational (bloquant).
3. Phase 3 — US1.
4. **STOP et VALIDER** : `rescrape-db --url <URL du Sheet>` rend 6 épreuves et
   955 participants ; le lien du Sheet, aujourd'hui ignoré, est importé (SC-001).

À ce stade la valeur de l'issue #53 est livrée. Les membres du TCN de l'épreuve
apparaissent déjà, US2 relevant surtout de la vérification.

### Livraison incrémentale

1. Setup + Foundational → socle.
2. + US1 → **MVP**, l'épreuve du Sheet est en base.
3. + US2 → périmètre club vérifié, garde anti-#76 en place.
4. + US3 → les liens fautifs rendent une cause, et un import à zéro course cesse
   de passer pour un succès.
5. + Polish → schéma d'API verrouillé par le test réseau, `AGENTS.md` à jour.

### Stratégie à plusieurs agents

Le gain est faible et concentré sur la Phase 1 : les fixtures se répartissent à
trois, `registry.py` se traite en parallèle du scraper. Le corps du module se fait
en séquence par un seul agent — c'est un fichier unique de ~600 lignes attendues,
sur le modèle d'`oktime.py`.

---

## Notes

- `[P]` = fichier différent, aucune dépendance sur une tâche incomplète.
- Aucune migration Alembic, aucun changement de contrat API ou CLI, aucun toucher
  au front : le front lit `is_supported` de l'API et rend les libellés de splits
  par le chemin générique de `lib/utils/splits.ts`.
- Vérifier que chaque test échoue **avant** d'implémenter.
- Un commit par tâche ou par groupe cohérent (Conventional Commits).
- Langue : identifiants, docstrings techniques, noms de tests et `logger.*` en
  **anglais** ; messages de `ValueError` réaffichés par le front et libellés de
  splits en **français** (principe I).
