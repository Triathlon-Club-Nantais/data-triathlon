# runnerbreizh.fr — sondage du HTML réel

Issue : [#56](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/56)
(sous-issue de #33, section B). Sondage effectué le **27/07/2026**.

Ce document est la **vérité de terrain** : il prime sur l'énoncé de l'issue, sur
le design et sur le plan. Toute divergence se tranche en re-sondant, pas en
raisonnant.

## Ce que l'issue annonçait, et ce qui est faux

L'issue #56 a été rédigée le 18/07/2026 sur une observation antérieure du site.
Deux de ses affirmations ne tiennent plus :

| Énoncé de l'issue | Observation du 27/07/2026 |
| --- | --- |
| « Markup en `<td>` stylés, **sans `<tr>`/`<th>` francs** » | **Faux.** La table de résultats est une `table.tableau-courses` avec des `<tr>` francs, 8 `<td>` par ligne. Il n'y a effectivement **aucun `<th>`** : la ligne d'en-tête est faite de `td.courses-annees`. Le site a été restylé (variables CSS `#0f172a`, `#e2e8f0` — palette Tailwind slate). |
| « `scrape()` + `scrape_event_all()` » | Hors convention actuelle : `scrape_event_all()` est **la seule** voie d'import depuis la suppression du scraping athlète-unique (cf. AGENTS.md, « Conventions scrapers »). |

Le reste de l'issue est confirmé : HTML statique, pagination `page=N`,
50 résultats par page, **aucun dossard**.

## Panel sondé

6 épreuves, 3 types, 2 millésimes, 19 requêtes au total.

| Clé `CourseFichierGpsNom` | Épreuve | Type annoncé | Classés | Pages |
| --- | --- | --- | --- | --- |
| `2026-07-1925plouescat` | Triathlon de Plouescat S (0.75/20/5) | Triathlon | 356 | 8 |
| `2026-07-058guidel` | Triskel Race Cross Duathlon de Guidel XS (2.2/5/1) | Duathlon | 40 | 1 |
| `2026-07-047pleneuf-val-andre` | Aquathlon du Val-André S (1/5) | Aquathlon | 82 | 2 |
| `2026-06-21111duosizun` | TriBreizh en Duo L (1.9/90/20) | Triathlon | 31 équipes / 62 lignes | 2 |
| `2025-09-0749quiberon` | Triathlon de Quiberon M (1.5/38/10) | Triathlon | 322 | 7 |
| `2025-04-1323nozay` | Duathlon Nozéen S Open (5/16/2.5) | Duathlon | 135 | 3 |
| `2025-10-0527coueron` | Couëron Duathlon S (5/20/2.5) | Duathlon | 270 | 6 |

Quiberon M 2025 a été **scrapé intégralement** (7 pages + 1 page vide = 8
requêtes, 322 lignes) : c'est sur lui que portent les mesures de casse de nom,
de statuts et de lignes anomales ci-dessous.

Le markup est **identique** sur les millésimes 2025 et 2026 : mêmes 8 colonnes,
mêmes libellés d'en-tête, même structure de cellule.

## Les URLs réellement présentes dans le Sheet

10 occurrences sur les 785 liens du Sheet, réduites à **4 épreuves distinctes** :

```
requetetriathlons.php?CourseFichierGpsNom=2025-09-0749quiberon&page=2&tricourse=&Sexe=
requetetriathlons.php?CourseFichierGpsNom=2025-09-0749quiberon
requetetriathlons.php?CourseFichierGpsNom=2025-04-1323nozay&page=2&tricourse=&Sexe=   (×6)
requetetriathlons.php?CourseFichierGpsNom=2025-10-0527coueron&page=3&tricourse=&Sexe=
triathlons.php?CoureurNom=KUENTZ&CoureurPrenom=Olivier
```

Trois enseignements, chacun structurant :

1. **La majorité des URLs porte `&page=N`** (2 ou 3) — le contributeur a copié
   l'URL de la page où il s'était trouvé. Un scraper qui partirait de l'URL telle
   quelle manquerait silencieusement les pages 1..N-1. Il faut **repartir de la
   page 1**, donc réécrire la query.
2. Les paramètres `tricourse=` (ordre de tri) et `Sexe=` (filtre M/F) sont des
   **vues** de la même épreuve. `Sexe=F` renvoie un sous-ensemble : les conserver
   amputerait l'import. `tricourse` change l'ordre, donc les rangs lus resteraient
   justes mais la pagination deviendrait dépendante du tri.
3. `sheet_source.normalize_url` **conserve la query** (elle distingue deux heats
   Breizh Chrono) : `…quiberon&page=2&…` et `…quiberon` sont donc deux entrées
   distinctes du Sheet, non dédoublonnées en amont. Sans canonicalisation dans le
   scraper, une même épreuve serait scrapée deux fois par `import-sheet`, et
   `Course.source_url` porterait l'une ou l'autre forme selon l'ordre d'arrivée
   — deux clés de cache TTL pour une épreuve.

La 11e forme, `triathlons.php?CoureurNom=…&CoureurPrenom=…`, est une **fiche
coureur** : le palmarès de tous les triathlons d'une personne, pas une épreuve.
Décision (arbitrage du 27/07/2026) : **refus explicite**, sur le précédent T2Area
qui refuse l'URL d'événement. Le fan-out mesuré coûterait ~19 épreuves × ~7 pages
≈ 130 requêtes pour une URL, et produirait N `Course` pour une `source_url`.

## Structure de la page

`GET https://www.runnerbreizh.fr/requetetriathlons.php?CourseFichierGpsNom=<clé>[&page=N]`

Apache + PHP 7.4, `text/html; charset=UTF-8`, `Cache-Control: no-store`. Trois
cookies posés (`PHPSESSID`, `urlsiterunners56`, `analitycs-runners56-ok`) —
aucun n'est nécessaire : chaque page répond en 200 sans session.

Deux `<table>` dans le document, et **une seule** porte le classement :

- `table#titre-courses` — bandeau de l'épreuve : **1** `<tr>`, 2 `<td>` (date en
  anglais abrégé ; nom + ville + distances), ou **3** quand la page porte la
  mention « Chronométrée par » — c'est cette troisième cellule qui l'accueille ;
- `table.tableau-courses` — le classement : **1 + n** `<tr>`.

| Index dans `.tableau-courses` | Rôle |
| --- | --- |
| 0 | en-tête : 8 `td.courses-annees` |
| 1..n | une ligne de résultat, 8 `<td>` |

Mesuré : page pleine = 51 `<tr>` (1 + 50), page 7 de Quiberon = 23 (1 + 22),
page au delà de la dernière = **1** (l'en-tête seul). Le bandeau n'est **pas**
dupliqué dans la table de classement — un décompte fait sur le document entier
(bandeau + en-tête = 2 `<tr>` sur une page vide) induit en erreur ici : le critère
de fin de pagination se lit dans `.tableau-courses`, où il ne reste que l'en-tête.

### Les 8 colonnes, figées quel que soit le sport

```
0  Nom et Prénom     3  Vélo               6  Classement
1  Perf              4  Place avant CàP    7  Catégorie
2  1ère épreuve      5  CàP
```

**Les libellés d'en-tête ne renseignent pas le sport.** Ils sont identiques sur
les 7 épreuves du panel, triathlon comme duathlon comme aquathlon :

- en **duathlon**, « 1ère épreuve » porte la CàP1 et « CàP » la CàP2 — le
  libellé « Vélo » reste juste par coïncidence ;
- en **aquathlon**, la cellule « Vélo » est **vide** (`<td …></td>`), le libellé
  reste affiché.

Corollaire : le mapping des splits doit se faire **par position et par
`event_type`**, jamais par libellé d'en-tête. C'est exactement ce que fait
`services/mapping._SPLIT_KEYS_BY_SPORT` sur les 5 slots positionnels de
`ScrapedResult` (`duathlon` → `course1`/`course2`, `aquathlon` → `swim`/`run`) :
le scraper remplit `swim_time` / `bike_time` / `run_time` depuis les colonnes
2 / 3 / 5 et laisse le mapping ré-étiqueter.

**Il n'y a ni T1 ni T2** : les transitions ne sont pas publiées. La colonne 4
(« Place avant CàP ») est un **rang**, pas un temps.

### Anatomie d'une cellule

Ligne de résultat (Plouescat S, 1er) :

```html
<td …><span style="color: #0f172a;">MACQ Guillaume</span></td>
<td …>01:01:43</td>
<td …><b>00:13:37</b><br/>P:4<br/><span …>1.12%</span><br/><span …>3.30 km/h</span></td>
<td …><b>00:30:09</b><br/>P:3<br/><span …>0.84%</span><br/><span …>39.79 km/h</span></td>
<td …><b>1</b><br/><span style="color: green; …">&#8599; 3</span></td>
<td …><b>00:16:43</b><br/>P:1<br/><span …>0.28%</span><br/><span …>17.94 km/h</span></td>
<td …><b>1</b>/356<br/><span style="color: #94a3b8;">=</span><br/><span …>0.28%</span></td>
<td …><b>1</b>/S3M</td>
```

- **colonne 0** — `NOM Prénom` en clair. Enveloppé dans un `<span>` pour un
  coureur non inscrit au site, dans un `<a class="M|F" href="triathlons.php?…&di=<id>">`
  pour un coureur inscrit (16 des 50 lignes de la page 1 de Quiberon). La classe
  du lien donne le genre — mais **seulement pour les inscrits**, donc source
  secondaire.
- **colonne 1** — temps total, `HH:MM:SS`. Toujours présent sur les 322 lignes
  de Quiberon (aucun DNF/DNS/DSQ publié : le site ne liste que des classés).
- **colonnes 2, 3, 5** — temps du segment en `<b>`, puis rang de segment
  (`P:4`), écart en % au vainqueur du segment, vitesse moyenne. Seul le `<b>` va
  dans les splits ; le reste est de l'analyse propre à runnerbreizh et n'a sa
  place que dans `raw_data`.
- **colonne 4** — rang à l'entrée de la dernière CàP + évolution (`↗ 3` / `↘ 56`
  / `=`, encodés `&#8599;` / `&#8600;`). Aucun équivalent en base : `raw_data`.
- **colonne 6** — `rang/total` + évolution + percentile. C'est la **seule source
  du nombre de classés**, identique sur toutes les lignes d'une épreuve.
- **colonne 7** — `rang de catégorie/CATÉGORIE`. Le suffixe donne le genre :
  `S3M`, `SEM`, `MAF`, `V1F`… La cellule peut porter un `<span>` de couleur
  (rose pour les femmes) : lire le texte, pas le premier enfant.

### Métadonnées de l'épreuve

Le `<title>` est le porteur le plus fiable, et le seul en format français :

```
Résultats de la course du 19/07/2026 - Triathlon de Plouescat S (0.75/20/5) - Plouescat - 25.75KM - Type : Triathlon
```

→ date `19/07/2026`, nom `Triathlon de Plouescat S (0.75/20/5)`, ville
`Plouescat`, distance `25.75KM`, type `Triathlon`.

Le bandeau HTML rend la même date en **anglais abrégé** (`19 <br />Jul<br /> 2026`) :
ne pas la lire là. Types observés dans `Type :` : `Triathlon`, `Duathlon`,
`Aquathlon`. Le nom d'épreuve porte la taille (`S`, `M`, `L`, `XS`, `XL`) →
`scrapers.classify.classify_event_type` suffit à produire le slug canonique et
la distance sort de `extract_distance_km`.

**URL inconnue** : la page répond **200** avec un `<title>` vide et 2 `<tr>`
seulement (aucune ligne de données). Il n'y a pas de 404 à guetter.

## Pagination

- 50 lignes par page ; `&page=N`, 1-indexé.
- Au delà de la dernière page : **200**, et `.tableau-courses` réduite à son seul
  `<tr>` d'en-tête. L'arrêt sur page sans ligne est donc fiable (vérifié sur
  `page=9` et `page=20` de Plouescat, `page=8` de Quiberon).
- Coût : `ceil(classés / 50) + 1` requêtes.

**Ne pas borner la pagination sur le total de la colonne 6.** En relais, le
total compte des **équipes** et non des lignes : « TriBreizh en Duo » annonce
`/31` pour 62 lignes réparties sur 2 pages. Un `ceil(31/50) = 1` s'arrêterait à
la moitié de l'épreuve. Le total reste utile comme garde de cohérence, jamais
comme borne.

## Ce que le site ne publie pas

### Aucun dossard

Aucune des 8 colonnes ne porte de dossard, sur aucune épreuve du panel.

Ce n'est **pas** un travail à faire : le repli anti-doublon par athlète existe
déjà, **générique**, dans `import_service._Persister.add` (commit `b49e295`,
motivé par les 5 599 participations sans bib de Sportinnovation). Un
`bib_number=""` suffit ; le multiset par athlète rend le réimport idempotent.
Rien à écrire côté scraper, rien à écrire côté import.

### Aucun club — conséquence fonctionnelle assumée

Ni le classement, ni la fiche coureur (`triathlons.php?CoureurNom=…`) ne portent
de club. La fiche donne le nom, la catégorie (`SEM`), des indices de performance
et le palmarès ; le mot « club » n'y apparaît que dans le menu de navigation.

Conséquence : `Participation.club` restera `NULL`, et le filtre `scope=club`
(`core.club.tcn_clause` sur `Participation.club`) **exclura ces participations**
du dashboard, de la page club et des stats club. Les résultats existent en base
et sont visibles par épreuve et par fiche athlète, pas dans le périmètre TCN.

Décision (arbitrage du 27/07/2026) : **limite acceptée**, le scraper reste fidèle
à sa source. Deux vérifications qui la rendent sans danger :

- `athlete_repository.resolve` ne met à jour `Athlete.club` que si un club est
  fourni (`if club and existing.club != club`) : un import runnerbreizh
  **n'efface pas** le club d'un athlète déjà connu comme TCN ;
- `AthleteListItem` / `athlete_repository.search(club_only=True)` filtrent sur
  `Athlete.club`, pas sur la participation : un athlète TCN reste dans la liste
  club même après un import runnerbreizh.

L'alternative — inférer `Participation.club` depuis `Athlete.club` quand le
scraper n'en fournit pas — changerait la sémantique « club au moment de la
course » pour **tous** les providers. Elle mérite son issue, elle n'est pas dans
#56.

### Aucune date de naissance, aucun statut

Seule la catégorie situe l'âge. `Athlete.birth_date` restera `NULL` — la clé
`UNIQUE(nom, prenom, birth_date)` s'en accommode déjà.

Le site ne publie que des classés : sur les 322 lignes de Quiberon, **aucune**
sans temps total. `mapping.derive_status` retombera sur `finisher` par son
heuristique ; le scraper n'a pas de statut explicite à poser.

## Lignes anomales mesurées

Sur les 322 lignes de Quiberon M 2025 :

- **3 lignes anonymes** dont la colonne 0 vaut littéralement `?DOSSARD #9998`,
  `?DOSSARD #43637`, `?DOSSARD #13475` (le `#` est suivi d'un identifiant interne
  à 4-5 chiffres — 43637 sur une épreuve de 322 classés : ce n'est pas un
  dossard de course). Leur colonne 7 vaut `0 /M` : rang de catégorie 0, genre
  seul. Elles portent un temps, des splits et un rang général valides.
- **1 nom mutilé** : `PROD?HOMME Anais`. Vérifié au niveau de l'octet : le HTML
  servi contient bien un `?` (0x3F), ce n'est pas un défaut de décodage de notre
  côté. C'est la source qui a perdu l'apostrophe.

Décision pour les lignes anonymes : **les importer**, sous leur libellé brut,
`bib_number` vide, identifiant conservé dans `raw_data`. Les écarter créerait 4
trous dans le classement, donc 3 `rank_gap` dans `services/quality.analyze` →
`is_reliable=false` sur toute l'épreuve → ratio de place masqué partout
(cf. `2026-07-25-meilleure-place-ratio-design.md`). Le coût est de 3 fiches
d'athlète fantômes, mais distinctes (l'identifiant diffère) : pas de fourre-tout
partagé.

