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
