# runnerbreizh.fr

`runnerbreizh.fr` est du **HTML statique paginé** : 50 lignes par page,
`&page=N`, arrêt sur la première page dont `table.tableau-courses` n'a plus que
son en-tête. Ne **jamais** borner la pagination sur le total annoncé en colonne
« Classement » : en relais il compte des **équipes** (31) et non des lignes (62),
la boucle s'arrêterait à la moitié de l'épreuve.

Ce total sert en revanche de **garde de complétude après coup**
(`_require_complete_ranking`) — vérifier n'est pas borner. Le critère d'arrêt seul
confond la fin du classement avec une page intermédiaire servie vide : les rangs
lus restent contigus (1..150), `quality.analyze` ne voit alors aucune anomalie et
l'épreuve tronquée sort `is_reliable=true`. La garde ne juge donc que si la
dernière page lue était **pleine** (une page incomplète est la fin publiée) et
compare un **plancher**, jamais une égalité — sans quoi le décompte en équipes du
relais refuserait toute épreuve par équipes. Elle compte les **lignes vues**, pas
les résultats retenus : une ligne hors format est un autre sujet, déjà
journalisé. Même principe pour le plafond de pagination (`_MAX_PAGES`) : l'avoir
atteint signifie que l'invariant d'arrêt est faux, donc on **lève** au lieu de
rendre des lignes vraisemblablement dupliquées. Dans les deux cas un import
refusé se rejoue (`rescrape-db --urls-from -`), une épreuve tronquée et marquée
fiable ne se rattrape pas.

L'URL d'entrée est **canonicalisée** (`runnerbreizh.canonical_url`) : on ne garde
que `CourseFichierGpsNom` et on repart de la page 1. Ce n'est pas cosmétique —
8 des 10 liens du Sheet portent `&page=2` ou `&page=3`, et `&Sexe=F` renvoie un
**sous-ensemble** : partir de l'URL telle quelle amputerait silencieusement
l'import de ses premières pages, donc de ses meilleurs classés. La
canonicalisation est faite par **allowlist** (reconstruction depuis le seul
paramètre d'épreuve), pas par soustraction des vues connues. Portée exacte : elle
fixe le `source_url` des `ScrapedResult`, **pas** la clé du cache TTL —
`Course.source_url` reçoit l'URL brute passée par `import_service`, donc deux
graphies d'une même épreuve dans le Sheet la font re-scraper. Vérifié en base :
une seule `Course`, aucune participation dupliquée.

Trois manques structurants, tous assumés. **Aucun dossard** : rien à faire côté
scraper, le repli anti-doublon par athlète de `import_service` (commit `b49e295`)
est générique. **Aucun club** — ni dans le classement, ni sur la fiche coureur :
`Participation.club` reste `NULL`, donc ces participations sont **hors du
périmètre `scope=club`** (dashboard, page club, stats). C'est arbitré, pas un
oubli ; et sans danger, `athlete_repository.resolve` ne mettant à jour
`Athlete.club` que si un club est fourni. **Aucune date de naissance** : seule la
catégorie situe l'âge, d'où le genre lu sur son suffixe (`S3M` → M) — sauf
catégorie d'équipe (`M+F`), qui décrit la composition du duo et non la personne
de la ligne.

Les 8 colonnes sont **figées quelle que soit la discipline** et leurs libellés
mentent : en duathlon « 1ère épreuve » est une course à pied, en aquathlon la
cellule « Vélo » reste affichée mais vide. Elles se lisent donc **par position**
(2/3/5 → slots `swim`/`bike`/`run`), `services/mapping.build_splits` les
ré-étiquetant selon `event_type` — jamais par libellé d'en-tête, contrairement à
T2Area. Les transitions ne sont pas publiées (pas de T1/T2). Corollaire côté
gabarit : un sport dont un slot positionnel n'a pas de discipline lisible
(`swim_time` en bike & run, `bike_time` en swimrun) reçoit une clé
**positionnelle** — `segment1`, `segment2`. Omettre ce slot du gabarit, comme
avant, jetait silencieusement le temps qui s'y trouvait ; lui donner un nom de
sport mentirait. Métadonnées d'épreuve dans le `<title>`, seul porteur de la date
en format français ; le nom y est nettoyé de son suffixe de distances
(`Triathlon de Quiberon M`, pas `… M (1.5/38/10)`) faute de quoi l'extraction de
commune de la carte échoue. La commune, elle, **est** dans le titre et vaut mieux
que celle déduite du nom (`Pléneuf-Val-André` contre `Val-André`) : faute de champ
ville dans `ScrapedResult`, elle est conservée en `raw_data["city"]` — la brancher
sur le géocodage changerait un contrat partagé par tous les fournisseurs.

Le rang de catégorie ne se lit **pas** au premier enfant `<b>` de la cellule : sur
une ligne féminine, le site enveloppe toute la cellule dans un `<span>` de couleur
et supprime le `<b>` (`<span>29/SEF</span>`). Rang et qualifiant se lisent donc
tous deux depuis le **texte** ; l'oublier perdait `rank_category` pour toutes les
coureuses, et donnait deux rangs différents aux deux équipiers d'un même duo
mixte.

Deux profondeurs d'URL refusées, avec un message qui nomme la forme attendue :
la **fiche coureur** (`triathlons.php?CoureurNom=…`, présente dans le Sheet) —
un palmarès multi-épreuves dont le fan-out coûterait ~130 requêtes pour une URL —
et l'**identifiant d'épreuve inconnu**, que le site sert en 200 avec un `<title>`
vide et qui passerait sinon pour une épreuve sans classement publié. Un titre
**au format inattendu** est refusé de même, et distinctement : il est lu par
position depuis la droite, donc un champ manquant décale tout — nom vide, ville
promue en nom, taille perdue dans le type, date pourtant juste
(`_require_event_name` : aucune ligne → identifiant inconnu, des lignes → format
du titre changé). `import_service._require_event_name` rattrape bien le nom vide
en aval, mais après le scrape, sans nommer la cause, et le type dégradé
n'y serait rattrapé par personne. Comme la
FFTRI, le site **republie** (« Chronométrée par BREIZHCHRONO ») : un
avertissement est journalisé quand le chronométreur est un provider supporté —
sa page ne lie que son accueil, aucune URL d'épreuve n'est reconstructible.

Deux particularités de données à connaître : les lignes que le site n'a pas
appariées à un coureur portent le libellé `?DOSSARD #43637` (3 sur 322 à
Quiberon) et sont **importées telles quelles** en nom, sans prénom — les écarter
créerait autant de trous dans le classement, comptés en `rank_gap` par
`services/quality.py`, ce qui masquerait le ratio de place de toute l'épreuve. Et
un relais publie **une ligne par équipier**, temps et rang partagés : les deux
participations sont importées, mais les rangs en doublon font sortir l'épreuve
`is_reliable=false` — limite connue de `quality._rank_anomalies`, hors périmètre.

Sondage du HTML réel (fait autorité) :
`docs/superpowers/specs/2026-07-27-runnerbreizh-sondage.md`. Spec, plan et
tâches : `specs/002-runnerbreizh-scraper/`.
