# RaceResult

RaceResult couvre de même trois façades d'un même produit (`raceresult.com`,
`espace-competition.com`, `chronoconsult.fr`, cf. `RaceResultProvider._HOSTS`),
toutes servies par la même API JSON publique — sans Playwright, et toutes
joignables via l'apex `my.raceresult.com` (aucune résolution de shard).
Particularités du moteur : les listes retenues sont celles dont `Mode` n'est pas
`"hidden"` dans `config["TabConfig"]["Lists"]` (qui porte le contest
explicitement) — critère **nécessaire mais non suffisant** : sur 406211 les
listes non-`hidden` sont des listes d'affichage et le seul vrai classement est
`hidden`. L'élargissement aux listes `hidden` est **réalisé** (#60) : elles ne créent ni
participant ni contest, elles **enrichissent** par **dossard** les participants
établis par les listes publiées (splits, scalaires vides). Coût : une requête
`list` par liste `hidden`. Le verrou C (410891, rang `(2)` sans point) reste
ouvert : `_RE_DUREE` rejette bien la cellule suffixée d'un finisher, mais un
non-finisher (DNF/DNS/DSQ), à qui RaceResult n'appose pas le suffixe, peut laisser
fuiter une durée intermédiaire nue comme split (élargissement renvoyé à un ticket
dédié). Design : `2026-07-23-raceresult-listes-hidden-design.md`.
Plusieurs listes peuvent couvrir un même contest et doivent être fusionnées.
La qualification de `Course` vient du **contest explicite** de `TabConfig.Lists` ;
le libellé de groupe de niveau 0 n'est consulté qu'en `Contest="0"`, et
seulement si tous ces libellés recoupent `contests` (ils sont sinon un axe
d'affichage : catégorie, sélecteur de split). Le `Name` de liste n'est **jamais**
un qualifiant — c'est un nom interne à pipe, et l'employer dupliquait
silencieusement des participations (cf. §3 du sondage).
La date d'épreuve n'existe que dans le JSON-LD schema.org de la page
`/{eventId}/results`.
Vérité d'API (15 épreuves au panel, 3 façades ; mesures détaillées sur 12/14/17) :
`docs/superpowers/specs/2026-07-19-raceresult-api-sondage.md` — elle prime sur le
design et sur le plan. Ne pas revenir à la route `/{id}/RRPublish/data/…` (alias
hérité, 404 sur les épreuves récentes) ni au filtre `Live` (qui vide certaines
épreuves) : les deux ont des tests de non-régression dédiés.
Design : `docs/superpowers/specs/2026-07-19-raceresult-scraper-design.md`.
