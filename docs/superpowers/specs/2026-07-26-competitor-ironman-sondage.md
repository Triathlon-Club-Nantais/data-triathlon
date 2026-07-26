# Sondage de la source Competitor / WTC (ironman.com) — 2026-07-26

- **Issue** : [#54](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/54) (sous-issue de #33, section B)
- **Statut : source de vérité empirique.** Ce document consigne des mesures, pas
  des déductions. Le design et le module `app/scrapers/competitor.py` doivent
  s'y conformer — pas l'inverse.

Toutes les mesures ci-dessous ont été prises le 2026-07-26, par requêtes réelles.

## Épreuves du panel

| uuid d'URL | Épreuve | Nature de l'uuid | Ce qu'elle a servi à établir |
| --- | --- | --- | --- |
| `bb98aa20-f278-e111-b16a-005056956277` | IRONMAN France (Nice) | **série** | iframe, 21 éditions, filtre ODIV du rendu serveur |
| `4db33a98-76a5-e411-9400-005056951bf1` | IRONMAN 70.3 Vichy | **série** | pagination réelle (`@odata.nextLink`), contrat d'API complet |
| `6d98aa20-f278-e111-b16a-005056956277` | IRONMAN 70.3 Aix-en-Provence | **série** | seconde façade 70.3, résolution d'uuid |
| `f3a6cf4c-e9d5-4c6f-a425-86b3b8ba0524` | 2025 IRONMAN France Nice | **édition** | classement courant, ODIV, statuts |
| `66511861-b71e-44fd-8c65-cd282323354c` | 2024 IRONMAN France Nice | **édition** | adressabilité par année |
| `bff11f8b-5b01-482f-8c43-9a0f50d5b394` | 2025 IRONMAN 70.3 Vichy | **édition** | pagination à 2000, DSQ |
| `d0d11a9f-7ba1-4ae1-a308-556363546b25` | 2024 IRONMAN 70.3 Vichy | **édition** | statuts, genre, ODIV (jeu analysé ligne à ligne) |

## 1. `ironman.com` n'affiche aucun résultat en propre

La page « Results » d'une course (`https://www.ironman.com/races/<slug>/results`,
200, ~670 Ko) encastre **trois** iframes, toutes sur `labs-v2.competitor.com` et
toutes porteuses du **même uuid** :

```
/results/event/{uuid}            → le classement
/results/event/odiv/{uuid}       → l'Open Division, à part
/clubpoints/event/{uuid}         → les points club
```

Conséquence pour l'extraction : un motif `results/event/{uuid}` ne capte que la
première, les deux autres ayant un segment non-uuid après `event/`. Aucun besoin
de discriminer sur les attributs de balise.

**La page d'accueil de course (`/races/<slug>`, sans `/results`) ne porte aucune
de ces iframes** — mesuré : 0 occurrence sur 797 Ko. Une URL de course nue n'est
donc pas exploitable.

