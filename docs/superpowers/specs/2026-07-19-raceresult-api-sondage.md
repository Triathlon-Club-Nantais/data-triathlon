# Sondage de l'API RaceResult — 2026-07-19

**Statut : source de vérité empirique.** Ce document consigne des mesures, pas des
déductions. Toute affirmation ici a été obtenue en interrogeant l'API réelle le
2026-07-19. Le plan `2026-07-19-raceresult-scraper.md` et le module
`backend/app/scrapers/raceresult.py` doivent s'y conformer — pas l'inverse.

**Pourquoi ce document existe.** Le premier sondage (2026-07-18) portait sur une
seule épreuve. Le moteur bâti dessus ne fonctionnait que sur elle : la revue
finale de branche a relevé cinq défauts bloquants, tous invisibles sans trafic
réel au-delà de cette épreuve. Le mode de défaillance n'était pas l'imprécision,
c'était **une épreuve unique érigée en généralité**. D'où la règle : ne rien
écrire ici qui n'ait été vérifié sur au moins trois épreuves, de préférence sur
plusieurs façades.

## Épreuves du panel

| eventId | Épreuve | Façade d'origine | Particularité |
| --- | --- | --- | --- |
| 393893 | Triathlon de Rumilly | my3 | l'épreuve historique du plan |
| 383326 | Aquathlon de Roanne | my3 | ancienne |
| 405215 | Genève Triathlon | my4 | 13 contests, relais, i18n |
| 405100 | La Foulée Agésinate | my2 | toutes listes `Live=1` |
| 406212 | Triathlon Vauban Besançon | my4 | groupes par **sexe** |
| 411749 | Mad'Trail 2026 | espace-competition | façade tierce |
| 410891 | Le Trail de la Ciboule | espace-competition | façade tierce |
| 392745 | ∆EH Tour of Hellas 2026 | chronoconsult | 6 listes sur 1 contest |
| 409130 | 24H Rollers du Mans | chronoconsult | listes en `Contest="0"` |

## 1. Route : `/{eventId}/results/…`, pas `/{eventId}/RRPublish/data/…`

La route employée par le plan initial est un **alias hérité**, disponible
seulement sur les épreuves anciennes.

| eventId | `/RRPublish/data/config` | `/results/config` |
| --- | --- | --- |
| 393893, 383326 | 200 | 200 |
| 405215, 406212, 405100 | **404** | 200 |
| les 6 épreuves des façades tierces | **404** | 200 |

La coupure suit l'ancienneté : **toute épreuve de la saison en cours échoue sur
l'alias**. Rumilly répondait par accident d'ancienneté. L'indice était présent
dès le départ — le 301 documenté en tête du module pointait déjà vers `/results/`.

Routes retenues :

```
GET {base}/{eventId}/results/config?page=results
GET {base}/{eventId}/results/list?key=…&listname=…&contest=N&page=results
```

## 2. Base : `my.raceresult.com` est universel

Les façades tierces chargent `//my.raceresult.com/RRPublish/load.js.php` — l'apex
**sans chiffre**. Vérifié : l'apex sert les 9 épreuves du panel en 200, sans
redirection, y compris celles hébergées sur `my2`/`my3`/`my4`.

Conséquence : **aucune résolution de shard n'est nécessaire.** Une seule base,
`https://my.raceresult.com`. Les sous-domaines numérotés restent acceptés en
entrée (une URL collée par un utilisateur peut les porter) mais ne doivent pas
être déduits ni devinés.

## 3. Les listes sont dans `TabConfig.Lists`

`config["lists"]` est **`null`** sur la route canonique, sur les 9 épreuves. Les
listes vivent dans `config["TabConfig"]["Lists"]` : un **tableau plat**, une
entrée par couple (liste, contest), le contest **explicite**.

```json
{"Name": "04 - Classements|Classement général", "Mode": "", "Contest": "3",
 "ShowAs": "Classement général", "Format": "VP", "Live": 0, "ID": "1FECBC"}
```

