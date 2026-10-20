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

Cause probable (non prouvée test par test) : ces tests dépendent du temps réel (debounce de 300 ms de `useDebounce` dans `TeammatesDialog`, enchaînements `userEvent` dans des dialogues Radix) et vivent sous le budget de 1 s de `findBy*`. Les rouges du 20/10 sont donc des délais dépassés par manque de CPU, pas une régression de code ni une horloge. La seule parade serait d'allonger les délais, ce que l'épic interdit (pas de hausse de `testTimeout`, pas de retries). Aucun correctif n'est appliqué : un test vert dans toutes les conditions reproductibles ne justifie pas d'en inventer un.

Limite : la suite complète sous couverture n'a pas été rejouée ici. Si les trois rouges reviennent à charge modérée, rouvrir avec la sortie complète de l'exécution fautive.