`https://www.ironman.com/<slug>-results` redirige vers `/races/<slug>/results`
(même corps à l'octet près). `follow_redirects=True` suffit.

## 2. L'iframe est une application Next.js *Pages Router*

`GET labs-v2.competitor.com/results/event/{uuid}` → 200, **6,5 Mo**, avec un
unique `<script id="__NEXT_DATA__" type="application/json">`. Pas de
`self.__next_f` : c'est l'ancien routeur, la charge est un seul JSON.

`props.pageProps` porte 8 clés, dont trois utiles :

| Clé | Contenu mesuré (IRONMAN France) |
| --- | --- |
| `subevents` | **21** éditions, de 2005 à 2025 |
| `latestResults` | 1748 lignes de résultat |
| `latestResultSubeventId` | `f3a6cf4c-…` = *2025 IRONMAN France Nice* |
| `nextResultsUrl` | `null` ici ; renseignée dès que le classement dépasse 2000 |

## 3. Une URL désigne une **série**, jamais une édition

C'est le fait structurant de cette source.

`subevents[i]` porte `wtc_eventid`, `wtc_name` (« 2025 IRONMAN France Nice »),
`wtc_eventdate` (`2025-06-29T00:00:00Z`) et `wtc_eventdate_formatted`
(`6/29/2025`). L'uuid de l'URL (`bb98aa20-…`) **n'est aucun** de ces
`wtc_eventid` : c'est un identifiant de série distinct.

Mesures sur le sélecteur d'année :

| Requête | Résultat |
| --- | --- |
| `/results/event/{uuid de série}` | 6 485 309 o — édition 2025 |
| `/results/event/{uuid d'édition 2024}` | 6 485 309 o — **édition 2025 quand même** |
| `/results/event/00000000-0000-0000-0000-000000000000` | 200, 29 619 o, `pageProps` **vide** |

Deux conclusions :

- **le segment d'URL n'est pas ignoré** (un uuid inconnu vide la page), mais il
  est résolu vers la série, et la page ne publie que la dernière édition. Le
  sélecteur d'année du site est purement client : **aucune URL ne porte
  l'année** ;
- **un uuid inconnu ne sort pas en 404** mais en 200 avec `pageProps` vide.
  C'est `subevents` qui fait office de détecteur d'épreuve introuvable.

Un piège de nommage vu au passage : la série 70.3 Vichy contient une édition
`2023 IRONMAN 70.3 Vichy DO-NOT-USE (see notes)` **en plus** de
`2023 IRONMAN 70.3 Vichy`. Deux éditions à la même date.

## 4. L'API est du Dataverse OData, joignable **uniquement** par le proxy de l'app

Le bundle client (`/_next/static/chunks/3z33xl4xi27dk.js`) livre le chaînage :

```js
let n = await fetch("/api/results-proxy?url=" + encodeURIComponent(r))
…
r = f(i?.["@odata.nextLink"] || null)
function f(e){ return e ? e.replace("/web/wtc_results?", "/web/results?") : null }
```

Mesures d'accès :

| Requête | Résultat |
| --- | --- |
| `GET api.competitor.com/web/wtc_results?…` | **404** `Resource not found` |
| `GET api.competitor.com/web/results?…` | **401** `missing subscription key` (APIM) |
| `GET labs-v2.competitor.com/api/results-proxy?url=…` | **200** |

Le proxy **valide sa cible** : toute entité autre que les résultats est refusée.

| `url=` pointant vers | Résultat |
| --- | --- |
| `api.competitor.com/web/results?…` | 200 |
| `api.competitor.com/web/wtc_events?$top=2` | **400** `{"error":"Invalid results URL"}` |
| `…/web/events`, `…/web/wtc_subevents` | **400**, idem |

Il n'y a donc **aucun moyen** d'obtenir la liste des éditions autrement que par
la page de 6,5 Mo. Le coût est structurel, pas un choix d'implémentation.

En revanche le proxy accepte un `$filter` **arbitraire**, ce qui donne accès à
n'importe quelle édition :

```
https://api.competitor.com/web/results
  ?$filter=_wtc_eventid_value eq {uuid d'édition}
  &$orderby=wtc_finishrankoverall
```

- filtre sur un uuid **d'édition** → le classement complet ;
- filtre sur un uuid **de série** → `value: []` (0 ligne). L'uuid de série n'est
  pas une valeur de `_wtc_eventid_value`.

Le proxy **réinjecte lui-même** la projection (`$select` + `$expand`) : une
requête sans `$select` renvoie quand même les 83 champs et les 4 entités liées.
Inutile de recopier le `$select` géant du front.

## 5. Pagination : 2000 lignes par page

Mesuré : 2025 IRONMAN 70.3 Vichy sort à 2000 lignes exactement avec un
`@odata.nextLink` (jeton `pagingcookie` Dataverse) ; 2024 IRONMAN 70.3 Vichy
sort à 1585 lignes sans lien suivant.

Le `nextLink` renvoyé pointe `/web/wtc_results?` — la forme que l'API directe
rejette en 404. Le front la réécrit en `/web/results?` avant de la passer au
proxy ; il faut faire pareil.

Le front dédoublonne les lignes recollées par `wtc_resultid` (`new Set(...)`).

## 6. `latestResults` est **amputé de l'Open Division**

Le `nextResultsUrl` du rendu serveur contient, en clair :

```
$filter=_wtc_eventid_value eq {uuid} and wtc_AgeGroupId/wtc_agegroupname ne 'ODIV'
```

Le rendu serveur applique donc le même filtre que l'affichage. Vérification par
comparaison, à édition égale :

| Édition | `latestResults` (page) | Requête sans filtre | ODIV perdus |
| --- | ---: | ---: | ---: |
| 2025 IRONMAN France Nice | 1748 (0 ODIV) | **1810** (62 ODIV) | **62** |
| 2025 IRONMAN 70.3 Vichy | 2000 (0 ODIV) | 2000 + pages (149 ODIV) | **149** |

Réutiliser `latestResults` pour économiser une requête coûterait donc des
participants réels — et rendrait l'édition courante incomparable aux éditions
anciennes, interrogées, elles, sans filtre.

## 7. Schéma d'une ligne de résultat

83 champs. Ceux qui portent l'information utile :

| Champ | Exemple | Note |
| --- | --- | --- |
| `wtc_ContactId.lastname` / `.firstname` | `Terrier` / `Vincent` | découpage déjà fait par la source |
| `wtc_ContactId.fullname` | `Vincent Terrier` | « Prénom NOM » |
| `wtc_bibnumber` / `wtc_bibnumber_v2` | `3544` / `null` | v2 est le repli alphanumérique |
| `_wtc_agegroupid_value_formatted` | `M30-34`, `ODIV` | catégorie |
| `wtc_AgeGroupId.wtc_gender_formatted` | `Male` | **le genre fiable** (cf. §8) |
| `wtc_finishtimeformatted` | `8:59:34` | `h:mm:ss`, heures non paddées |
| `wtc_swimtimeformatted` | `0:51:48` | |
| `wtc_transition1timeformatted` | `0:03:47` | **T1** |
| `wtc_biketimeformatted` | `4:59:44` | |
| `wtc_transitiontime2formatted` | `0:03:50` | **T2 — nommage asymétrique de T1** |
| `wtc_runtimeformatted` | `3:00:25` | |
| `wtc_finishrankoverall` / `…group` / `…gender` | `1` | scratch / catégorie / sexe |
| `wtc_finisher`, `wtc_dnf`, `wtc_dns`, `wtc_dq` | booléens | |
| `_wtc_teamresult_value` | `null` | relais ; **0 non-nul sur tout le panel** |

**Piège de nommage à ne jamais confondre** : `wtc_swimtime_formatted` (avec
tiret bas avant `formatted`) vaut `"3,108"` — des **secondes** avec séparateur
de milliers — tandis que `wtc_swimtimeformatted` (sans tiret bas) vaut
`"0:51:48"`. Idem pour bike, run, finish. Un seul caractère sépare la durée du
nombre de secondes.

Deux sentinelles, lues dans le bundle du front
(`99999 != e ? e : "-"` et `"0:00:00" != e ? e : "-"`) :

- **rang `99999`** = non classé. 93 lignes sur 1585 (Vichy 2024) ;
- **temps `"0:00:00"`** = absence. Observé en T2 sur les abandons.

Les champs de confort `athlete`, `bib` et `countryiso2` sont **fabriqués côté
navigateur** (`e.wtc_ContactId.fullname`, etc.) : présents dans `latestResults`,
**absents** des pages du proxy. Mesuré : `athlete` vaut `None` sur toute réponse
proxy.

## 8. `wtc_ContactId.gendercode` est faux

Sur 2024 IRONMAN 70.3 Vichy : **77 lignes sur 1585** où
`wtc_ContactId.gendercode_formatted` contredit
`wtc_AgeGroupId.wtc_gender_formatted`. Cas le plus lisible : Vincent Terrier,
vainqueur scratch masculin d'IRONMAN France 2025, catégorie `M30-34`, est donné
`gendercode: 2` / `"Female"`.

Le genre doit donc être lu **sur la catégorie d'âge**, jamais sur la fiche de
contact.

## 9. Statuts

Distribution sur 2024 IRONMAN 70.3 Vichy (1585 lignes) :

| | Nombre |
| --- | ---: |
| `wtc_finisher` | 1521 |
| `wtc_dnf` | 47 |
| `wtc_dns` | 14 |
| `wtc_dq` | 0 |
| **aucun des quatre** | **3** |

Ces 3 lignes sans aucun drapeau sont un cas réel et non résolu à la source. Un
abandon conserve ses splits partiels (`wtc_swimtimeformatted: "1:19:16"`) mais
perd son temps final (`null`) et voit ses trois rangs à `99999`.

## 10. Aucun club n'est publié

Recherche exhaustive sur les 83 champs : **aucun champ de club**. Le seul champ
approchant est `_wtc_teamresult_value` (relais, nul partout sur le panel). Les
seules données d'appartenance sont la nationalité
(`wtc_CountryRepresentingId.wtc_iso2`) et la ville de résidence
(`wtc_ContactId.address1_city`).

**Conséquence directe pour ce projet** : `app/core/club.is_tcn` travaille sur un
libellé de club. Une participation importée depuis Competitor sortira toujours
avec `club = ""`, donc **jamais marquée TCN**. L'iframe `/clubpoints/event/`
existe et porte, elle, des points club — elle n'a pas été sondée ; c'est la
piste à ouvrir si le rattachement au club devient nécessaire.

## 11. Distances

`wtc_swimdistancecompleted` / `bikedistancecompleted` / `rundistancecompleted` /
`totaldistancecompleted` sont les distances **parcourues par l'athlète**, pas
celles de l'épreuve : 214,23 km au total pour IRONMAN France (dont 169,23 km de
vélo, contre 180 km nominaux), et partielles pour un abandon. Elles ne
renseignent donc pas `Course.distance_km`.