**Conséquence structurante : le contest n'a plus à être résolu empiriquement.**
Tout l'échafaudage de découverte par essais (`_contest_candidates`, réserve
d'ambiguïté, filet de dernier recours) répond à un problème qui n'existe que sur
l'alias hérité.

## 4. `Mode == "hidden"` est le discriminant — pas `Live`

Le critère `Live` retenu en Task 7 est faux : il avait été calibré sur une seule
épreuve, où il coïncidait avec le bon critère.

| eventId | listes | non-`hidden` | contests | contests couverts par les non-`hidden` |
| --- | --- | --- | --- | --- |
| 393893 | 4 | 4 | 4 | tous |
| 405215 | 35 | 13 | 13 | tous |
| 405100 | 10 | 3 | 3 | tous |
| 406212 | 14 | 7 | 8 | 7 sur 8 |
| 411749 | 13 | 2 | 2 | tous |
| 392745 | 7 | 6 | 2 | 1 sur 2 |
| 409130 | 4 | 3 | 3 | via `Contest="0"` |

`Mode != "hidden"` sélectionne les classements publiés et couvre les contests de
façon quasi exhaustive. À l'inverse, sur 405100 les 10 listes portent `Live=1`, y
compris les trois vrais classements : **le filtre `Live` y vide l'épreuve
entièrement.** `Format` ne discrimine pas davantage.

Deux contests non couverts subsistent (406212 contest 3, 392745 contest 100) :
ils n'ont aucune liste publiée. Absence à la source, pas perte du scraper.

## 5. Mapping des colonnes : l'algorithme du plan est **correct**

Seul son emplacement était faux. `DataFields` est à la **racine du payload**
(`payload["DataFields"]`) ; `payload["list"]["DataFields"]` vaut `null`.

L'algorithme `col = DataFields.index(Field.Expression)` reste exact et reste
nécessaire : `DataFields` compte régulièrement plus d'entrées que `Fields`
(Rumilly 20 vs 18, Genève 22 vs 19), et préfixe toujours `BIB` et `ID`, qui n'ont
pas d'entrée `Fields`. Indexer positionnellement décalerait toutes les colonnes.

`Fields` est bien sous `payload["list"]["Fields"]`.

## 6. Vocabulaire réel des expressions (correctif C-E)

Union observée sur le panel. Le module ne reconnaissait que la colonne de gauche.

| Rôle | Expressions rencontrées |
| --- | --- |
| nom | `AfficherNom`, `LFNAME`, `AfficherNoms`, `ucase([NomRelais])`, `if([Relais]=1;ucase([NomRelais]);[AfficherNom])` |
| temps | `TIME`, `OuStatut([TIME])`, `if([STATUS]<>2;[TIME])`, `TempsOuStatut` |
| rang | `OuStatut([ClassementGénéral.P])`, `OuStatut([AUTORANK.p])`, `ClassementGeneralp` |
| dossard | `BIB`, `DossardBis`, `DisplayBib` |
| club | `CLUB`, `ucase([CLUB])` |
| catégorie | `AGEGROUP.NAMESHORT`, `#[ClassementCatégorie.p][AGEGROUP.NAMESHORT]`, `[AGEGROUP1.NAMESHORT] & iif(…)`, `[CatégorieRelais]` |
| segments | `[Natation]`/`[Swim]`, `[Vélo]`/`[Bike]`, `[Course]`/`[Run]`, `[Transition1]`, `[Transition2]`, chacun possiblement enveloppé de `if([STATUS]<>2;…)` |

Trois formes transverses à gérer :

- **L'enveloppe `if([STATUS]<>2;[X])`** est omniprésente sur les épreuves
  récentes. Sans elle, aucun segment n'est reconnu sur 405215/406212.
- **La casse du suffixe varie** : `.P` et `.p` coexistent. La règle « suffixe `.P`
  ⇒ rang, jamais un temps » tient, à condition d'être insensible à la casse.
- **La concaténation `X & iif(…)`** colle un rang au libellé (`"M (1.)"`,
  `"M0M (1.)"`), comme le faisait déjà `#[…][…]`.

