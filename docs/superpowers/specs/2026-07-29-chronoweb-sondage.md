# chronoweb.com — sondage du HTML réel

Issue : [#55](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/55)
(sous-issue de #33, section B). Sondage effectué le **29/07/2026**.

Ce document est la **vérité de terrain** : il prime sur l'énoncé de l'issue, sur
le design et sur le plan. Toute divergence se tranche en re-sondant, pas en
raisonnant.

## Ce que l'issue annonçait, et ce qui est faux

| Énoncé de l'issue #55 | Observation du 29/07/2026 |
| --- | --- |
| « `<select>` liste les épreuves de l'événement (→ **boucle** pour `scrape_event_all`) » | **Faux, et c'est le fait structurant du sondage.** Il n'y a rien à boucler : **une seule requête rend déjà toutes les épreuves de l'événement**, classements complets inclus. Le `<select>` ne pilote qu'un basculement de classe CSS `hidden` côté navigateur. |
| « Parsing du tableau en `<div>` (pas de `<tr>`/`<th>` — sélecteurs par classe) » | **Confirmé.** `div.htmltable` / `a.table-row.body` / `div.table-cell`, aucune balise de tableau. |
| « Extraction du dossard depuis `&bib=` » | Confirmé, mais **inutilement indirect** : le dossard est aussi le texte de `div.lineinfo_bib`, dans la ligne. |
| « `scrape()` + `scrape_event_all()` » | Hors convention actuelle : `scrape_event_all()` est **la seule** voie d'import (cf. AGENTS.md, « Conventions scrapers »). |
| « Effort : M — markup non standard à parser » | Le markup est régulier et **strictement identique sur les 89 épreuves du panel**. La difficulté réelle est ailleurs : une ligne du tableau n'est pas un participant, mais un **passage à un point de chronométrage** (voir plus bas). |

## Panel sondé

21 événements, **89 épreuves**, **31 642 lignes**, **14 015 participants
distincts**, millésimes 2015 → 2026, 6 disciplines. Pages conservées sous
`pages/ev<event>_ep<epreuve>.html` pendant le sondage.

| `event` | Événement | Date | Épreuves | Participants |
| --- | --- | --- | --- | --- |
| 145 | Foulées de la solidarité | 13/08/2015 | 2 | 195 |
| 146 | Triathlon de Chalain | 14/06/2015 | 1 annoncée, **0 tableau** | **0** (aucun classement publié) |
| 147 / 148 | Les Géraldines de la Vichyssoise / Les Marcels | 24/05/2015 | 2 + 2 | 167 + 167 (publiés **deux fois**, cf. § doublons) |
| 296 | Duathlon de Toulouse 2024 | 10/03/2024 | 6 | 904 |
| 323 | Triathlon d'Oléron 2024 | 06/10/2024 | 3 | 854 |
| 334 | Aquathlon de la Verrerie 2025 | 23/03/2025 | 6 | 185 |
| 347 | Altriman 2025 | 12/07/2025 | 4 | 1 574 |
| 349 | Swimrun du Levézou 2025 | 27/07/2025 | 5 | 199 |
| 353 | Triathlon de l'Omois 2025 | 31/08/2025 | 4 | 886 |
| 355 | Triathlon de St Pardoux 2025 | 07/09/2025 | 5 | 487 |
| 356 | ALEFPA Trail 2025 | 20/09/2025 | 5 | 1 014 |
| 358 | Triathlon d'Oléron 2025 | 12/10/2025 | 5 | 1 049 |
| 368 | Aquathlon de la Verrerie 2026 | 29/03/2026 | 5 | 170 |
| 369 | Triathlon de Limoges métropole 2026 | 25/04/2026 | 7 | 663 |
| 371 | Triathlon de Dijon 2026 | 30/05/2026 | 8 | 1 622 |
| 373 | Trail des Ponticauds 2026 | 12/06/2026 | 1 | 350 |
| 374 | Triathlon de Chalain 2026 | 13/06/2026 | 7 | 1 261 |
| 375 | Font Romeu nature trail 2026 | 20/06/2026 | 4 | 1 733 |
| 379 | Course nature du Château 2026 | 18/07/2026 | 3 | 365 |
| 381 | Swimrun du Levézou 2026 | 26/07/2026 | 5 | 170 |

Le catalogue complet du site (`/resultats.php`) porte **222 événements**. Son
paramètre `?annee=` est **ignoré côté serveur** : les trois millésimes demandés
ont rendu trois fois le même octet-pour-octet (170 406 o), le filtrage par année
étant fait en JavaScript.

## Le fait structurant : une requête = tout l'événement

`resultats_evenement.php?event=323&epreuve=1147` et
`resultats_evenement.php?event=323&epreuve=1148&cat=all&point=10` rendent la
**même page**, à 28 lignes de diff près :

```diff
-  <option value="1147"  selected >Triathlon M</option>
+  <option value="1147"  >Triathlon M</option>
-  <div class="results_epreuve epreuve_1147 " data-race="1147">
+  <div class="results_epreuve epreuve_1147 hidden" data-race="1147">
-  init_epreuve = 1147;
+  init_epreuve = 1148;
```

Conséquences, toutes vérifiées :

- `epreuve`, `cat` et `point` sont des **paramètres d'affichage**. Un `epreuve`
  inexistant (`?event=323&epreuve=999`) rend la page complète des 3 épreuves,
  sans erreur ;
- l'import d'une URL chronoweb est un import **d'événement entier**, comme
  Chronoplace et ok-time : 8 épreuves et 1 622 participants pour Dijon 2026, en
  **une** requête HTTP ;
- il n'y a **aucune pagination**, aucun appel AJAX, aucun JS à exécuter.

Coût mesuré : 14 Ko à 4,5 Mo par page, **1,09 s** pour la plus lourde (Dijon
2026, 4 887 lignes).

## Structure de la page

```
h2.date                                  06/10/2024        (jj/mm/aaaa, seul porteur de la date)
h2.name                                  Triathlon d'Oléron 2024
select.select_epreuve > option[value]     1147 → « Triathlon M »   (libellé de chaque épreuve)
div.results_epreuve.epreuve_1147[data-race=1147]
  div#table_epreuve_1147.htmltable.results_list
    div.table-row.head > div.table-cell   (9 en-têtes)
    a.table-row.body[data-cat][data-point][data-pointname]   ← une ligne = un PASSAGE
      div.table-cell.classement
        div.display_rank_global           1
        div.display_rank_cat.hidden       1
      div.table-cell                      02:13:26        Temps de course (cumulé)
      div.table-cell.lineinfo_name        MARIN Thomas
      div.table-cell.lineinfo_bib         360
      div.table-cell                      MSE             Cat. (= data-cat)
      div.table-cell                      00:39:26        Temps intervalle (durée du segment)
      div.table-cell                      6               Clt. int.
      div.table-cell.vmoyenne             15.22 km/h
      div.table-cell.gain                 0
```

Les 9 en-têtes — `Clt.` | `Temps de course` | `Nom` | `Doss.` | `Cat.` |
`Temps intervalle` | `Clt. int.` | `Vit. moyenne` | `Gain` — sont **identiques
sur les 89 épreuves du panel**, quelle que soit la discipline.

**Le rang ne se lit pas au texte de la première cellule.** Elle contient deux
`<div>` superposés (global affiché, catégorie masquée) : `get_text()` rend
« 11 » pour un athlète 1ᵉʳ au général et 1ᵉʳ de catégorie, et « 11837 » pour
118ᵉ / 37ᵉ. Il faut lire `div.display_rank_global` et `div.display_rank_cat`
séparément. Les deux sont présents et numériques sur **31 642 / 31 642** lignes.

## Une ligne n'est pas un participant, c'est un passage

Chaque ligne porte `data-point` (id du point de chronométrage) et
`data-pointname`. Sur les 31 642 lignes du panel, **trois** libellés seulement :
`Course` (13 709), `Vélo` (9 157), `Natation` (8 776). Le couple
`(dossard, point)` est unique : **zéro doublon** mesuré.

Un participant = l'union de ses lignes au sein d'une épreuve. Exemple
(Oléron 2024, épreuve 1147, dossard 360) :

| `data-point` | Nom du point | Temps de course | Temps intervalle | Clt. global |
| --- | --- | --- | --- | --- |
| 1 | Natation | 00:24:24 | 00:24:24 | 1 |
| 8 | Vélo | 01:31:34 | 01:00:09 | 1 |
| 14 | Course | 02:13:26 | 00:39:26 | 1 |

Trois invariants, tous mesurés sur l'ensemble du panel :

1. **`Temps de course` est un cumul depuis le départ**, croissant avec l'ordre
   des `data-point` : 8 930 participants vérifiés, **0 contre-exemple** ;
2. **`Temps intervalle` est la durée du segment** qui précède le point ;
3. au **premier** point, les deux sont égaux : 8 884 / 8 884.

Donc, pour un participant : le **temps total** et les **rangs finaux** sont ceux
de sa ligne au point de `data-point` **maximal** ; les **splits** sont les
`Temps intervalle` de chaque point, dans l'ordre.

Contrôle croisé : sur Oléron 2024/1147, `Clt. global` au point 14 vaut 45 pour
le dossard 347, et sa fiche individuelle affiche « Général : 45 » — même valeur,
même temps (02:40:34).

### Les transitions ne sont pas publiées, mais elles sont calculables

Aucun point `T1` / `T2` dans le tableau. L'écart
`cumul[i] − intervalle[i] − cumul[i−1]` est pourtant exactement la transition :

- **jamais négatif** sur 17 497 écarts mesurés (714 nuls, 15 343 entre 1 s et
  10 min, 1 440 au-delà) ;
- les 1 440 écarts > 10 min sont **concentrés** sur Oléron (2024 et 2025) et
  Altriman, dont les transitions sont réellement longues — ce ne sont pas des
  anomalies de mesure ;
- vérification au caractère près contre la fiche individuelle, qui, elle,
  publie une ligne `table-row.transition` « Changement » :

| Épreuve / dossard | Écart calculé | « Changement » de la fiche |
| --- | --- | --- |
| 1147 / 360 (T1) | 00:07:01 | 00:07:01 |
| 1147 / 360 (T2) | 00:02:26 | 00:02:26 |
| 1147 / 347 (T1) | 00:11:03 | 00:11:03 |
| 1147 / 347 (T2) | 00:03:38 | 00:03:38 |

Un triathlon chronoweb peut donc renseigner les **5 slots** `swim/t1/bike/t2/run`
sans requête supplémentaire. La reconstitution n'est possible que si le
participant a les deux points encadrants : à défaut, la transition reste vide,
elle ne s'invente pas.

### Un point intermédiaire peut manquer à un finisher

Oléron 2025, épreuve 1291 : 450 au point Natation, **439** au Vélo, 445 à la
Course. Un participant peut donc finir sans avoir été lu à un point
intermédiaire. Le split correspondant est simplement absent — ce n'est ni un
abandon ni une erreur de parsing.

## Statuts : aucun libellé, un seul signal

Le HTML ne contient **aucun** `DNF`, `DNS`, `DSQ`, `Abandon` ni `NC` (recherche
insensible à la casse sur tout le panel). Le seul signal disponible est
l'**absence de ligne au point final** : 199 participants sur 14 015 (**1,42 %**)
ont franchi au moins un point sans figurer au dernier.

- un participant absent du point final n'a **ni temps total ni rang final** :
  l'heuristique existante de `services/mapping.derive_status` (finisher si temps
  total, sinon DNF) le classe déjà DNF sans que le scraper ait à se prononcer ;
- **DNS et DSQ sont invisibles** : un non-partant n'a aucune ligne, un
  disqualifié n'est pas distingué d'un abandon. Limite de la source.

## Ce que la source ne publie pas

### Aucun club

**Zéro occurrence** de « club » dans le HTML du panel, ni dans le tableau, ni
sur la fiche individuelle. Comme runnerbreizh et Competitor, les participations
chronoweb sortiront avec `club = NULL`, donc **hors du périmètre `scope=club`**
(dashboard, page club, stats). C'est une limite de la source, pas un choix
d'implémentation — et elle est sans danger : `athlete_repository.resolve` ne met
à jour `Athlete.club` que si un club est fourni.

### Aucune date de naissance

Seule la catégorie situe l'âge.

### La ville n'est pas sur la page de résultats

Elle n'existe que dans le **catalogue** `/resultats.php`
(`div.table-cell.location` : « St Georges d'Oléron », « Les Angles »…). La
récupérer coûte une requête de 170 Ko par import — arbitrage à trancher au
cadrage, pas une évidence.

## Identité des participants

Le champ `div.lineinfo_name` mélange trois casses, mesurées sur les 31 642
lignes :

| Forme | Occurrences | Exemple |
| --- | --- | --- |
| `NOM Prénom` | 27 414 | `MARIN Thomas` |
| Tout en majuscules | 2 002 | `PRIOUX EMMANUEL`, `JEAN BONNEAU` |
| Tout en minuscules | 2 226 | `fayet pascaline` |

`utils.split_athlete_name` traite les trois, avec sa limite documentée
(« JEAN BONNEAU » → nom entier, prénom vide). Rien de spécifique à écrire.

**Mojibake résiduel de la source** : 4 lignes sur 31 642 portent `VÈronique` /
`ValÈrie` (saisie CP850 recodée en UTF-8 côté chronoweb). La page est bien
servie et bien décodée en UTF-8 ; il n'y a rien à corriger côté scraper.

## Catégories : deux conventions dans le même champ

81 codes distincts, sur deux conventions **contradictoires** :

| Convention | Genre | Exemples |
| --- | --- | --- |
| FFTRI — **préfixe** | 1ʳᵉ lettre | `MSE`, `FSE`, `MV1`, `FV7`, `MS2`, `MCA`, `FPU` |
| FFA — **suffixe** | dernière lettre | `SEM`, `SEF`, `V1M`, `V3F`, `ESM`, `JUF`, `CAM` |
| FFA masters — **suffixe**, préfixe trompeur | dernière lettre | `M0M`, `M0F`, `M1F`, `M7M`, `M9M` |
| Équipe | aucun | `MIXT`, `DUOX`, `DUOM`, `DUOF`, `MASC`, `FEM` |

Le piège est `M0F` : préfixé `M`, féminin. Lire le genre au premier caractère
donnerait « masculin » à toutes les féminines masters FFA.

Règle qui classe correctement les **81** codes du panel :

1. `MIXT`, `DUOX`, `DUOM`, `DUOF` → genre vide (le code décrit une **équipe**) ;
2. `MASC` → M, `FEM` → F ;
3. code commençant par `M`/`F` **suivi d'une lettre** → genre = premier
   caractère (`MSE`, `FV1`) ;
4. sinon → genre = dernier caractère s'il vaut `M`/`F` (`SEM`, `V1F`, `M0F`,
   `M1M` : le chiffre en deuxième position exclut la règle 3) ;
5. sinon → vide.

`MASC` / `FEM` / `MIXT` apparaissent **aussi hors relais** (50 / 45 / 64 lignes,
p. ex. le dossard 422 d'Oléron 2024 en Triathlon M individuel) : ce sont alors
des catégories « toutes classes », pas un marqueur d'équipe.

## Relais : une ligne par équipe

Contrairement à runnerbreizh (une ligne par équipier), chronoweb publie **une
ligne par équipe**, avec le nom d'équipe dans la colonne Nom :

| Épreuve | Dossards | Exemple de « nom » | Catégorie |
| --- | --- | --- | --- |
| Duathlon Toulouse « S Relais » | 13 | `TRIPOTES TEAM GOLFECH RELAIS1` | `MIXT` |
| Omois « Triathlon S Relais » | 27 | `LES BRAS CASSÉS` | `MASC` |
| Levézou « Swinrun M duo » | 38 | `LES Y DU SWIMRUN HERAULT` | `MASC` |
| Verrerie « Aquathlon Team Relais » | 14 | `CREUSOTRI` | `MASC` |

Conséquence : pas de rang dupliqué, donc pas de dégradation de
`quality.analyze` — contrairement au relais runnerbreizh. Le signal
d'appartenance est le **libellé d'épreuve** (`Relais`, `Duo`, `Team`) ; la
catégorie seule ne suffit pas (`MASC` existe en individuel).

L'« Aquathlon Team Relais » de la Verrerie 2025 pousse le modèle plus loin :
**8 points** alternant `Natation` et `Course` (4 relayeurs), 112 lignes pour
14 équipes. Les 5 slots positionnels n'y suffisent pas — c'est le cas d'usage du
chemin générique `ScrapedResult.segments`.

## Classification des épreuves

`classify_event_type(libellé, contexte=nom_événement)` a été passé sur les 89
libellés du panel. Il est juste sur 86, avec trois écarts mesurés :

| Événement | Libellé | Classé | Attendu | Cause |
| --- | --- | --- | --- | --- |
| ALEFPA Trail 2025 | `53 km`, `32 km`, `22 km`, `13 km` | `course-a-pied` | `trail` | `53 km` **nomme un sport** (course à pied) pour le classifieur, qui ne consulte donc pas le contexte. Curiosité : `7 kms` (Ponticauds) échappe à la règle et sort bien en `trail`. |
| Les Géraldines / Les Marcels (2015) | `Les Géraldines` | `triathlon` | `course-a-pied` | Ni le libellé ni le contexte ne nomment un sport → repli global du classifieur. |
| Altriman 2025 | `Altriman` | `triathlon` | `triathlon-xl` | Le nom de marque ne porte pas la taille. |

Les deux premiers sont des limites **du classifieur partagé**, pas du scraper :
les corriger toucherait tous les fournisseurs. À documenter, pas à contourner
localement.

Le nom de chaque `Course` se compose avec `utils.qualify_event_name` :
« Triathlon d'Oléron 2024 » + « Triathlon M » → `Triathlon d'Oléron 2024 -
Triathlon M`. Sans qualification, les 8 épreuves de Dijon fusionneraient et
leurs dossards entreraient en collision (issue #21).

## Les URLs réellement présentes dans le Sheet

7 occurrences, **5 URLs distinctes**, **3 formes** :

```
resultats_evenement.php?event=323&epreuve=1147
resultats_evenement.php?event=323&epreuve=1148&cat=all&point=10        (×3)
resultats_participant.php?event=347&epreuve=1234&bib=599
resultats_participant.php?event=347&epreuve=1235&bib=1563
files/pdf/Resultats_Triathlon_dOlron_2025.zip
```

Trois enseignements :

1. **deux des cinq URLs sont des fiches individuelles.** Comme la fiche T2AREA,
   elles se **tronquent** vers leur événement (`event=347`), qui est justement
   l'unité d'import — aucune information n'est perdue ;
2. **une URL pointe une archive ZIP**, pas une page de résultats. Elle doit être
   refusée avec un message qui nomme la forme attendue, sans quoi le scraper
   tenterait de parser un binaire ;
3. les paramètres `epreuve`, `cat`, `point`, `bib` sont **sans effet sur les
   données**. Ne garder que `event` donne une clé d'événement unique — et donc
   une seule entrée de cache TTL pour les 4 graphies d'Oléron 2024 ci-dessus.
   (Comme pour runnerbreizh, cette canonicalisation fixe le `source_url` des
   `ScrapedResult`, **pas** `Course.source_url`, que `import_service` remplit
   avec l'URL brute.)

## Cas limites du serveur

| Requête | Réponse | Signal exploitable |
| --- | --- | --- |
| `?event=99999&epreuve=99999` | **200**, 12 Ko | « Aucun évènement trouvé avec cet ID... », **pas de `h2.name`** |
| `resultats_evenement.php` sans paramètre | **200**, 12 Ko | idem, + `Warning : Undefined variable $eventinfo` |
| `?event=323&epreuve=999` | **200**, page complète | l'épreuve inconnue est ignorée, l'événement est rendu |
| `event=146` (Triathlon de Chalain 2015) | **200**, 14 Ko | `h2.name` **présent**, `<select>` présent, **aucune ligne** |

D'où la distinction à tenir, comme pour runnerbreizh : **pas de `h2.name` → URL
fausse, on lève** ; **`h2.name` présent mais zéro ligne → événement sans
classement publié, on rend une liste vide** (que `import_service` traite déjà
sans erreur, en 0 importé).

## La fiche individuelle est cassée sur les épreuves mono-point

`resultats_participant.php` renvoie du PHP en erreur dès que l'épreuve n'a qu'un
seul point de chronométrage (trail, swimrun) :

```
Warning : Undefined variable $nom_coureur in /sites/chronoweb.com/files/dist/resultats_participant.php on line 261
Warning : Undefined variable $time in /sites/chronoweb.com/files/dist/resultats_participant.php on line 254
```

Mesuré sur ALEFPA Trail 2025 (bib 1) et Swimrun du Levézou 2025 (bib 91), alors
que les mêmes participants sont parfaitement lisibles dans le tableau
d'événement. **Ne jamais faire dépendre l'import de cette page** : elle
n'apporte, quand elle fonctionne, que les points de passage intermédiaires
(« 8 km », « 14 km ») et les transitions — ces dernières étant déjà calculables
depuis le tableau.

## Doublons côté site

Les événements **147** et **148** publient le **même couple d'épreuves** (« Les
Géraldines », « Les Marcels », 24/05/2015, mêmes 167 participants) sous deux
`event` différents. Importer les deux URLs créerait deux `Course` de même
`(nom, date, type)`… donc **une seule** en base, la contrainte d'unicité les
fusionnant, avec des dossards identiques : l'upsert par
`(course_id, bib_number)` absorbe le doublon. Rien à faire, mais à savoir avant
de conclure à un bug de comptage.

Autre cas voisin : le Duathlon de Toulouse 2024 publie deux épreuves
« Challenge 1er Tour » / « Challenge 2ème Tour » (208 et 318 participants, point
unique `Vélo`) qui sont des **classements dérivés**, pas des courses. Elles
donneront deux `Course` supplémentaires. Le sondage le constate ; l'arbitrage
(importer ou filtrer) relève du cadrage.

## Politesse et robots.txt

```
User-agent: *
Crawl-delay: 3600
```

Aucun `Disallow`. Le `Crawl-delay` d'une heure vise les robots d'indexation, pas
un import ponctuel : notre usage est d'**une requête par épreuve importée**.
C'est un argument de plus contre tout balayage du catalogue (222 événements) et
contre une requête d'appoint systématique sur `/resultats.php`.

## Ce qui existe déjà et qu'il ne faut pas réécrire

| Besoin | Où c'est déjà fait |
| --- | --- |
| Normalisation des temps | `scrapers/utils.normalize_time` |
| Découpage nom / prénom | `scrapers/utils.split_athlete_name` |
| Qualification du nom d'épreuve | `scrapers/utils.qualify_event_name` |
| Type d'épreuve | `scrapers/classify.classify_event_type(…, contexte=…)` |
| Statut d'un non-finisher | `services/mapping.derive_status` (heuristique : pas de temps → DNF) |
| Ré-étiquetage des splits par sport | `services/mapping.build_splits` (+ `segments` pour les cas > 5 slots) |
| Détection du provider | `scrapers/registry` : déclarer `_HOSTS = ("chronoweb.com",)` sur un `HostMatchedProvider`, **jamais** un `in url` |
