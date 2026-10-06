# Sondage altichrono.fr et nextrun.fr (#1208)

Mesuré le 06/10/2026, hors connexion, par le client HTTP gardé de l'application.

## altichrono.fr : un déploiement Wiclax de plus

`https://altichrono.fr/resultats/2026_bouchet` est une page WordPress qui
n'embarque qu'une iframe G-Live :
`/wp-content/glive/g-live.html?f=/wp-content/glive-results/2026_bouchet/TRIATHLON%20DU%20LAC%20DU%20BOUCHET.clax`.
Même montage que `chronowest.fr` (#35) : le scraper Wiclax suit l'iframe et lit
le `.clax`. Il suffit donc d'ajouter le host à `WiclaxProvider._HOSTS`, aucun
fournisseur à écrire. Import vérifié de bout en bout : 13 parcours, dont 6
d'équipes.

Les deux swimruns n'ont aucun mot d'équipe dans leur parcours (« SWIMRUN S »,
« SWIMRUN M ») mais ne classent que des catégories `EQX`, `EQF`, `EQM` : le
scraper Wiclax type désormais relais un parcours à majorité stricte de ces
catégories, la règle de TimePulse.

## nextrun.fr : une API JSON publique, scraper à écrire après décision

- `robots.txt` : `User-agent: *` et `Disallow:` vide, tout est autorisé.
- La page `/events/{event}/editions/{édition}/results` est rendue côté serveur
  (SvelteKit) à partir de deux routes JSON publiques, sans authentification :
  - `GET /api/events/{event}/editions/{édition}/results` : nom, ville, dates et
    la liste des courses (`race_id`, `name`, `date`, `results_published`,
    `finisher_count`) ;
  - `GET /api/races/{race_id}/results/rows` : une ligne **par personne**,
    `bib_number`, `first_name`, `last_name`, `club`, `team_name`, `gender`
    (`male`/`female`), `category`, `status` (`finisher`…), `official_time_ms`,
    `real_time_ms` (nul sur Lancieux), `scratch_rank`, `gender_rank`,
    `category_rank`, `is_orphan`.
- Défi-Swimrun de Lancieux 2026 : 7 courses, dont une non publiée (« Kids »).
  Les duos publient **chaque équipier** sur sa ligne, avec le club de la
  personne et le nom de l'équipe dans `team_name` ; le `scratch_rank` compte des
  personnes, les deux équipiers d'un duo ont deux rangs consécutifs au même
  temps. Le nom de course porte « Duo » ou « Solo » : `heat_is_relay` le lit.
- Aucun split publié sur cet événement.

Ce que l'écriture devra trancher : une ligne par personne ou une par équipe sur
les duos (le premier rend le résultat visible sur le profil de chaque équipier
sans geste d'attribution, #997), et la base légale d'un nouveau fournisseur
(#332), qui précède tout scraper.