Décision pour `PROD?HOMME` : **laisser tel quel**. Réécrire `?` en `'` serait
deviner ; et la graphie corrigée, si elle arrive par un autre provider, sera
réconciliée par le mécanisme de l'issue #66 (`rescrape-db`).

## Relais / duo : une ligne par équipier

`TriBreizh en Duo L` publie **une ligne par équipier**, les deux partageant le
temps total, le rang général et la catégorie :

```
THOMAS Matthieu    04:45:06   1/31   1/M+M
COGREL Alban       04:45:06   1/31   1/M+M
COLLEAUX Jildaz    04:45:31   2/31   2/M+M
MONTABERT Gael     04:45:31   2/31   2/M+M
```

Le type annoncé reste `Triathlon` ; le relais se lit dans le nom (« en Duo ») et
dans la catégorie (`M+M`, `M+F`). `is_relay` est donc déductible, et il entre
dans `uq_course_identity` — sans collision ici, « TriBreizh en Duo L » et
« TriBreizh L » ayant des noms distincts.

**Limite connue, non corrigée** : deux finishers au même `rank_overall`
déclenchent `ANOMALY_DUPLICATE_RANK` dans `quality.analyze`, qui ne tolère les
rangs partagés qu'**entre** groupes solo/relais, pas au sein d'un groupe. Une
épreuve en duo sortira donc `is_reliable=false`. C'est la conséquence d'un format
source qui classe des équipes en listant des personnes ; le corriger relève de
`quality.py`, pas de #56.

