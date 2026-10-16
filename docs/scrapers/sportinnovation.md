# Sportinnovation : pièges mesurés

Module : `backend/app/scrapers/sportinnovation.py`. Formes d'URL et routes
d'API : docstring du module.

## Courses retirées par le fournisseur (#1350, mesuré le 15/10/2026)

- Une course de l'API (`results.sportinnovation.fr/race/{slug}`) peut
  disparaître sans que son événement disparaisse. Carnac 2025
  (`gqjk02-triathlon-de-carnac-2025`) répond toujours sur `/api/events/{slug}`,
  mais `/api/events/{slug}/races` rend une liste vide : ses courses `zmhc-*`
  ont été retirées.
- Une course retirée répond **404 avec une page HTML**, et non plus avec l'objet
  `{"error": …}` d'avant. Le scraper lève alors « Course Sportinnovation
  introuvable » au lieu d'un `JSONDecodeError`.
- Conséquence pour le test d'intégration de la forme `/race/{slug}` et pour
  l'entrée correspondante du seed démo (`backend/scripts/seed_demo.py`, #1431) :
  tous deux pointent sur l'édition la plus récente (Carnac 2026,
  `refl6a-triathlon-m`) et devront être repointés ensemble si elle disparaît à
  son tour.

## Schéma FFA à passages inline (#1575, mesuré le 16/10/2026)

BayMan 2026, Triathlon L (`xu94e7-triathlon-l`, course 7690, 971 lignes).
`/api/races/{slug}/results` ne porte ni `id` ni `slug` d'athlète (seulement
`runnerSlug`) : aucune requête `/api/results/{ref}` n'est faite, et c'est ce qui
laissait les splits vides. Ils sont pourtant dans la liste elle-même :

- `intermediates` : `[{controlPointLabel, distanceFromStart, realTimeFfa}]`,
  temps **cumulés** depuis le départ. Libellés : `Tps Nat`, `Transition 1`,
  `Tps Velo`, `Transition 2`, `FINISH` (renommé « Tps CAP » à l'affichage par
  `intermediatePointNames` de `/api/races/{slug}`).
- Un segment est l'écart avec le passage du segment précédent ; il reste vide si
  ce passage manque (13 lignes s'arrêtent après le vélo, 5 sautent vélo et T2).
  Un point répété (5 « Transition 2 » doublées, une seconde d'écart au plus)
  garde son passage le plus tôt. Liste vide sur les DNS.
- Mesuré sur un triathlon seulement : un duathlon de ce schéma (libellés
  `IN1`/`OUT1`…, cumulés ou non) est à re-sonder avant de s'y fier.
- Rangs : `officialGeneralRank`, `officialSexRank`, `officialCategoryRank`
  (et leurs `real*`), et non `generalRank`/`sexRank`/`categoryRank`.
- Le `realTimeFfa` de `FINISH` peut différer de `officialTimeFfa` de
  plusieurs minutes (6 min 43 s sur le dossard 761) : le total reste
  l'officiel, la somme des splits suit le temps réel.
- Source fautive connue : le dossard 338 n'a pas de passage vélo et un
  « Transition 1 » à 04:47:11, d'où une T1 de 4 h importée telle quelle.

## Pare-feu après une rafale

Juste après une passe complète des tests d'intégration (splits récupérés par
20 requêtes parallèles), `sportinnovation.fr/api/*` a répondu **403 « Access
forbidden! »** en HTML pendant quelques minutes, puis de nouveau normalement.
Un 403 isolé sur cette API se re-sonde plus tard avant d'être pris pour une
dérive.
