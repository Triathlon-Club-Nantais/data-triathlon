# T2Area (FFTRI)

`fftri.t2area.com` (T2Area) est la plateforme officielle de la FFTRI : Joomla
server-rendered, classement complet en **une** requête, **aucune pagination**.
L'URL accepte trois profondeurs — édition (`/calendrier/<événement>/<épreuve>/<année>.html`,
le cas nominal), fiche individuelle (**tronquée** vers son édition, la forme du
Sheet) et épreuve sans année (1 GET de plus, on prend la dernière édition
publiée). Une URL d'**événement** est refusée : ses épreuves ont des dernières
éditions d'années différentes, un fan-out n'aurait pas d'année lisible. Un appel
= une `Course`. **Préférer l'URL d'édition dans le Sheet** : une URL d'épreuve
sans année est stockée telle quelle en `Course.source_url` — après publication
d'une nouvelle édition, un `import-sheet` (`force=False`) retombe alors sur la
course de l'année précédente, la juge fraîche (TTL 30 j) et renvoie `cached` au
lieu d'importer la nouvelle édition. Pas un bug : la conséquence d'accepter
cette profondeur, à connaître avant de la choisir dans le Sheet.

**Markup refait par la FFTRI (constaté le 24/09/2026, re-sondé le 30/09, #898).**
Le `<table id="resultList">` a disparu : chaque participant est une carte
`article.edition-result`, qui porte `data-gender`, `data-cat`, `data-league`,
`.edition-rank` (rang global **ou** statut `DNF`/`DSQ`), `.edition-name`,
`.edition-club` (suivi du badge `.edition-cat-badge`, `MS2`), `.edition-time`,
les splits (`.edition-split` : `<small>Natation</small><b>00:19:05</b>`, `—`
pour une transition non chronométrée) et le lien de fiche
(`a.edition-details-link` sous `/calendrier/`). L'en-tête « Résultats du … -
édition du 18-09-2022 » est passé du `<h1>` (qui ne dit plus que « Édition
2022 ») au `<title>`. Mesures sur La Baule M 2022, Nevers duathlon M 2022 et Lac
du Bouchet L 2025 : 901, 162 et 117 cartes, splits présents sur 893, 162 et 117
d'entre elles ; huit finishers de La Baule n'ont ni splits ni lien de fiche.

Conséquences. **Les splits sont désormais dans le classement**, pour tous les
participants : plus de requête par fiche pour eux. **Les rangs par genre et par
catégorie, eux, n'y sont plus** : ils ne vivent que sur la fiche individuelle
(bandeau `.rd-rank` : « 453 Global », « 419 Sexe », « 89 Catégorie »), donc le
scraper ne charge que les fiches des **finishers** membres du TCN (25 requêtes sur
les 901 lignes de La Baule). Les recalculer depuis l'ordre de la liste a été
mesuré, puis écarté : l'écart atteint une place au-delà de quelques centaines de
lignes (La Baule, rang 451 : 418 calculé, 417 publié). C'est l'un des deux
scrapers conscients du club, avec Breizh Chrono ; il **réutilise**
`core/club.py`, il ne le réimplémente pas (#76).

**La FFTRI republie** : chaque page porte « Résultats produits par X ». Quand X
est un provider supporté, un avertissement est journalisé — mais la mention ne
lie que l'accueil du chronométreur, jamais l'épreuve, donc aucune URL source
n'est constructible : seul l'opérateur peut la fournir.

Détails de lecture : une **édition inexistante** répond 303 vers
`/calendrier.html` ; `_fetch_edition` la reconnaît à l'URL finale et le dit,
là où une page sans carte signale un markup modifié. `00:00:00` et `—` valent
temps absent ; `bib_number` n'est rempli que lorsque la clé de fiche est un vrai
dossard (`bib-566`), jamais avec une licence (`A15993`) ni un identifiant interne
(`id-1153352`) ; le genre vient de `data-gender` (une carte peut n'avoir aucun
badge de catégorie) ; splits mappés **par libellé** (`CàP 1`/`CàP 2` en
duathlon, `T1`/`T2`), un libellé inconnu faisant basculer toute la ligne sur
`segments`. La page d'épreuve sans année, elle, n'a pas changé : ses liens
`/<épreuve>/<année>.html` donnent toujours la dernière édition. Design d'origine :
`docs/superpowers/specs/2026-07-26-t2area-scraper-design.md`, plan :
`docs/superpowers/plans/2026-07-26-t2area-scraper.md`.
