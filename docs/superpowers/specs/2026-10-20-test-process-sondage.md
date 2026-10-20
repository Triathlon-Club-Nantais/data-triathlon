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