## 12. Angles morts — ce que ce document n'établit pas

1. **Relais.** `_wtc_teamresult_value` est nul sur les 7 épreuves du panel. Le
   traitement du relais est donc écrit d'après le nom du champ, sans aucune
   mesure. Une épreuve avec relais publié invaliderait peut-être l'hypothèse.
2. **Les 3 lignes sans drapeau de statut** n'ont pas été expliquées.
3. **`/clubpoints/`** n'a pas été sondée (cf. §10).
4. **Pagination au-delà de 2 pages** : jamais observée. La plus grosse épreuve
   du panel tient en 2 pages ; le comportement du `pagingcookie` sur une 3ᵉ page
   est supposé, pas mesuré.
5. **Sports non-triathlon.** `pageProps.sport` vaut `Triathlon` sur tout le
   panel ; le bundle contient une branche `"Running" === U` avec un autre jeu de
   colonnes. Les épreuves de course à pied de la marque n'ont pas été sondées.
6. **Stabilité du proxy.** Il accepte aujourd'hui un `$filter` arbitraire. Rien
   ne garantit qu'il ne se restreindra pas au seul `nextLink` qu'il a émis.
7. **Volume réel dans le Sheet.** L'issue annonce 7 occurrences ; elles n'ont
   pas été relues une à une, ni vérifiées comme pointant des pages `/results`.
