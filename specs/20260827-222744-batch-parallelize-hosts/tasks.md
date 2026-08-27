---

description: "Task list — Parallélisation du batch d'import par hôte de chronométrage"
---

# Tasks: Parallélisation du batch d'import par hôte de chronométrage

**Input**: Design documents from `specs/20260827-222744-batch-parallelize-hosts/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/cli-batch-parallelism.md](./contracts/cli-batch-parallelism.md), [quickstart.md](./quickstart.md)

**Issue**: [#690](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/690)

**Tests**: le Principe III de la constitution v1.1.1 est **non-négociable** — TDD sans réseau. Chaque tâche de test précède l'implémentation qu'elle couvre et doit **échouer** avant d'être satisfaite. Aucune dérogation demandée dans `plan.md`.

**Organization**: tâches groupées par user story (`spec.md`), chacune livrable et vérifiable seule dans la mesure du possible — voir la note d'ordonnancement ci-dessous pour l'exception assumée.

## Format: `[ID] [P?] [Story] Description`

- **[P]** : parallélisable (fichiers différents, aucune dépendance sur une tâche en cours)
- **[Story]** : US1 / US2 / US3, selon `spec.md`
- Chemins de fichiers explicites, relatifs à la racine du worktree

## Path Conventions

Application existante : `backend/` (Python). Aucun dossier nouveau — la
feature modifie `app/services/batch.py`, `app/services/progress.py`,
`app/cli/progress.py` et les deux commandes CLI qui consomment `run_batch`
(cf. `plan.md` §Project Structure).

---

## Note d'ordonnancement, à lire avant de commencer

`spec.md` classe la fiabilité du bilan et de la supervision dans **US3**
(P2, priorité la plus basse des trois). Ce classement reflète la **valeur
métier** de chaque story, pas l'ordre où le code peut se permettre d'être
incorrect. Deux morceaux d'US3 sont en réalité des **prérequis de sûreté** de
la concurrence elle-même, pas des améliorations qu'on pourrait différer :

- l'accumulation thread-safe de `BatchTotals` — sans elle, la concurrence
  d'US1 perd ou corrompt silencieusement des compteurs (violerait FR-004/
  SC-003 dès le premier lot multi-hôtes) ;
- l'arrêt coopératif sur Ctrl-C — sans lui, les threads de groupe (non
  démons par défaut dans `ThreadPoolExecutor`) empêchent le processus de
  sortir tant qu'ils n'ont pas fini **naturellement**, ce qui peut geler un
  Ctrl-C pendant toute la durée restante du lot (régression de FR-007/SC-004).

Ces deux points sont donc traités dans **Phase 3 (US1)**, pas Phase 5 (US3) :
un `run_batch` parallèle n'est mergeable qu'avec les deux. Phase 5 (US3) se
concentre sur ce qui reste réellement indépendant et différable sans risque
de sûreté : l'**identité de groupe** dans `ProgressReporter` et son affichage
(`PlainReporter`/`RichReporter`) — sans elle, le batch reste correct et
sûr, seul l'affichage en cours d'exécution reste trompeur.

Phase 4 (US2) ne contient volontairement **aucune tâche d'implémentation** :
l'invariant de politesse par chronométreur découle, par construction, du
regroupement de la Phase 2 (Foundational) et du modèle « un thread par
groupe » de la Phase 3 (US1) — deux threads du même groupe ne peuvent
structurellement pas exister. Phase 4 verrouille cet invariant par des tests,
y compris pour les deux providers multi-domaines identifiés en `research.md`.

---

## Phase 1: Setup

**Purpose**: rien à initialiser — la stack et l'outillage sont en place.
Borner le terrain avant de le toucher.

- [X] T001 Vérifier l'état de départ vert depuis `backend/` :
  `uv run pytest -m "not integration"` et `uv run ruff check .` — 4 échecs
  pré-existants et hors périmètre dans `test_auth/test_startup_warning.py`
  (worktree identique à `main`, non touchés par cette feature) ; ruff propre
- [X] T002 [P] Confirmer par `grep -n "_HOSTS\s*=" backend/app/scrapers/registry.py`
  que les providers multi-domaines recensés dans `research.md` (Wiclax,
  RaceResult) n'ont pas changé depuis la conception ; noter tout écart avant
  de continuer — conforme, aucun écart

**Checkpoint**: point de comparaison établi, conception toujours à jour.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: le regroupement par chronométreur, brique commune aux trois user
stories.

**⚠️ CRITICAL**: aucune user story ne peut commencer avant la fin de cette
phase.

- [X] T003 [P] Test (rouge) : `_group_by_host` regroupe les `BatchItem` par
  chronométreur via `app.scrapers.registry.detect_provider`, préserve l'ordre
  d'origine à l'intérieur de chaque groupe, ne fusionne **jamais** deux
  domaines d'un même provider multi-domaines sous des clés différentes, et
  donne un groupe distinct à chaque URL non reconnue par le registre (pas de
  fusion de plusieurs inconnues sous une même clé vide) — dans
  `backend/tests/test_services/test_batch.py`
- [X] T004 Implémenter `_group_by_host(items: list[BatchItem]) -> list[tuple[str, list[BatchItem]]]`
  dans `backend/app/services/batch.py`, basé sur
  `app.scrapers.registry.detect_provider(url)` avec repli sur l'hôte réseau
  littéral de l'URL quand la détection rend une chaîne vide — chaque groupe
  porte son `host_key` (pas une liste de listes nue : T011/T024 en ont besoin
  directement, sans le re-dériver) — fait passer T003
- [X] T005 [P] Ajouter dans `backend/tests/test_services/test_batch.py` (ou
  `backend/tests/conftest.py` si plus réutilisable) une fixture de
  synchronisation (`threading.Barrier`/`Event`) permettant de prouver un
  chevauchement réel entre deux traitements sans dépendre d'un `sleep()`
  minuté — consommée par les Phases 3 et 5

**Checkpoint**: regroupement correct et couvert ; outillage de test de
concurrence prêt.

---

## Phase 3: User Story 1 — Réduire le temps mur d'un batch multi-hôtes (Priority: P1) 🎯 MVP

**Goal**: des épreuves de chronométreurs différents s'exécutent en même
temps, avec un plafond de concurrence configurable, sans régression quand il
n'y a qu'un seul chronométreur, et sans jamais perdre le bilan ni bloquer un
Ctrl-C.

**Independent Test**: lancer un batch sur un lot mêlant plusieurs dizaines de
chronométreurs et mesurer le temps mur (`quickstart.md` §4) ; il doit être
significativement inférieur à `--max-concurrent-hosts 1`.

### Tests for User Story 1

> **NOTE: écrire ces tests EN PREMIER, vérifier qu'ils ÉCHOUENT avant l'implémentation** (Principe III, non-négociable).

- [X] T006 [P] [US1] Test (rouge) : deux chronométreurs distincts sont
  traités en même temps — prouvé par la fixture de T005 (les deux scrapes
  démarrent avant qu'aucun ne termine). Inclut le cas du plafond : avec
  `max_concurrent_hosts=k` et k+1 groupes, au plus k tournent en même temps à
  tout instant (la fixture de barrière le prouve, pas un minutage) — dans
  `backend/tests/test_services/test_batch.py`
- [X] T007 [P] [US1] Test (rouge) : le bilan (`BatchTotals`) d'un lot
  multi-hôtes traité en concurrence contient exactement les mêmes compteurs
  et le même contenu (`failures`, `passive_sources`, `reassignments`) qu'une
  exécution avec `--max-concurrent-hosts 1` sur le même lot — ordre non
  garanti, contenu identique (FR-004/SC-003). Inclut le cas d'isolation des
  échecs (FR-009) : un groupe qui échoue en cours de route n'affecte ni le
  déroulement ni le résultat d'un autre groupe concurrent, toujours en
  succès — dans `backend/tests/test_services/test_batch.py`
- [X] T008 [P] [US1] Test (rouge) : un Ctrl-C (`KeyboardInterrupt`) pendant un
  lot multi-hôtes empêche toute **nouvelle** épreuve de démarrer après le
  signal, laisse les épreuves déjà en cours aller à leur terme, et produit un
  `totals.interrupted=True` reflétant exactement le travail commité — dans
  `backend/tests/test_services/test_batch.py`
- [X] T009 [P] [US1] Test (rouge) : un lot mono-chronométreur (ou avec moins
  de groupes que le plafond de concurrence) produit exactement le même bilan
  et la même **séquence et le même compte** d'appels reporter qu'avant la
  feature (mêmes évènements dans le même ordre : `batch_start` → `item_start`
  → … → `item_done` → `batch_end`) — les tests existants
  (`test_run_batch_relaie_la_progression_intra_epreuve` et consorts) restent
  verts (SC-002). **Note** : la Phase 5 (T023) ajoute un paramètre `host` à
  chaque tuple `item_start`/`item_progress`/`item_done` — la forme exacte des
  tuples changera alors dans ces mêmes tests (T009 ne gèle que la séquence
  d'évènements, pas leur arité littérale) ; voir T023
- [X] T010 [P] [US1] Test (rouge) : `--max-concurrent-hosts` est accepté par
  `import-sheet` et `rescrape-db`, transmis jusqu'à `run_batch`, et refuse une
  valeur non entière strictement positive avec le code de sortie **2**.
  Inclut une assertion sur `--json` (FR-005) : le jeu de clés de sortie sur un
  lot multi-hôtes est strictement identique à celui obtenu avec
  `--max-concurrent-hosts 1` (même schéma, seul l'ordre des listes peut
  différer) — dans `backend/tests/test_cli/`

### Implementation for User Story 1

- [X] T011 [US1] Refondre la boucle de `run_batch` (`backend/app/services/batch.py`) :
  dispatcher les groupes de `_group_by_host` dans un
  `concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent_hosts)`,
  un thread par groupe traitant ses épreuves strictement en séquence (même
  corps de boucle qu'aujourd'hui, délai de politesse inclus), chaque thread
  ouvrant sa propre `Session` via `session_scope()` — fait passer T006, T009
- [X] T012 [US1] Protéger l'accumulation dans `BatchTotals` contre l'écriture
  concurrente (verrou léger autour du seul bloc de comptabilité par épreuve,
  hors du scrape lui-même) — fait passer T007. **Post-revue de code** :
  l'ouverture de la `Session` d'un groupe (`session_factory()`) pouvait lever
  hors de tout filet et faire perdre le bilan de tout le batch (pool épuisé,
  coupure transitoire) — un groupe en échec d'ouverture compte désormais
  chacune de ses épreuves en erreur au lieu de faire planter `run_batch` ;
  test de régression ajouté
  (`test_run_batch_echec_d_ouverture_de_session_de_groupe_ne_perd_pas_le_bilan`)
- [X] T013 [US1] Remplacer la capture de `KeyboardInterrupt` autour de
  l'ancienne boucle séquentielle par un signal coopératif (`threading.Event`)
  vérifié par chaque thread de groupe entre deux épreuves de son lot ; le
  thread principal attend la fin propre de tous les groupes avant d'assembler
  le bilan partiel et de laisser l'appelant sortir en 130 — fait passer T008
- [X] T014 [US1] Ajouter le paramètre `max_concurrent_hosts: int = 4` à
  `run_batch`, et le répercuter dans ses deux appelants
  (`backend/app/services/bulk_import_service.py`,
  `backend/app/services/rescrape_service.py`)
- [X] T015 [P] [US1] Ajouter l'option Typer `--max-concurrent-hosts` (défaut
  4, entier strictement positif) à
  `backend/app/cli/commands/import_sheet.py` — fait passer T010
- [X] T016 [P] [US1] Ajouter la même option à
  `backend/app/cli/commands/rescrape_db.py` — fait passer T010

**Checkpoint**: `run_batch` est parallèle, thread-safe côté bilan,
interruptible proprement, pilotable en CLI — livrable en l'état (MVP), même
si l'affichage de progression reste temporairement ambigu sous concurrence
(couvert par US3).

---

## Phase 4: User Story 2 — Continuer à respecter la politesse envers chaque chronométreur (Priority: P1)

**Goal**: verrouiller par des tests l'invariant qui rend la parallélisation
acceptable — aucune accélération du rythme perçu par un chronométreur donné,
y compris ceux qui publient sur plusieurs domaines.

**Independent Test**: sur un lot où plusieurs épreuves ciblent le même
chronométreur (mono- ou multi-domaine), vérifier qu'aucune paire de requêtes
vers lui ne part sans le délai de politesse actuel entre elles.

### Tests for User Story 2

> Aucune implémentation nouvelle attendue ici — voir la note d'ordonnancement. Si un de ces tests échoue, c'est `_group_by_host` (T004) ou l'orchestration (T011) qu'il faut corriger.

- [X] T017 [P] [US2] Test (rouge, doit passer sans nouveau code si T004/T011
  sont corrects) : plusieurs épreuves du même chronométreur restent traitées
  en séquence avec le même délai de politesse qu'aujourd'hui, même quand
  d'autres chronométreurs tournent en parallèle — dans
  `backend/tests/test_services/test_batch.py`
- [X] T018 [P] [US2] Test (idem) : deux domaines d'un même chronométreur
  multi-domaines (Wiclax : `wiclax-results.com` / `chronosmetron.com` /
  `chronowest.fr` ; ou la famille RaceResult) ne partent **jamais** en
  parallèle l'un de l'autre — dans `backend/tests/test_services/test_batch.py`
- [X] T019 [US2] Si T017 ou T018 échoue : corriger `_group_by_host` (T004) ou
  l'orchestration de `run_batch` (T011) jusqu'à ce qu'ils passent — pas de
  nouvelle capacité, une correction du regroupement — les deux passent du
  premier coup, aucune correction nécessaire

**Checkpoint**: invariant de politesse verrouillé par test, y compris pour
les chronométreurs multi-domaines.

---

## Phase 5: User Story 3 — Garder une supervision fiable de la progression (Priority: P2)

**Goal**: l'exploitant peut distinguer, en temps réel, quelles épreuves de
quels chronométreurs sont en cours et lesquelles sont terminées — sans que ça
ne mette en jeu la sûreté du batch (déjà acquise en Phase 3).

**Independent Test**: observer la sortie de progression (`--plain` et
terminal Rich) d'un batch multi-hôtes et vérifier qu'aucune ligne/tâche n'est
attribuée au mauvais chronométreur.

### Tests for User Story 3

- [X] T020 [P] [US3] Test (rouge) : le Protocol `ProgressReporter`
  (`item_start`/`item_progress`/`item_done`) porte une identité de groupe, et
  `NullReporter` l'accepte sans effet — dans
  `backend/tests/test_services/test_batch.py` (si extrait, nommer le nouveau
  fichier `backend/tests/test_services/test_progress.py` — **pas**
  `test_progress.py` à la racine de `test_cli/`, qui teste déjà
  `app/cli/progress.py`, un module différent)
- [X] T021 [P] [US3] Test (rouge) : `PlainReporter` distingue par une
  annotation explicite deux épreuves de chronométreurs différents en cours en
  même temps, sans mélanger leurs lignes — dans
  `backend/tests/test_cli/` (fichier de test de `app/cli/progress.py`)
- [X] T022 [P] [US3] Test (rouge) : `RichReporter` maintient une tâche Rich
  distincte par chronométreur actif, sans que le démarrage d'un groupe
  n'efface ou n'écrase l'état d'un autre groupe en cours — dans
  `backend/tests/test_cli/`

### Implementation for User Story 3

- [X] T023 [US3] Étendre le Protocol `ProgressReporter`
  (`backend/app/services/progress.py`) : `item_start`/`item_progress`/
  `item_done` gagnent un paramètre d'identité de groupe ; mettre à jour
  `NullReporter` en conséquence. Mettre à jour aussi le `FakeReporter`/
  `fake_reporter` de `backend/tests/test_services/conftest.py` et les
  assertions des tests existants qui enregistrent ses appels (T009 et
  consorts) pour inclure ce nouvel argument — fait passer T020, sans casser
  T009
- [X] T024 [US3] Adapter `run_batch` (`backend/app/services/batch.py`) pour
  transmettre l'identité de groupe à chaque appel reporter
- [X] T025 [P] [US3] Adapter `PlainReporter`
  (`backend/app/cli/progress.py`) — fait passer T021
- [X] T026 [P] [US3] Adapter `RichReporter`
  (`backend/app/cli/progress.py`) — une tâche Rich par groupe actif, au lieu
  du singleton `_item_task` actuel — fait passer T022

**Checkpoint**: toutes les user stories sont fonctionnelles ; la progression
reste lisible et correctement attribuée sous exécution concurrente.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T027 [P] Mettre à jour `backend/app/cli/AGENTS.md` : documenter
  `--max-concurrent-hosts`, la sémantique de regroupement par chronométreur
  (y compris le cas multi-domaines), et le fait que l'ordre de `failures`/
  `passive_sources` dans `--json` n'est plus garanti égal à l'ordre du lot
  d'entrée dès qu'il y a plus d'un chronométreur
- [X] T028 Exécuter `quickstart.md` de bout en bout (sections 1 à 3
  obligatoires ; section 4 optionnelle/manuelle, réseau réel) et consigner
  dans la description de la PR le temps mur mesuré (`--max-concurrent-hosts 1`
  vs défaut) sur un lot multi-hôtes réel — §1 (suite `test_batch.py`) et §2
  (suite complète + ruff) exécutées et vertes. §3/§4 **non exécutées** ici :
  elles demandent un vrai scrape réseau vers un chronométreur tiers
  (klikego.com) via `backend/.env`, qui pointe la base **de production**
  Azure — une action réseau sortante vers un tiers, hors du périmètre d'une
  vérification autonome. À faire manuellement avant merge si une confirmation
  empirique du gain de temps mur est souhaitée.
- [X] T029 `uv run pytest -m "not integration"` et `uv run ruff check .` verts
  sur l'ensemble de la suite backend, sans régression hors du périmètre de la
  feature — 4239 passed (+4 échecs pré-existants hors périmètre, identiques à
  la baseline T001) ; `ruff check .` propre ; suite rejouée deux fois, stable

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** : aucune dépendance — démarre immédiatement
- **Foundational (Phase 2)** : dépend de la Phase 1 — **bloque** les trois
  user stories
- **US1 (Phase 3)** : dépend de la Phase 2 ; c'est le cœur mergeable (MVP)
- **US2 (Phase 4)** : dépend de la Phase 2 **et** de la Phase 3 (elle teste
  l'orchestration que Phase 3 vient de construire) — ce n'est **pas**
  indépendant de l'implémentation, seulement de tâches d'implémentation
  supplémentaires
- **US3 (Phase 5)** : dépend de la Phase 2 ; peut démarrer en parallèle de
  Phase 3/4 (fichiers disjoints : `progress.py` vs `batch.py`), mais son
  intégration finale (T024) suppose que `run_batch` (T011) existe déjà
- **Polish (Phase 6)** : dépend de toutes les phases précédentes

### Parallel Opportunities

- T001/T002 en parallèle (Setup)
- T003/T005 en parallèle (Foundational, fichiers/aspects disjoints)
- T006/T007/T008/T009/T010 en parallèle (tests US1, avant T011)
- T015/T016 en parallèle (deux commandes CLI distinctes)
- T017/T018 en parallèle (tests US2)
- T020/T021/T022 en parallèle (tests US3) ; T025/T026 en parallèle
  (implémentations US3, fichiers disjoints dans `cli/progress.py` mais
  classes distinctes)
- **US3 (Phase 5) peut être menée en parallèle de US1 (Phase 3)** par une
  deuxième personne dès la Phase 2 terminée, à condition d'intégrer T024
  après que T011 existe

---

## Parallel Example: User Story 1

```bash
# Tests US1, en parallèle (avant toute implémentation) :
Task: "Test concurrence effective de deux chronométreurs (T006)"
Task: "Test équivalence du bilan sous concurrence (T007)"
Task: "Test Ctrl-C coopératif multi-hôtes (T008)"
Task: "Test non-régression mono-chronométreur (T009)"
Task: "Test option --max-concurrent-hosts (T010)"