## Le site est un republieur

Comme `fftri.t2area.com`, runnerbreizh republie des résultats produits ailleurs :
le bandeau de Plouescat porte « Chronométrée par » + le logo `BREIZHCHRONO` —
un provider que nous supportons déjà, avec dossards **et** clubs. La mention
n'est présente que sur 2 des 7 épreuves du panel, et son lien pointe l'accueil du
chronométreur (`http://www.breizhchrono.com`), jamais l'épreuve : aucune URL
source n'est constructible depuis la page. Comme pour T2Area, le geste utile est
un **avertissement journalisé** — seul l'opérateur peut fournir l'URL native.

## Ce qui existe déjà et qu'il ne faut pas réécrire

| Besoin | Outil existant |
| --- | --- |
| `NOM Prénom` → (nom, prénom), particules incluses | `scrapers.utils.split_athlete_name` |
| Nom d'épreuve → slug canonique + taille | `scrapers.classify.classify_event_type` |
| Distance depuis le nom | `scrapers.classify.extract_distance_km` |
| Rang `« 1 »`, `« 1/356 »` → `int` | `scrapers.utils.normalize_rank` |
| Splits ré-étiquetés par sport | `services.mapping.build_splits` (slots positionnels) |
| Dédup sans dossard | `services.import_service` (déjà générique) |
| Détection par host | `registry.HostMatchedProvider` + `_HOSTS` |
| Relais depuis la catégorie | `chronoplace._is_relay_category` (à factoriser si réutilisé) |

Host à déclarer : `runnerbreizh.fr` (le site sert sur `www.runnerbreizh.fr` ;
`HostMatchedProvider` couvre l'apex et ses vrais sous-domaines).
