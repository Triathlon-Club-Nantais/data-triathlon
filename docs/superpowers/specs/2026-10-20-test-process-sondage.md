# Sondage : processus de test (#1704)

Mesures et constats de l'epic. Ce fichier prime sur le design, la spec et le plan.

## Tests rouges du 20/10

Constat de départ : une exécution avec couverture de toute la suite frontend sur `main` (machine chargée, load 12 à 34 sur 8 coeurs) a mis rouges, deux fois de suite, trois tests : `AthleteDetachAction` « sépare les résultats cochés après confirmation, puis ouvre la nouvelle fiche », `TeammatesDialog` « ne propose pas un coureur déjà dans l'équipe », `CalendrierEntrainements` « liste les séances à venir d'abord… » (bloc « vu le 10/10/2026 »).

Mesures (vitest 5.0.2, `@vitest/coverage-v8` 5.0.2, les trois fichiers, 42 tests) :

| Condition | Résultat |
| --- | --- |
| Chaque fichier isolé, sans couverture | vert |
| Chaque fichier isolé, avec couverture v8 | vert |
| Les trois fichiers ensemble, sans couverture, 5 exécutions (load 17 à 33) | vert 5/5 |
| Couverture, 24 boucles CPU parasites (load 17) | vert 3/3 |
| Couverture, 32 boucles parasites (load 40 à 44) | vert 4/4 |
| Couverture, 64 boucles parasites (load 78 à 83, soit 10x les coeurs) | rouge 3/3 : 3, 4 puis 1 test rouge |

Aucune condition raisonnable ne reproduit les trois tests nommés. Le rouge n'apparaît qu'en famine CPU extrême, et il touche alors des tests différents d'une exécution à l'autre, dont d'autres que les trois (`TeammatesDialog` « n'attribue rien tant que l'équipe compte moins de deux coureurs », « attribue le relais aux coureurs choisis, dans l'ordre », « renvoie vers le rattachement… »). Deux signatures : `Unable to find role=... ` après le délai par défaut de 1000 ms de `findBy*`, et dépassement du `testTimeout` de 5 s.

Horloge de `CalendrierEntrainements` : le bloc fige `Date` (`vi.useFakeTimers({ toFake: ["Date"] })` + `vi.setSystemTime(new Date(2026, 9, 10, 12))`), donc aucune dépendance à « aujourd'hui ». Les minuteries réelles restent actives, ce qui est voulu pour `findBy*`.

Rejeu de la condition d'origine : suite frontend complète sous couverture v8 (`npx vitest run --coverage --coverage.provider=v8 --coverage.reportOnFailure`), en parallèle d'un `pytest -m "not integration" --cov=app` backend complet (7209 passed), load 18 à 21 :

| Exécution | Résultat |
| --- | --- |
| Suite complète + couverture, run 1 | 305 fichiers, 3445 tests verts |
| Suite complète + couverture, run 2 | 1 rouge, `AthleteHeaderActions` « bascule la hiérarchie d'un seul rendu, panneau chargé » (1050 ms, délai `findBy*`), aucun des trois tests d'origine |
| `components/athletes` + `components/admin/jeunes`, ordre de fichiers et de tests mélangé, seeds 1, 42, 1337 | 200 tests verts à chaque seed |