Colonnes à ignorer (bruit d'affichage) : `Icone("photos")`, `[LienPhotos]`,
`CustomFlag`, `NATION.IOCNAME`, `GapTimeTop(…)`, `format(3.6*[CONTEST.LENGTH]…)`,
et toute expression de couleur `iif([SEX]="m";"C(0, 0, 0)";…)`. Ces dernières
produisent des cellules `"C(0, 0, 0)"` en queue de ligne.

**`LFNAME` sérialise `"NOM, PRÉNOM"`** (`"BONNIER, EMMANUEL"`) — format virgulé
que `split_athlete_name` ne gère pas.

## 7. `data` : profondeur variable et groupes qui ne sont pas des statuts

Le plan postulait deux niveaux fixes, le second portant le statut. **Les deux
moitiés de cette affirmation sont fausses.**

| eventId | profondeurs rencontrées |
| --- | --- |
| 405215, 392745 | tableau **plat** |
| 411749, 409130 | 1 niveau |
| 405100 | 2 niveaux |
| 393893, 406212 | **1 et 2 niveaux au sein de la même épreuve** |

Les clés de groupe observées :

- statuts : `#1_`, `#2_Abandons`, `#3_Non Partants`, `#2_Non Partants`,
  `#4_Non Partants`, **`#3_Disqualifiés`** (DSQ — non prévu par le plan) ;
- **sur 406212 : `#1_Masculin`, `#1_Féminin`, `#2_Masculin`** — un groupement par
  **sexe**, pas par statut.

Le numéro de préfixe n'est donc pas un rang de statut stable, et le libellé n'est
pas nécessairement un statut. Deux règles en découlent :

1. **Descendre récursivement** jusqu'aux feuilles, sans présumer la profondeur.
2. **Interpréter le libellé par liste blanche** de jetons de statut connus. Tout
   libellé non reconnu (`Masculin`, `Féminin`) est un groupement neutre : le
   statut reste vide, la ligne est un finisher. Mapper l'inconnu vers DNF/DNS
   marquerait abandonnées 5 des 7 listes de 406212.

## 8. Résolution de l'`eventId` sur les façades (correctif C-D)

Les deux façades servent le même appel, mais **pas la même syntaxe** :

```js
// espace-competition.com — identifiant nu
var rrp=new RRPublish(document.getElementById("divRRPublish"), 411749, "results");

// chronoconsult.fr — identifiant entre guillemets
var rrp = new RRPublish(document.getElementById("divRRPublish"), "392745", "results");
```

L'expression rationnelle doit tolérer les guillemets optionnels et l'espace
variable autour de `new RRPublish`. La fixture `chronoconsult_result_page.html`
utilise à tort la forme d'espace-competition : elle ne teste pas la façade
qu'elle prétend couvrir.

Pages d'épreuve pour de futures fixtures :
`https://chronoconsult.fr/result/<slug>/` et
`https://www.espace-competition.com/index.php?module=sportif&action=resultat&comp_uid=<id>`.

## 9. Métadonnées : le JSON-LD tient

Confirmé sur les 9 épreuves : `GET {base}/{eventId}/results` sert un bloc
`application/ld+json` de type `Event` portant `startDate` (ISO `YYYY-MM-DD`) et
`name`. C'est la seule source de la date d'épreuve — elle n'est dans aucun payload
JSON de l'API.

## 10. Ce qui reste vrai du plan initial

- Le nom de fournisseur `raceresult` et les trois façades.
- L'absence totale de Playwright.
- L'algorithme d'indexation par `DataFields` (§5).
- La règle « suffixe `.P` ⇒ rang » et le collage rang+catégorie.
- Le JSON-LD comme unique source de date (§9).
- **Le besoin d'arbitrer entre plusieurs listes d'un même contest** : 392745 en
  expose 6 sur le contest 1, 409130 en expose 3 sur `Contest="0"`. La fusion et
  la préférence par richesse restent nécessaires — c'est la *découverte* du
  contest qui devient inutile, pas l'arbitrage entre listes.
