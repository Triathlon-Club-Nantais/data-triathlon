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

**Sous-URL de contest (#989).** Chaque course est stockée sous
`https://my.raceresult.com/<event>/results?contest=N` (`_sub_source_url`), en
fan-out comme en `--single-heat` : l'URL soumise (façade comprise) n'est jamais
posée sur les lignes d'un contest explicite, sans quoi elle devenait la source
passive de tous les contests à la fois. Le scraper relit ce sélecteur
(`target_contest`) : une sous-URL ne scrape que son contest, ses listes `hidden`
et les lignes `Contest="0"` qui s'y rattachent. `rescrape-db` fait donc un
scrape par contest, et non plus N scrapes de l'épreuve entière. `?contest=0` ne
cible rien et vaut l'épreuve entière ; un contest absent des listes publiées
lève. `GET /scrape/detect` masque la bascule « import unique » sur une telle
URL, comme sur une URL Breizh Chrono déjà ciblée.

**Épreuve mixte (#977).** Quand une épreuve publie à la fois des listes à
contest explicite et des listes `Contest="0"`, le repli « tout ou rien » de
`_groupes_zero_fiables` ne vaut plus : le qualifiant vide y créait une `Course`
au nom d'épreuve nu où chaque participant était importé une seconde fois
(Supertri 363395 : 972 lignes en plus ; Côte de Jade 342814 : 205, soit la somme
des trois contests), et chaque dossard devenu double rendait l'enrichissement
`hidden` « ambigu ». Hors groupement corroboré, une ligne `Contest="0"` rejoint
désormais son contest par sa cellule `CONTEST.NAME` et s'y fusionne par
`_prefer` ; sans contest résoluble, elle est ignorée (un avertissement par
liste). Une liste `Contest="0"` sans temps d'arrivée ni rang général (les
classements de segment Strava de 363395) est écartée avant fusion. Une épreuve
publiée entièrement en `Contest="0"` (409130, 380823) garde le repli.

**Colonnes de rang (#984).** `_role` reconnaît, avant la règle du suffixe `.p` :
`RANK1` (`RANK1`, `RANK1p`, `RANK1.p`) et `ClassementGen` comme rang général, et
`ClassementMF` / `ClassementMFJ` (avec ou sans `.p`) comme **rang de sexe**
(`rank_gender`). Seul `RANK1` est retenu : sur 342814 et 386706, `RANK2` et
`RANK3` sont les rangs de sexe et de catégorie collés à leur cellule, et
`RANK1` court de 1 à N sur le contest, sexes mêlés (mesuré sur 386706). Un
`<split>.AGEGROUP.P` / `.OVERALL.P` / `.GENDER.P` est un rang de segment, testé
avant la règle `agegroup` qui en faisait la catégorie selon l'ordre des colonnes.
Quand deux listes d'un même contest portent chacune un rang (404650 : rang
général en « Scratch », rang de sexe en « MF »), la fusion comble les rangs
vides de la ligne retenue avec ceux de l'autre (`_completer_rangs`), sauf pour
un non-finisher ou deux identités distinctes. Mesuré sur 404650 : `rank_gender`
passe de 0 à 1 065 lignes sur 1 221.

**Nom virgulé (#906).** `LFNAME` sérialise « NOM, Prénom » (toute casse :
`JUMEAUX, ADRIEN`, `Courjon, Rose`). `utils.split_athlete_name` coupe désormais
sur la **première** virgule, nom à gauche et prénom à droite, pour tous les
fournisseurs ; la garde `&` des noms d'équipe (#63) passe avant. Les fiches déjà
en base (environ 6 400, dont environ 2 950 doublons exacts) ne sont pas
reprises par ce correctif.

**Temps à dixièmes (#904).** Supertri 363395 publie son temps d'arrivée sous
`TIME1` étiqueté « Temps », et toutes ses durées avec un dixième à la virgule
(`02:35:01,7`). `TIME1` n'avait aucun rôle (il finissait en segment « Temps »)
et la garde du rôle `temps` aurait de toute façon rejeté la fraction : les
1 043 finishers de l'épreuve sortaient sans `total_time`, donc en DNF. Une
colonne `TIMEn` devient le temps d'arrivée **seulement** si son libellé est
« Temps », « Temps total », « Temps final » ou « Time » : `TIMEn` désigne un
résultat quelconque (`TIME2` « Natation » sur 342814, `TIME19` « Tours » sur
409130). La fraction est tronquée à la seconde (`_sans_fraction`), sur le temps
d'arrivée comme sur les segments ; `normalize_time` et `_RE_DUREE` restent
inchangés. Les courses déjà en base (181 à 186) sont à re-scraper.
