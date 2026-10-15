# Sportinnovation : pièges mesurés

Module : `backend/app/scrapers/sportinnovation.py`. Formes d'URL et routes
d'API : docstring du module.

## Courses retirées par le fournisseur (#1350, mesuré le 15/10/2026)

- Une course de l'API (`results.sportinnovation.fr/race/{slug}`) peut
  disparaître sans que son événement disparaisse. Carnac 2025
  (`gqjk02-triathlon-de-carnac-2025`) répond toujours sur `/api/events/{slug}`,
  mais `/api/events/{slug}/races` rend une liste vide : ses courses `zmhc-*`
  ont été retirées.
- Une course retirée répond **404 avec une page HTML**, plus avec l'objet
  `{"error": …}` d'avant. Le scraper lève alors « Course Sportinnovation
  introuvable » au lieu d'un `JSONDecodeError`.
- Conséquence pour le test d'intégration de la forme `/race/{slug}` : il pointe
  sur l'édition la plus récente (Carnac 2026, `refl6a-triathlon-m`) et devra
  être repointé si elle disparaît à son tour.

## Pare-feu après une rafale

Juste après une passe complète des tests d'intégration (splits récupérés par
20 requêtes parallèles), `sportinnovation.fr/api/*` a répondu **403 « Access
forbidden! »** en HTML pendant quelques minutes, puis de nouveau normalement.
Un 403 isolé sur cette API se re-sonde plus tard avant d'être pris pour une
dérive.