Conclusion : **ouverte**. Les trois tests d'origine n'ont été rouges dans aucune des conditions rejouées ; la pollution entre tests (ordre mélangé) n'a rien révélé sur ces dossiers. Observations seulement, sans cause établie : sous forte charge, des tests quelconques passent le délai de 1 s de `findBy*` ou le `testTimeout` de 5 s, et un test étranger à la liste a échoué ainsi à load 18 à 21. Aucun correctif appliqué (hausse des délais et retries interdits). Si les trois rouges reviennent, rouvrir avec la sortie complète de l'exécution fautive (messages d'erreur, load, processus concurrents).

## Coût de create_all

Suite unitaire backend de la boucle locale (`pytest -m "not integration" -n 0`, sans `--migrations`), 7135 passés, 3841 appels à `create_all`/`drop_all`. Instrumentation temporaire non commitée : `time.perf_counter` autour de `MetaData.create_all` et `drop_all`, cumul écrit en fin de session.

| Exécution | load au départ | durée suite | `create_all` | `drop_all` | part |
| --- | --- | --- | --- | --- | --- |
| 1 | 1,49 | 178,6 s | 46,5 s | 16,9 s | **35,5 %** |
| 2 | 3,97 (hors seuil) | 947,1 s | 322,4 s | 92,0 s | non retenue |
| 3 | 16,39 (hors seuil) | 175,0 s | 45,6 s | 16,3 s | non retenue (35,3 %, concorde) |

Seule l'exécution 1 est sous le seuil de charge (< 2,0) ; la machine s'est chargée pendant et après (load 4 à 32), donc les durées absolues sont gonflées (la suite fait ~58 s au repos, cf. sondage du 2026-08-20) mais la part, mesurée dans le même processus, est stable entre les exécutions 1 et 3. Une seule répétition valide : le minimum de 2 n'est pas atteint.

Décision : part ≈ 35 % > 10 %, donc fixture transactionnelle retenue (schéma partagé par worker, rollback par test). Implémentation à faire séparément ; à remesurer au repos après coup.

### Après la fixture transactionnelle

`db_session` et `db_session_fk` partagent un schéma par worker xdist (moteur SQLite mémoire, `create_all` une fois) ; chaque test tourne dans une transaction annulée, `Session(bind=connection, join_transaction_mode="create_savepoint")`, avec le contournement pysqlite (événements `connect` et `begin`). Même protocole, même instrumentation temporaire non commitée, `-n 0 -p no:randomly`.

| Exécution | load au départ | durée suite | `create_all` | `drop_all` | part |
| --- | --- | --- | --- | --- | --- |
| 1 | 16,54 (hors seuil après 10 min d'attente) | 131,5 s | 24 appels, 4,30 s | 1 appel, 0,00 s | non retenue (3,3 %) |
| 2 | 6,12 (hors seuil après 10 min d'attente) | 224,6 s | 24 appels, 6,50 s | 1 appel, 0,01 s | non retenue (2,9 %) |
| 3 | 1,73 | 95,0 s | 24 appels, 3,58 s | 1 appel, 0,00 s | **3,8 %** |

Une seule exécution sous le seuil (load 2,8 à sa fin, 20 processus `pytest`/`vitest` étrangers pendant l'exécution 1) : le minimum de 2 n'est pas atteint, la durée absolue reste à remesurer au repos. La part, elle, concorde sur les trois : de 3841 appels et ~35 % à 24 appels et ~3-4 %.

Les 24 appels restants : les deux moteurs du worker (`db_session`, `db_session_fk`), les 10 tests marqués `own_database`, et des moteurs propres à leur test, hors de `db_session`, laissés tels quels (`db_session_concurrent` de `test_services/conftest.py`, fichier SQLite réel pour du vrai multi-thread ; `_two_sessions` de `test_course_repository.py` ; `test_core/test_sql_observability.py` ; `test_cli/test_logging.py`).

Nombre de tests : 7135 passés, 19 ignorés avant comme après, en ordre fixe (`-p no:randomly`) comme en ordre aléatoire (`--with pytest-randomly`).

`own_database` : 10 tests observent les frontières de transaction et reçoivent leur propre base, sans changement d'assertion. Huit comptent les instructions SQL d'un appel, et la `Session` jointe émet un `SAVEPOINT` à l'ouverture de chaque transaction là où le `BEGIN` implicite de pysqlite restait invisible ; deux (`test_session.py`) vérifient que `_bump_last_seen` commite par une session à part, ce qu'un SAVEPOINT imbriqué dans celui de la requête ne peut pas tenir. Deux tests de plan de requête (`test_course_repository.py`) passent leur `EXPLAIN QUERY PLAN` par la session au lieu de `bind.connect()`, la session étant liée à une `Connection`.

## Vitest

Vitest 5.0.2, suite complète du front (`npx vitest run`, 305 fichiers, 3447 tests dont 2 ignorés).

`npx vitest doctor` n'existe pas dans cette version : `doctor` est pris pour un filtre de fichiers et lance la suite en mode veille (processus tué). Pas de profil par commande dédiée ; la ventilation vient de la ligne `Duration`.

Ventilation (exécution de base 1) : `tests` 39 %, `environment` 36 %, `import` 12 %, `setup` 10 %, `transform` 3 %. Le coût d'environnement (jsdom) pèse autant que les tests eux-mêmes ; les autres exécutions sont voisines (tests 39 à 42 %, environment 34 à 37 %).

### Essai 1 : `isolate: false` sur le projet `node` seul

Config d'essai jetable (`isolate: false` ajouté au projet `node`), bras entrelacés A B A B.

| Bras | Exécution | load au départ | Duration | Tests passés | Statut |
| --- | --- | --- | --- | --- | --- |
| A (base) | 1 | 3,43 (hors seuil après 10 min d'attente) | 88,69 s | 3445 | non retenue |
| B (`isolate: false`) | 1 | 3,15 (hors seuil) | 121,77 s | 3445 | non retenue |
| A (base) | 2 | 10,07 (hors seuil) | 187,68 s | 3445 | non retenue |
| B (`isolate: false`) | 2 | 38,13 (hors seuil) | 524,29 s | 3431, 14 échecs jsdom | non retenue |

Aucune exécution sous le seuil (load < 2,0) : la machine était occupée par une autre session vitest (load 3 à 50). Le minimum retenu n'est pas atteignable ; l'écart brut (A 88,69 s contre B 121,77 s) est du bruit de charge, pas un signal. Les 14 échecs de B 2 sont des tests du projet `jsdom` (que l'essai ne touche pas), des délais dépassés à load 38, ce qui confirme la fragilité sous forte charge relevée plus haut. Mêmes 3445 passés sur les exécutions à charge modérée. Décision : **non retenu, à remesurer au repos**. Aucun changement de config.

### Essai 2 : happy-dom sur le projet `jsdom`

**Non mesuré** : aucune fenêtre sous le seuil n'est venue, et mesurer à load 30+ n'aurait produit que du bruit. `happy-dom` n'a pas été installé (`package.json` et `package-lock.json` inchangés), `test/environments.test.ts` non touché. Décision : **à remesurer au repos** (A/B entrelacé, ≥ 3 répétitions, même nombre de tests passés exigé).

## testmon

pytest-testmon 2.2.0 (`uv add --dev pytest-testmon`), machine chargée (load ~30, durées non comparables, essai fonctionnel).

Première passe `FULL_SUITE=1 uv run pytest -m "not integration" --testmon` (`-n 4`) : 7136 passés, 19 ignorés, 562 s, aucune erreur de verrou, `backend/.testmondata` (6,7 Mo) écrit. Constat : `-m` désactive la sélection (« selection automatically deactivated because -m was used »), la collecte reste faite. La forme utilisable est `--testmon --testmon-forceselect -m "not integration"`.

| Cas | Sélection |
| --- | --- |
| Aucun changement | 0 test (`4 workers [0 items]`), 22 s |
| Corps de `app/services/fftri_category.py` modifié (ligne neutre, puis annulée) | 66 tests rejoués : 19 `tests/test_services/test_fftri_category.py` (le service), 14 `test_training_session_service.py` et 1 `test_training_group_service.py` (services appelants), 16 `test_api/test_admin_training_sessions.py`, 15 `test_auth/test_admin_profiles_api.py`, 1 `test_api/test_admin_training_groups.py`. Ex. : `tests/test_services/test_fftri_category.py::test_the_season_switches_on_november_first`, `tests/test_auth/test_admin_profiles_api.py::test_the_list_carries_the_fftri_category_and_membership_end` |
| Fixture `tests/fixtures/breizhchrono_live_classements.html` modifiée (ligne ajoutée, puis retirée) | 0 test (`changed files: 0`), alors que `tests/test_breizhchrono.py` la lit : limite connue |

`git diff backend/app` vide après le cas 2. Le hook `test_gate.py` traite désormais `--testmon` comme ciblé (cas ajoutés dans `test_test_gate.py`).

testmon_retenu: oui

## Consolidation, lot 1 (`test_raceresult.py`)

mutmut sur `app.scrapers.raceresult*` (2074 mutants, module entier, sous le
budget de 30 min). Durées indicatives seulement : charge hors seuil, une
exécution par bras.

| Mesure | load au départ → à la fin | Durée murale | Tués / survivants / timeouts | Statut |
| --- | --- | --- | --- | --- |
| Avant (cartographie de la tâche 11 reprise) | 4,95 → 17,94 | 336 s | 1613 / 461 / 0 | non retenue (charge) |
| Après (cartographie incrémentale des nouveaux tests) | 2,72 → 10,92 | 145 s | 1613 / 461 / 0 | non retenue (charge) |

Verdict identique mutant par mutant. Couverture de lignes du fichier seul :
672/703 avant et après, mêmes lignes manquées. Constat d'outillage : un `mutmut
run` sans motif garde le verdict d'un mutant dont seul le test a changé (seules
les fonctions source modifiées sont invalidées) ; avec un motif, tous les
mutants désignés sont rejoués (`__main__.py`, « Rerun mutant if it's explicitly
mentioned »). Détail du lot : `2026-10-20-test-consolidation-inventaire.md`.

## Consolidation, lot 2 (`test_import_service.py`)

mutmut sur `app.services.import_service*` (389 mutants, module entier, sous le
budget de 30 min). Durées indicatives seulement : charge hors seuil, une
exécution par bras.

| Mesure | load au départ → à la fin | Durée murale | Tués / survivants / timeouts | Statut |
| --- | --- | --- | --- | --- |
| Avant (cartographie reprise du lot 1) | 3,31 → 21,67 | 505 s | 225 / 164 / 0 | non retenue (charge) |
| Après (cartographie incrémentale des nouveaux tests) | 11,22 → 10,11 | 281 s | 225 / 164 / 0 | non retenue (charge) |

Verdict identique mutant par mutant (`import_service.py.meta` comparé). Couverture
de lignes du fichier seul : 101/105 avant et après, mêmes lignes manquées ;
couverture de tout `app/` par ce fichier : lignes manquées identiques.

## Consolidation, lot 3 (`RaceFinishers.test.tsx`)

Stryker sur `components/results/RaceFinishers.tsx` (754 mutants, fichier entier,
sous le budget de 30 min), runner `vitest-gt`. Une première mesure avec le
runner publié rendait 0 tué sur 754 (tout test sous un `describe` sauté,
`testsCompleted: 0`) : non exploitable, d'où le correctif du runner. Avec lui,
`lib/rank.ts` passe de 7/10 à 9/10 et `components/tcn/ErrorScreen.tsx` de 0/11
à 10/11 (load 20). Durées indicatives seulement : charge hors seuil, une
exécution par bras et par concurrence.

| Mesure | load au départ → à la fin | Durée murale | Tués / survivants / timeouts | Statut |
| --- | --- | --- | --- | --- |
| Avant, concurrence 7 | 1,30 → 15,80 | 1186 s | 310 / 114 / 325 | non retenue (charge) |
| Après, concurrence 7 | 9,04 → 16,29 | 909 s | 407 / 187 / 155 | non retenue (charge) |
| Avant, concurrence 3 | 9,04 → 4,14 | 826 s | 451 / 298 / 0 | non retenue (charge) |
| Après, concurrence 3 | 3,59 → 7,26 | 913 s | 447 / 283 / 19 | non retenue (charge) |

À concurrence 7 (défaut), la charge que Stryker s'impose fait exploser les
timeouts, et deux bras n'ont plus le même ensemble de mutants tranchés : la
comparaison se fait à concurrence 3. Verdict identique sur les 730 mutants
tranchés par les deux bras à concurrence 3 ; les 4 mutants tués avant et en
timeout après (ligne 735) sont tués par la relance ciblée,
`npx stryker run --force --concurrency 3 --timeoutMS 60000 --mutate "components/results/RaceFinishers.tsx:735-735"` sur le fichier consolidé
(8 tués sur 8, 17 s). À ensemble égal : 451/749 → 451/749. Couverture du
fichier seul : 135/137 lignes avant et après, mêmes lignes manquées. Détail du
lot : `2026-10-20-test-consolidation-inventaire.md`.

**Re-gate après rebase** (21/10) : `main` a modifié `RaceFinishers.tsx`
(filtre par sexe, #1702/#1730), donc la preuve ci-dessus portait sur l'ancien
source. Relancée sur le source rebasé, `--force --concurrency 3 --mutate
"components/results/RaceFinishers.tsx"`, avant = fichier de test de `main`,
après = fichier consolidé rebasé. Durées indicatives seulement (une exécution
par bras).

| Mesure | load au départ | Durée murale | Tués / survivants / timeouts / sans couverture | Statut |
| --- | --- | --- | --- | --- |
| Avant (149 tests) | 4,39 | 906 s | 511 / 307 / 0 / 6 | non retenue (charge) |
| Après (128 tests) | 0,90 | 842 s | 511 / 307 / 0 / 6 | indicative (une exécution) |

824 mutants, clé sur l'étendue complète : même ensemble, verdict identique
mutant par mutant, aucun timeout, donc aucune relance. 511/818 → 511/818
(62,5 %). Couverture du fichier seul identique : 98,6 % des lignes, 98,83 %
des instructions, 96,59 % des branches, mêmes lignes manquées (576-583).
Porte tenue.

## Consolidation, lot 4 (`AppNav.test.tsx`)

Stryker sur `components/layout/AppNav.tsx` (794 mutants au rapport, fichier
entier), runner `vitest-gt`, `--force --concurrency 3`. L'avant dépasse le
budget de 30 min (2016 s) ; la restriction aux lignes touchées aurait couvert
presque tout le fichier. Durées indicatives seulement : charge hors seuil, une
exécution par bras.

| Mesure | load au départ → à la fin | Durée murale | Tués / survivants / timeouts | Statut |
| --- | --- | --- | --- | --- |
| Avant | 2,17 → 3,53 | 2016 s | 385 / 369 / 29 | non retenue (charge) |
| Avant, relance des timeouts (lignes 488 à 547, `--timeoutMS 60000`) | 2,09 → 3,86 | 126 s | 29 timeouts : 6 / 23 / 0 | non retenue (charge) |
| Après, premier brouillon (écarté) | 2,37 → 4,86 | 1610 s | 414 / 369 / 0 | non retenue (charge) |
| Après | 2,93 → 4,41 | 1586 s | 391 / 392 / 0 | non retenue (charge) |

Mutants comparés par leur étendue complète (début et fin, mutateur,
remplacement) : une clé sur le seul début confond 20 mutants d'`AppNav.tsx` et
en perdait 10. Avant, timeouts tranchés par la relance : 391/783. Après : 391/783, verdict
identique mutant par mutant (11 sans couverture exclus des deux côtés). Le
premier brouillon gagnait 23 mutants (lignes 116 à 379) par un faux positif :
le test de focus fusionné échoue lancé seul sur le code intact, et Stryker ne
rejoue que les tests couvrant le mutant. Remis à part, l'après a été remesuré.
Couverture du fichier seul : 116/120 lignes avant et après, mêmes lignes
manquées. Détail du lot : `2026-10-20-test-consolidation-inventaire.md`.

## Avant / après

Mesures du 21/10, fin d'epic, `FULL_SUITE=1`, protocole du sondage du 2026-08-20 (seuil `load average` 1 min < 2,0). Le load d'une exécution vient en grande partie de `-n 4` ou des workers vitest eux-mêmes : une exécution lancée juste après une autre démarre donc au-dessus du seuil. Les exécutions retenues sont celles lancées machine au repos (load < 1,1, aucun `pytest`, `vitest`, `next dev` ni Stryker étranger).

La colonne « 20/10 (avant) » reprend les chiffres que le plan
(`docs/superpowers/plans/2026-10-20-test-process.md`, tâche finale, étape 1)
cite au lancement de l'epic ; ni la commande ni le commit mesuré n'y sont
consignés, et ils précèdent la base de la branche (voir sous le tableau).

| Mesure | 20/10 (avant) | 21/10 (après) | load au départ | Statut |
| --- | --- | --- | --- | --- |
| Backend unitaire, tests | 6 823 | 7 125 passés, 19 ignorés | | |
| Backend unitaire, durée | | **26,4 s** (puis 25,9 s et 31,2 s) | 1,09 (puis 2,23 et 2,95) | retenue (1re) ; les deux autres non retenues (charge) |
| Backend `--migrations`, tests | | 7 199 passés, 19 ignorés | | |
| Backend `--migrations`, durée | | **84,5 s** (avant : 90,7 s, 84,8 s, 85,0 s) | 0,97 (avant : 3,52, 2,83, 3,34) | retenue (au repos) ; trois premières non retenues (charge) |
| Backend, couverture | 98 % | 98 % (19 442 instructions, 422 manquées, `--migrations`) | | |
| Frontend `npm test`, tests | 3 224 | 3 403 passés, 2 ignorés (305 fichiers) | | |
| Frontend `npm test`, durée | | **69,6 s** (avant : 72,4 s) | 0,88 (avant : 3,13) | retenue (au repos) ; la première non retenue (charge) |
| Frontend, couverture | 92,37 % des lignes | 92,07 % des lignes (91,33 % instructions, 89,55 % branches, 85,7 % fonctions) | | |

L'écart avec la colonne du 20/10 ne vient pas de `main` pendant l'epic : la branche n'avait jamais fusionné `main`, et ces chiffres précèdent sa base (`22e24042`). Rapporté à cette base (comptes `--collect-only -q -m "not integration"` relevés le 21/10 sur les deux arbres), l'écart est celui de l'epic seule. Backend : 7 228 tests collectés à la base (7 209 passés, 19 ignorés), moins 11 (lots 1 et 2), plus 1 (`test_db_session_fixture.py`, tâche 6), soit 7 218 avec `--migrations` (7 199 passés) ; sans `--migrations`, les 74 tests Alembic désélectionnés en local laissent 7 125 passés. Frontend : 3 403 passés, soit 3 445 à la base moins 42 (lots 3 et 4) ; la base est déduite et non relancée, les deux fichiers des lots étant les seuls fichiers de test frontend que la branche touche. La couverture frontend recule de 0,30 point de lignes par rapport au 20/10, sans que la consolidation y soit pour quelque chose (couverture par fichier identique avant et après chaque lot).

Après rebasage sur `origin/main` (`d9b0ba6a`, 21/10), les comptes changent encore, du fait de `main` : backend 7 245 tests collectés sans `--migrations`, 7 319 avec (`--collect-only -q -m "not integration"`) ; frontend 3 268 entrées de `npx vitest list`, qui affiche un `it.each` une seule fois (son gabarit `%s`) et ne se compare donc pas au total d'exécution ci-dessus. Le total d'exécution frontend attend la suite complète de fin de branche.

Durées absolues du 20/10 : le sondage n'en conserve aucune sous protocole pour la suite complète (la seule valeur au repos, ~58 s pour 7 135 tests en `-n 0`, date du sondage du 2026-08-20 ; la suite fait 95,0 s en `-n 0` à load 1,73 après la fixture transactionnelle). En `-n 4` (addopts), la suite unitaire backend tient donc en 26,4 s au repos. Le gain de la tâche 6 (fixture transactionnelle) reste jugé sur la part de `create_all` (35,5 % puis 3,8 %), et l'A/B en bras entrelacés de la durée murale reste à faire machine libre ; les essais vitest de la tâche 7 (`isolate: false`, happy-dom) ne sont pas rejoués ici et attendent eux aussi une mesure au repos.

Couverture frontend sous v8 (`npx vitest run --coverage --coverage.provider=v8`) : 305 fichiers, 3 403 tests, aucun rouge (le flaky de #1708 ne s'est pas manifesté, load 6 à 11 en fin d'exécution).

### Consolidation

| Lot | Fichier | Tests avant → après | Retirés | Mutation | Couverture du fichier |
| --- | --- | --- | --- | --- | --- |
| 1 | `test_raceresult.py` | 381 → 377 | 4 | 1613/2074 → 1613/2074 | 95,6 % → 95,6 % |
| 2 | `test_import_service.py` | 169 → 162 | 7 | 225/389 → 225/389 | 96,2 % → 96,2 % |
| 3 | `RaceFinishers.test.tsx` | 134 → 113 (149 → 128 après rebase) | 21 | 451/749 → 451/749 (après rebase : 511/818 → 511/818) | 98,5 % → 98,5 % (98,6 % après rebase) |
| 4 | `AppNav.test.tsx` | 146 → 125 | 21 | 391/783 → 391/783 | 96,7 % → 96,7 % |
| Total | | | **53** sur ~10,4 k (10 412 tests au 21/10) | inchangée | inchangée |

Source : `2026-10-20-test-consolidation-inventaire.md`. Arrêt de la consolidation par décision du contrôleur : 4 lots à environ 1 à 1,5 h de calcul chacun ont retiré 53 tests sur environ 10,4 k sans changement de score, donc les 149 lots restants de l'inventaire servent à l'occasion, sans campagne.
