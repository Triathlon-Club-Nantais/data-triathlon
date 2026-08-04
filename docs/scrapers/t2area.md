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

Deux particularités structurantes. **Les splits ne sont pas dans le classement** :
ils vivent sur la fiche individuelle, soit une requête par participant — le
scraper ne charge donc que les fiches des membres du TCN (25 requêtes sur les 901
lignes de La Baule M 2022). C'est le seul scraper conscient du club ; il
**réutilise** `core/club.py`, il ne le réimplémente pas (#76). Et **la FFTRI
republie** : chaque page porte « Résultats produits par X ». Quand X est un
provider supporté, un avertissement est journalisé — mais la mention ne lie que
l'accueil du chronométreur, jamais l'épreuve, donc aucune URL source n'est
constructible : seul l'opérateur peut la fournir.

Détails de lecture : colonnes lues **par libellé d'en-tête** (l'en-tête réel en
porte 10, `id_league` et `league` s'intercalant avant `Détails`) ; `00:00:00` vaut
temps absent (un DNF sort avec cette valeur) ; `bib_number` n'est rempli que
lorsque la clé de fiche est un vrai dossard (`bib-566`), jamais avec une licence
(`A44719`) ni un identifiant interne (`id-1153352`) ; splits mappés **par
libellé** (`CàP 1`/`CàP 2` en duathlon), un libellé inconnu faisant basculer
toute la fiche sur `segments`. Design :
`docs/superpowers/specs/2026-07-26-t2area-scraper-design.md`, plan :
`docs/superpowers/plans/2026-07-26-t2area-scraper.md`.
