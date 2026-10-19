# Sondage : couverture de `rank_gender` et du sexe athlète par fournisseur (#1644)

Mesuré le 19/10/2026 sur la base de production (Azure PostgreSQL), en lecture
seule (`SET TRANSACTION READ ONLY`). Population : participations `finisher`,
fournisseur de la source active de l'épreuve.

## Remplissage par fournisseur

| Fournisseur | Finishers | Sexe athlète connu | `rank_gender` rempli | Relais | Épreuves |
| --- | ---: | ---: | ---: | ---: | ---: |
| breizhchrono | 46 938 | 94,1 % | 16,2 % | 12,8 % | 136 |
| klikego | 32 574 | 95,3 % | 94,8 % | 9,2 % | 216 |
| competitor | 23 665 | 96,8 % | 95,5 % | 0 % | 10 |
| wiclax | 17 095 | 96,1 % | 100 % | 12,1 % | 135 |
| raceresult | 11 408 | 89,2 % | 44,8 % | 11,3 % | 99 |
| prolivesport | 9 741 | 93,2 % | 100 % | 15,7 % | 25 |
| sportinnovation | 5 617 | 99,3 % | 12,4 % | 1,6 % | 17 |
| timepulse | 4 811 | 97,6 % | 100 % | 5,1 % | 50 |
| chronoweb | 3 811 | 99,5 % | 0 % | 0 % | 11 |
| oktime | 1 064 | 98,2 % | 100 % | 5,0 % | 8 |
| nextrun | 591 | 100 % | 100 % | 59,1 % | 6 |
| runnerbreizh | 412 | 100 % | 0 % | 0 % | 2 |
| chronoplace | 260 | 96,9 % | 0 % | 8,1 % | 3 |

Membres TCN (9 libellés de club `is_tcn`) : sexe connu à 94 à 100 % selon le
fournisseur ; `rank_gender` rempli à 94 à 100 % sauf raceresult (11 %),
sportinnovation (0 %) et chronoplace (0 %).

Épreuves : 734, dont **212 sans aucun `rank_gender`** et 290 avec au moins un
finisher de sexe inconnu. Challenges : 67 résultats finishers, `rank_gender`
rempli à 100 %.

## Le `rank_gender` officiel diverge de la position recalculée

Position recalculée = rang du finisher parmi les finishers non relais de même
sexe de l'épreuve, ordonnés par `rank_overall`. Accord avec `rank_gender` :

| Fournisseur | Lignes comparées | Accord | `rank_gender` > recalculé | `rank_gender` < recalculé |
| --- | ---: | ---: | ---: | ---: |
| klikego | 28 233 | 72,2 % | 23,3 % | 4,5 % |
| competitor | 22 593 | 43,8 % | 25,8 % | 30,4 % |
| wiclax | 14 922 | 70,7 % | 22,1 % | 7,2 % |
| prolivesport | 8 209 | 77,6 % | 20,5 % | 1,8 % |
| breizhchrono | 7 539 | 31,6 % | 39,6 % | 28,9 % |
| timepulse | 4 566 | 86,9 % | 10,7 % | 2,4 % |
| raceresult | 4 305 | 92,3 % | 6,3 % | 1,4 % |
| oktime | 1 011 | 100 % | 0 % | 0 % |
| sportinnovation | 696 | 15,9 % | 62,5 % | 21,6 % |
| nextrun | 242 | 100 % | 0 % | 0 % |

Exemple klikego, épreuve 1123, femmes par `rank_overall` : `rank_gender`
1, 2, 3, 4, 5, **7**, 8, 9. Une concurrente manque en base ou porte le mauvais
sexe : le rang officiel reste juste, la liste filtrée a un trou.

## Conséquences pour l'epic #1643

- Le sexe athlète est assez rempli pour filtrer (≥ 89 % partout).
- Le repli sur une position recalculée n'est pas marginal : 29 % des épreuves.
- Officiel et recalculé ne se mélangent pas dans une même liste. Décision
  utilisateur (19/10/2026) : **rang officiel quand l'épreuve le fournit**, trous
  compris ; position recalculée pour toute l'épreuve sinon, signalée comme telle.

Scripts : requêtes SQL agrégées sur `participations`, `athletes`,
`course_sources`, `challenge_results` ; non versionnées (sondage ponctuel).