# Options CLI, en parallèle (après T011-T014) :
Task: "Option --max-concurrent-hosts sur import-sheet (T015)"
Task: "Option --max-concurrent-hosts sur rescrape-db (T016)"
```

---

## Implementation Strategy

### MVP First (User Story 1 seule)

1. Phase 1 (Setup) + Phase 2 (Foundational)
2. Phase 3 (US1) — inclut la sûreté du bilan et du Ctrl-C, non séparables
   (voir note d'ordonnancement)
3. **STOP et VALIDER** : `quickstart.md` §1-3, puis §4 si un accès réseau
   réel est disponible
4. Mergeable en l'état : temps mur réduit, contrat CLI intact, rien perdu sur
   Ctrl-C — l'affichage de progression reste seulement approximatif sous
   concurrence

### Incremental Delivery

1. Setup + Foundational → terrain prêt
2. US1 → validé indépendamment → **MVP**, mergeable
3. US2 → verrouille l'invariant de politesse par test (aucun risque de
   régression fonctionnelle, tâches de test uniquement)
4. US3 → supervision précise sous concurrence (peut être menée en parallèle
   de US1/US2 par une autre personne, s'intègre en dernier)
5. Polish → documentation, mesure réelle, suite complète verte

---

## Notes

- [P] = fichiers différents, aucune dépendance non résolue
- Vérifier que chaque test échoue avant d'implémenter (Principe III)
- Commit après chaque tâche ou groupe logique cohérent
- S'arrêter à chaque checkpoint pour valider la story avant de continuer
- Ne pas rouvrir `backend/app/scrapers/registry.py` : cette feature le
  **consomme** (résolution URL → chronométreur), elle ne le modifie pas
