# nextrun.fr

**nextrun.fr** (#1224) sert ses pages de résultats en SvelteKit, rendues côté
serveur à partir de deux routes JSON publiques, sans authentification ;
`robots.txt` autorise tout. Le scraper (`backend/app/scrapers/nextrun.py`) lit
directement ces routes, sans HTML :

- `GET /api/events/{épreuve}/editions/{édition}/results` : nom, ville, dates et
  liste des courses (`race_id`, `name`, `date`, `results_published`) ;
- `GET /api/races/{race_id}/results/rows?page=N&page_size=200` : une ligne par
  personne.

URL acceptée : `https://nextrun.fr/events/{épreuve}/editions/{édition}/results`
(le segment `results` est facultatif). Une URL sans `editions/{édition}` est
refusée avec un message qui donne la forme attendue. Toute l'édition est
importée en un seul passage (`ModuleProvider`, pas de fan-out) ; chaque course
devient une épreuve « {événement} - {course} ».

## Pièges mesurés (Défi-Swimrun de Lancieux 2026, 06-07/10/2026)

- **Pagination** : 50 lignes par défaut ; `page_size` n'accepte que 20, 50, 100
  ou 200 (422 « n'est pas dans [20, 50, 100, 200] » au-delà). Le scraper demande
  200 et suit `page` jusqu'au `total` annoncé ; un garde de 50 pages lève plutôt
  que de rendre un classement tronqué.
- **Date en UTC** : `start_date` vaut `2026-08-21T22:00:00Z` pour une épreuve du
  22/08. La date d'une course se lit dans son `date`, convertie en heure de Paris.
- **Course non publiée** (`results_published: false`, « SwimRun XS Kids ») :
  ignorée, aucune requête.
- **« Licence Expérience »** dans `club` est un type de licence, pas un club
  (177 lignes sur 306 mesurées) : le club est laissé vide.
- **`is_orphan: true`** (4 lignes sur 306) : ligne de chrono sans club ni
  catégorie (`category_rank` nul), mais nommée, datée et classée. Importée telle
  quelle.
- `official_time_ms` porte le temps ; `real_time_ms`, `laps` et `distance_m` sont
  nuls partout. Aucun split publié.
- `status` ne vaut que `finisher` sur Lancieux ; une autre valeur passe par
  `derive_status_from_label`, et un DNF/DNS/DSQ perd temps et rangs.

## Duos : une ligne par personne

La source publie **chaque équipier sur sa ligne**, avec son propre dossard
(336 et 335 pour « Power natation »), son club, son sexe, sa catégorie, son temps
(à la seconde près : 37:54 et 37:55) et ses rangs ; `scratch_rank` compte des
personnes, les deux équipiers ont deux rangs consécutifs. Le nom d'équipe est
dans `team_name`.

**Choix : on importe une ligne par personne**, comme runnerbreizh, seul autre
fournisseur qui publie un duo équipier par équipier. Les lignes sont marquées
relais par le nom de course (« Duo », `heat_is_relay`).

Pourquoi pas une ligne par équipe composée par #997 (liaison
`participation_teammates`, alimentée à l'import par le découpage de #895) :

- il faudrait **inventer** un résultat d'équipe que la source ne publie pas :
  quel temps (les deux diffèrent), quel dossard (deux), quel sexe et quelle
  catégorie (ceux de chaque personne), quels rangs (à renuméroter, puisque
  `scratch_rank` compte des personnes et laisserait un trou sur deux) ;
- la raison qui a fait rejeter « une participation par équipier » dans #997, la
  contrainte d'unicité `(course_id, bib_number)` sur un dossard partagé, ne tient
  pas ici : chaque équipier a son dossard ;
- les rangs restent ceux de la source, sans doublon ni trou : la qualité de
  l'épreuve (`quality._rank_anomalies`) n'est pas dégradée, contrairement à
  runnerbreizh dont les équipiers partagent un rang ;
- le résultat apparaît sur la fiche de chaque équipier sans geste
  d'attribution, avec son club à lui : un adhérent en duo avec un non-adhérent
  est reconnu par son propre club.

Conséquence assumée : un podium de duo du TCN où les deux équipiers sont
adhérents compte deux lignes dans les podiums du club, comme pour runnerbreizh.
`team_name` est conservé dans `raw_data`, pas dans `Participation.team_name`
(réservé à la saisie manuelle et aux relais composés).

Sondage initial : `docs/superpowers/specs/2026-10-06-nextrun-altichrono-sondage.md`.
Base légale : `docs/superpowers/specs/2026-10-01-base-legale-decision.md` (#332).
