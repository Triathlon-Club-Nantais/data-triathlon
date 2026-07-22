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

**Amendé le 2026-07-19, après la branche de correctifs.** Le sondage initial
portait sur 9 épreuves, et cette taille d'échantillon l'a lui-même mis en
défaut : la revue de branche a montré que son §4 était trop fort et que son §6
énumérait des colonnes jamais implémentées. Les amendements portés ici viennent
des mesures de la branche (`.superpowers/sdd/fix-*-report.md`), pas d'un nouveau
sondage. Ils sont signalés par la mention **(amendement)** et déclarent chacun
la portée de la mesure qui les fonde. Les §§ non marqués sont ceux du sondage
d'origine, inchangés et non re-mesurés.

## Épreuves du panel

Les 9 premières lignes sont le panel du sondage d'origine. Les 6 suivantes
**(amendement)** sont les épreuves qui ont mis cette version en défaut ou qui
fondent les §§ 11 et 12 ; elles ont toutes été atteintes par l'apex
`my.raceresult.com`, leur façade d'origine n'a pas été relevée.

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
| 401699 | Half Iron Lac d'Annecy | apex | concaténation imbriquée dans `if(…)` ; rang collé aux segments |
| 406211 | World Triathlon Para Cup, Besançon | apex | **infirme le §4** : seule liste non-`hidden` = liste d'affichage |
| 380823 | Bike & Run de Pontcharra | apex | vocabulaire anglais `Finish.GUN` ; **aucune** liste `hidden` |
| 400001 | Swimrun Côte de Jade | apex | swimrun, 0 segment publié |
| 403144 | Aquaterra (SwimRun L) | apex | swimrun, 0 segment publié |
| 409725 | Swimrun Thonon | apex | swimrun, 0 segment publié |

Les mesures de la branche portent selon les cas sur 12 épreuves (panels
`fix-1` à `fix-4`), 14 (sondes de `fix-1`) ou 17 (panel capturé de `fix-6`,
10 831 participations, 176 691 cellules). Chaque énoncé amendé ci-dessous
nomme la sienne.

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

### 3.1 Le libellé de groupe n'est **pas** un contest **(amendement, revue de branche)**

Le contest de `TabConfig.Lists` fait autorité **dès qu'il est renseigné**. Le
libellé de groupe de niveau 0 de `data` ne doit pas le concurrencer : mesuré, il
n'est un contest que par coïncidence.

| Épreuve | Libellés de niveau 0 | Ce qu'ils sont réellement |
| --- | --- | --- |
| 393893 (Rumilly) | `#1_Distance M` | un contest — d'où la généralisation d'origine |
| 406211 (Para Cup) | `Finish`, `Run - Start` | des **sélecteurs de point de chrono** |
| 409130 (24H Rollers) | `24h DECOUVERTE`, `14H`, `` | une **catégorie**, un contest, rien |
| 380823 (Pontcharra) | `10 Km`, `20 Km` | des contests, corroborés par `contests` |

Le libellé servant **à la fois** de qualifiant de `Course` et de clé de fusion,
s'y fier produit *simultanément* une `Course` fantôme et une duplication de
participations — que `UNIQUE(course_id, bib_number)` ne bloque pas, les `Course`
étant distinctes. **La perte est silencieuse.** Mesuré sur 409130 : 3 `Course`,
302 dossards présents dans plusieurs d'entre elles, dont 370 lignes rangées sous
le `Name` de liste `03-Qualifs|Classement Qualifs`.

**Règle retenue**, et pourquoi elle est globale :

1. `Contest != "0"` → `contests[contest]`, sans consulter le groupe. Repli
   `f"Contest {n}"` si la table l'ignore — jamais le `Name` de liste.
2. `Contest == "0"` (« toutes catégories », le seul cas sans contest donné) → on
   consulte le groupe **seulement si tous** les libellés de niveau 0 des listes
   `Contest="0"` de l'épreuve sont des valeurs de `contests`.
3. Sinon, aucun qualifiant : une `Course` unique, où la fusion par dossard
   dédoublonne au lieu de dupliquer.

Le point 2 est **tout ou rien à l'échelle de l'épreuve**, et ce n'est pas un
excès de prudence : sur 409130 `14H` *est* une valeur de `contests`, mais les 72
dossards de `24h DECOUVERTE` sont **tous** inclus dans les 456 de `14H`. Une
corroboration libellé par libellé les aurait laissés dans deux `Course` à la
fois. Un seul libellé étranger révèle un axe d'affichage, pas la partition en
contests, et disqualifie donc le groupement entier.

Effet mesuré (avant → après) : 409130 3 `Course` / 302 dossards dupliqués → 1 / 0 ;
406211 2 `Course` de points de chrono → 10 contests réels ; 380823, 393893,
401699, 405215 **inchangées à l'octet**.

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

Sur ces 7 épreuves, `Mode != "hidden"` sélectionne les classements publiés et
couvre les contests de façon quasi exhaustive. À l'inverse, sur 405100 les
10 listes portent `Live=1`, y compris les trois vrais classements : **le filtre
`Live` y vide l'épreuve entièrement.** `Format` ne discrimine pas davantage.

Deux contests non couverts subsistent (406212 contest 3, 392745 contest 100) :
ils n'ont aucune liste publiée. Absence à la source, pas perte du scraper.

### 4.1 Correction **(amendement)** : critère nécessaire, pas suffisant

L'énoncé « `Mode != "hidden"` sélectionne les classements publiés » était une
généralisation de 7 épreuves. **406211 l'infirme** (mesuré dans `fix-3`) :

| liste | `Mode` | `Contest` | lignes | rôle `temps` | segments |
| --- | --- | --- | --- | --- | --- |
| `01-Classements\|Classement général` | **`hidden`** | `0` | 33 | **oui** | Swim, T1, Bike, T2, Run |
| `01-Résultats en ligne\|LIVE` ×13 | `''` | 1..13 | 42 au total | non | aucun réel |
| `01-Résultats en ligne\|Concurrents` | `hidden` | `0` | 4 | non | — |

La polarité y est **inversée** : le vrai classement est `hidden`, et les seules
listes non-`hidden` sont des listes d'affichage `{Selector.Splits}`. Énoncé
correct :

> `Mode != "hidden"` marque ce que l'organisateur a choisi de publier. C'est
> une condition **nécessaire** pour qu'une liste soit retenue, **pas
> suffisante** pour qu'elle soit un classement : une liste d'affichage peut
> être non-`hidden`, et un classement complet peut être `hidden`.

Portée : mesuré sur 12 épreuves (panel `fix-3`), une seule présente
l'inversion. La règle empirique tient donc sur 11 des 12 — ce qui est
précisément la raison pour laquelle 7 épreuves ne suffisaient pas à la
valider.

**Conséquence dans le moteur** : la sélection reste bornée aux listes
non-`hidden`, et l'insuffisance du critère est compensée en aval, à
l'exécution, par l'arbitrage entre listes (`_prefer`/`_richness`) et par la
reconnaissance de `FinishResult.TEXT` (§6.2) — pas par un critère de sélection
plus fin.

### 4.2 L'élargissement aux listes `hidden` est **différé**, ni réfuté ni clos

Fusionner les listes `hidden` avec les listes publiées a été mesuré sur 406211
(`fix-3`) : la fusion par `(libellé de contest, dossard)` ne trouve **aucune
clé commune** entre les deux familles — `'PTS5 Men'` d'un côté, `'PTS5 M'` de
l'autre — d'où **79 lignes au lieu de 42**, soit 37 doublons, et autant de
`Course` fantômes en aval.

Ce que cette mesure établit est un **préalable**, pas une impossibilité :
l'élargissement exige d'abord une **réconciliation des libellés de contest**.
Décision humaine du 2026-07-19 : l'élargissement est **différé en ticket**
derrière ce préalable. Ne pas lire ce paragraphe comme « instruit et clos ».

Conséquence assumée et mesurée : 406211 récupère ses 42 temps mais sort avec
**0 segment**, alors que sa liste `hidden` publie Swim/T1/Bike/T2/Run pour
33 participants. Ce n'est pas une régression (la ligne de base était déjà 0),
c'est de la donnée réelle non captée.

**Second verrou sur la même route** (mesuré sur 410891, `fix-4`) : cette
épreuve porte 111 splits réels sur 122 lignes, mais dans une liste `hidden`
**et** au format `'2:05:29 (2)'` — rang entre parenthèses **sans point**, donc
non décollé par `_RE_RANG_SUFFIXE_STRICT` (§12.2) et rejeté par `_RE_DUREE`.
L'élargissement aux `hidden` **ne suffirait donc pas seul** sur cette épreuve :
il y a deux verrous, pas un.

Contre-exemple utile, du même relevé : sur 411749 les colonnes de split des
listes `hidden` existent mais sont **entièrement vides** (0 valeur sur 172 et
226 lignes). L'élargissement n'y changerait rien. Les listes `hidden`
contiennent parfois de la donnée, parfois des colonnes préparées et jamais
alimentées ; rien dans le panel ne permet de dire laquelle est la règle.

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

**(amendement)** Ces enveloppes se **composent**, et c'est ce que la version
initiale n'avait pas vu. Deux conséquences mesurées sur 401699 (Half Iron Lac
d'Annecy), qui passait de 0 à 456/587 participants avec segments une fois les
deux traitées :

- Le dépelage doit être un **point fixe**, pas une séquence d'étapes appliquée
  une fois dans un ordre fixe : une concaténation imbriquée dans un `if(…)`
  n'est autrement jamais repelée. La borne d'itérations n'est **pas**
  inatteignable — un `if(cond;…)` imbriqué ne libère qu'un niveau par tour, donc
  11 niveaux la dépassent. Mesuré, et verrouillé par test.
- Le rang peut être collé **à la valeur de segment** (`'2:08:00 (1.)'`), pas
  seulement au libellé de catégorie. Il doit être décollé **avant**
  qualification de la durée — sous la forme à point exigé (§12.2).

Colonnes à ignorer (bruit d'affichage), **observées** : `Icone("photos")`,
`[LienPhotos]`, `CustomFlag`, `NATION.IOCNAME`, `GapTimeTop(…)`,
`format(3.6*[CONTEST.LENGTH]…)`, et toute expression de couleur
`iif([SEX]="m";"C(0, 0, 0)";…)`. Ces dernières produisent des cellules
`"C(0, 0, 0)"` en queue de ligne. **Cette liste est un relevé, pas une
description de ce que le module implémente** : cf. §6.1.

**`LFNAME` sérialise `"NOM, PRÉNOM"`** (`"BONNIER, EMMANUEL"`) — format virgulé
que `split_athlete_name` ne gère pas.

### 6.1 Ce qui est réellement exclu **(amendement)**

La version initiale de ce §6 laissait entendre que les sept formes ci-dessus
étaient écartées par le module. Elles ne l'étaient pas ; la revue de branche
l'a relevé, et `fix-6` (I3) a tranché. État réel, mesuré sur le panel de
17 épreuves :

| Forme | Exclue explicitement ? | Statut mesuré |
| --- | --- | --- |
| `CustomFlag` | oui (égalité exacte) | **corrige un défaut actif** — 27 listes, 766 cellules ; entrait bien dans `segments` |
| `[LienPhotos]` | oui (égalité exacte) | défensive — 13 listes, mais jamais dans `list.Fields`, seulement dans `DataFields` |
| `NATION.IOCNAME` | oui (égalité exacte) | défensive — le point la fait déjà rejeter par la forme |
| `Icone("photos")` | oui (préfixe) | défensive — la parenthèse la fait déjà rejeter |
| `GapTimeTop(…)` | oui (préfixe) | défensive — idem, 16 variantes relevées |
| `format(3.6*[CONTEST.LENGTH]…)` | **non** | écartée par la seule forme, mais **pas par la parenthèse** — cf. ci-dessous |
| expressions de couleur `iif(…)` | **non** | écartées par la seule forme, mais **pas par la parenthèse** — cf. ci-dessous |

**Rectificatif (revue de branche)** : les deux dernières lignes portaient une
explication fausse (« écartée par la seule forme (parenthèse) »). Le verdict —
exclue — est juste, le mécanisme ne l'était pas, et c'est le mécanisme que les
tâches futures citeront.

`format` **et** `iif` sont l'un et l'autre dans `_RE_ENROBAGE`
(`raceresult.py:228-230`) : `_peel` leur **retire** donc la parenthèse au lieu
de buter dessus. Mesuré à l'exécution :

| Expression | Après `_peel` | Ce qui la rejette réellement |
| --- | --- | --- |
| `format(3.6*[CONTEST.LENGTH];"0.0")` | `3.6*contest.length` | le point et l'astérisque (`_RE_TOKEN_SIMPLE`) |
| `iif([X]>1;"red";"blue")` | `"blue"` | les guillemets (`_RE_TOKEN_SIMPLE`) |
| `Icone("photos")` | `icone("photos")` | la parenthèse — ici l'explication d'origine **est** juste |

`Icone(` n'étant pas un enrobage, sa parenthèse survit : c'est le seul des trois
cas où le mécanisme annoncé était le bon. La différence n'est pas cosmétique —
elle dit que la parenthèse n'est *pas* un critère de rejet général, puisque tout
enrobage reconnu la fait disparaître.

**Piège à ne pas reproduire**, relevé sur une 1re version de ce rectificatif :
`_RE_LITTERAL` *matche* bien `"blue"`, mais **elle n'est jamais consultée sur ce
chemin**. Elle ne sert qu'à l'étape 1 de `_peel` (`raceresult.py:322`), au
découpage sur `&`. La colonne est qualifiée plus loin, dans `_map_columns`
(`:729`), où le seul filtre de forme est `_RE_TOKEN_SIMPLE` — ce sont donc les
guillemets, refusés par cette regex, qui écartent l'expression. Citer une regex
qui matche mais ne s'exécute pas, c'est refaire à échelle réduite l'erreur que ce
rectificatif corrige : **vérifier le chemin d'appel, pas seulement le prédicat.**

Trois précisions qui appartiennent à la vérité de référence :

- L'exclusion porte sur l'**expression pelée**, pas sur le libellé affiché.
- Elle n'est consultée que sur la branche « candidat au rôle de segment » :
  une colonne qui obtient d'abord un rôle via la reconnaissance de vocabulaire
  n'est pas écartée. Inerte aujourd'hui, non garanti par construction.
- Les colonnes exclues partent en `raw_data`, elles ne sont pas jetées.
  Prix mesuré : 592 participations sur 10 831 gagnent une clé
  `raw_data['CustomFlag']` vide.

**Deux colonnes de même nature restent hors liste** : `ChampionOrTeamJersey`
(179 cellules) et `TeamJersey` (17), des maillots `[img:…]` sur 392745.
Neutralisées par leur seule valeur, comme l'était `CustomFlag` avant I3.
Signalées, non traitées.

### 6.2 Vocabulaire du temps : règle de forme et anglais **(amendement)**

Le relevé initial (`TIME`, `OuStatut([TIME])`, `if([STATUS]<>2;[TIME])`,
`TempsOuStatut`) était franco-centré. Deux défauts in-domaine s'en sont suivis,
tous deux mesurés :

- **380823** (Bike & Run de Pontcharra) ne publie que `Finish.GUN` :
  58/58 participants sortaient sans `total_time`, alors que `raw_data` portait
  `'Finish.GUN': '31:27'`. Après correctif : 58 → 3 sans temps, et les 3
  restants sont des `DNS` vérifiés (dossards 70, 165, 167).
- **406211** publie son chrono sous
  `switch([{Selector.Splits}.NAME]=[Finish.NAME];[FinishResult.TEXT];…)`,
  pelé en `finishresult.text` : 42/42 sans temps → 0.

Formes de temps à reconnaître, telles qu'implémentées :

| Forme | Rôle obtenu |
| --- | --- |
| `temps` nu (égalité exacte), `TempsOuStatut`, `TIME`, `OuStatut([TIME])`, `if([STATUS]<>2;[TIME])` | `temps` |
| `(temps\|arrivee\|finish).(gun\|chip)` — ancré, alternations **fermées** | `temps` |
| `(temps\|arrivee\|finish).text` | `temps_texte` (dernier recours) |
| `finishresult.text` — racine à part, appariée à son **seul** suffixe | `temps_texte` |

Priorité **chip > gun > texte**. Chip et gun sont deux temps officiels
réellement observés (`Arrivée.*` sur 411749 et 410891) ; `.text` ne l'a jamais
été sous ces trois racines — la branche existe pour combler un vide, jamais
pour déclasser une mesure.

Ce qui **n'est pas** couvert, volontairement : `finishresult.gun` et
`finishresult.chip` ne sont pas reconnus (racine appariée à un seul suffixe).
Aucun n'a jamais été observé ; une épreuve qui en publierait verrait la valeur
partir en `raw_data` — visible et récupérable, plutôt que promue en silence.

Branches **non confirmées sur trafic réel** : `.text` sous les trois racines
`temps`/`arrivee`/`finish`, et `Temps.*` / `temps` nu. Elles ont été écrites
pour anticiper l'inconnu, avec un ordre de priorité qui borne le risque ; elles
ne sont adossées à aucune mesure.

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
   statut reste vide, la ligne est un finisher.

> **(amendement)** La première version de ce § justifiait la liste blanche par
> « mapper l'inconnu vers DNF/DNS marquerait abandonnées 5 des 7 listes de
> 406212 ». **C'est faux, et l'énoncé est retiré** : aux profondeurs réellement
> observées, la construction du résultat retombe déjà sur un statut vide, donc
> la liste blanche est **redondante**. Elle est conservée pour l'héritage
> statut → sexe et comme garde de robustesse, et testée comme telle — une
> propriété explicitement **non observée**, pas un correctif.

## 8. Résolution de l'`eventId` sur les façades (correctif C-D)

Les deux façades servent le même appel, mais **pas la même syntaxe** :

```js
// espace-competition.com — identifiant nu
var rrp=new RRPublish(document.getElementById("divRRPublish"), 411749, "results");

// chronoconsult.fr — identifiant entre guillemets
var rrp = new RRPublish(document.getElementById("divRRPublish"), "392745", "results");
```

L'expression rationnelle doit tolérer les guillemets optionnels et l'espace
variable autour de `new RRPublish`.

**(amendement)** Ce § signalait que la fixture `chronoconsult_result_page.html`
utilisait à tort la forme d'espace-competition. **Corrigé depuis** : elle porte
la forme quotée. Le constat est conservé pour mémoire, il n'est plus d'actualité.

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

## 11. Segments : panel et comptes **(amendement)**

`AGENTS.md` renvoie à ce § pour le panel et les chiffres. Toutes les valeurs
ci-dessous viennent des mesures de `fix-4`, moteur exécuté tel quel via
`scrape_event_all` sur l'apex, en série avec 3 s de délai.

### 11.1 Les épreuves qui remontent des segments

| eventId | participants | avec segments | max segments | segments observés |
| --- | --- | --- | --- | --- |
| 393893 Rumilly | 874 | 734 | 5 | Nat., T1, Vélo, T2, CAP |
| 405215 Genève | 4226 | 4060 | 5 | Natation, T1, Vélo, T2, Course |
| 383326 Roanne | 128 | 120 | 2 | Natation, Course |
| 406212 Besançon | 348 | 315 | 5 | Natation, T1, Vélo, T2, Course |
| 401699 Annecy | 587 | 456 | 3 | Nat. + T1, Vélo, Course + T2 |

**Maximum observé : 5 segments.** `services/mapping.build_splits` est
déplafonné pour les scrapers qui renseignent `segments` — c'est une propriété
du **code**, vérifiée par lecture, **jamais une observation** : aucune épreuve
du panel n'expose plus de 5 segments. Ne pas en déduire qu'un swimrun
multi-legs conserverait toutes ses étapes ; rien ne le mesure.

### 11.2 Les 9 épreuves à zéro segment, et leur cause exacte

Cause **unique et uniforme** sur les neuf : **aucune liste publiée ne porte de
colonne de split**. Les correctifs C2/C3 n'en expliquaient aucune — il n'y
avait rien à expliquer, et aucun défaut du moteur n'est établi ici.

La portée de cet énoncé est celle de la mesure : ce qui a été inspecté est le
contenu des listes **publiées** (non-`hidden`), les seules que le moteur
atteint. « La source ne publie pas de segment » serait une affirmation plus
large, et elle est fausse en général — §4.2 montre sur 410891 qu'une liste
`hidden` peut porter un split réel et renseigné. D'où la colonne de portée :

| eventId | épreuve | part. | segments | listes `hidden` |
| --- | --- | --- | --- | --- |
| 400001 | Swimrun Côte de Jade | 281 | 0 | **ouvertes** — pas de table de segments |
| 403144 | Aquaterra (SwimRun L) | 1483 | 0 | **ouvertes** — pas de table de segments |
| 411749 | Mad'Trail 2026 | 398 | 0 | **ouvertes** — colonnes de split présentes mais **entièrement vides** |
| 410891 | Trail de la Ciboule | 517 | 0 | **ouvertes** — **un split réel y existe**, hors d'atteinte (§4.2) |
| 409725 | Swimrun Thonon | 83 | 0 | **non ouvertes** |
| 405100 | La Foulée Agésinate | 456 | 0 | **non ouvertes** |
| 392745 | ∆EH Tour of Hellas | 95 | 0 | **non ouvertes** |
| 409130 | 24H Rollers du Mans | 898 | 0 | **non ouvertes** |
| 380823 | Bike & Run de Pontcharra | 58 | 0 | **inexistantes** — seule épreuve où « la source ne publie pas de segment » est établi sans réserve |

Ce que la table établit : **le moteur ne perd aucun segment atteignable** sur
ces 9 épreuves. Ce qu'elle n'établit pas : que ces épreuves soient dépourvues
de segments à la source. Pour les quatre « non ouvertes », rien n'a été
regardé.

### 11.3 Ce que le moteur écarte, et sur quel critère

Sur ces épreuves, des colonnes sont bien retenues comme *candidates* segment
(`Noms`, `Cat.`, `Pén.`, `Licence`, `Km/H`, `Tours`, `Distance`, `Nation`,
`Jersey`, `Classement J1`, `Equipiers`) puis rejetées **ligne à ligne par la
valeur** (`_RE_DUREE`), pas par l'étiquette. Fait mesuré : aucune ne ressort en
segment. Le bien-fondé du rejet est vérifié sur les valeurs relevées
(`'447.795'`, `'107'`, `'Masculin (1.)'`, `'2722273'`, `'43 pt'`…) ; pour
`Pén.`, `Classement J1` et `Jersey`, aucune valeur n'a été relevée — les juger
sur leur étiquette est une **inférence non vérifiée**.

## 12. Défauts connus et non fermés **(amendement)**

Aucun n'est un manque d'instruction : chacun a été mesuré, puis laissé ouvert
par un arbitrage explicite.

### 12.1 `OuStatut([Temps])` traverse sans garde de durée

Le rôle `temps` est plus large que les seuls chip/gun : `tempsoustatut` figure
dans la table d'égalités exactes et `OuStatut(…)` est un enrobage pelé. La
valeur promue en `total_time` par ce chemin **ne passe donc aucune garde de
durée**. Pré-existant aux correctifs, mesuré **latent** : 0 valeur non-durée
sur les 12 épreuves du panel `fix-3`. Remède identifié, non appliqué : qualifier
par « `normalize_time` a reconnu la valeur » plutôt que par `_RE_DUREE`.

À ne pas confondre avec le repli `.text`, qui, lui, **est** gardé par
`_RE_DUREE` — garde volontairement plus stricte que `normalize_time`, laquelle
lit des formes comme `1h23'45` que `_RE_DUREE` rejette.

### 12.2 Le décollage de rang exige le point : angle mort concédé sciemment

Le rang suffixé n'est décollé de `nom`/`club`/`temps`/`segments` que sous la
forme `(5.)`, **point exigé** ; `(2)` survit. Motif, mesuré : la règle
permissive amputait des valeurs légitimes (`'TRIATHLON CLUB NANTAIS (44)'`) et
fusionnait deux équipes distinctes (`'TCN (1)'` / `'TCN (2)'`). La forme sans
point n'était attestée sur aucune des 14 épreuves alors sondées ; la parenthèse
légitime, si.

Arbitrage : une erreur **bruyante et réversible** (split perdu, valeur brute
visible) préférée à une faute **muette et irréversible** (identité mutilée,
entités fusionnées). L'angle mort s'est depuis matérialisé sur une épreuve
réelle — 410891, `'2:05:29 (2)'` (§4.2) — sans invalider l'arbitrage, mais il
n'est plus hypothétique.

La règle permissive reste employée pour `sexe` et `categorie`, dont les
vocabulaires sont fermés.

### 12.3 Découpage des noms d'équipe

`split_athlete_name` est appelé **sans condition** sur la cellule `nom` du
scraper. Quand la source y met un nom d'équipe, l'identité est mutilée et
persistée telle quelle : `nom='GUILLAUME', prenom='& ANTHONY'` (403144),
`nom='Associés', prenom='Les Inconnus'` (380823). **19 identités** mesurées sur
17 épreuves / 10 831 participations.

Non trivial, d'où le ticket plutôt que le correctif : `split_athlete_name` est
partagé par tous les scrapers, et des noms de personnes légitimes portent `/`
ou `-`.

**Corrigé (#63).** `_build_result` ne découpe plus une cellule « nom » reconnue
comme nom d'équipe : garde par valeur (`&`) + garde par colonne (expression
source `NomRelais`/`NomEquipe`/`AfficherNoms` non conditionnelle). Le nom entier
va dans `nom`, `prenom` vide. `split_athlete_name` (partagé) reste intact.
Détail : `2026-07-22-raceresult-noms-equipe-design.md`. Angle mort assumé et
**loggé** : un nom d'équipe sans `&` servi par une colonne conditionnelle
(`if([Relais]=1;ucase([NomRelais]);[AfficherNom])`) échappe aux deux gardes ;
`scrape_event_all` le signale (`logger.warning`, « angle mort #63 »).

### 12.4 `is_relay` n'est **pas** la cause des `Athlete` d'équipe

L'hypothèse « `is_relay` mal détecté ⇒ `Athlete` fantômes via
`UNIQUE(nom, prenom, birth_date)` » est **infirmée dans sa forme causale**. Le
fondement est la **lecture du chemin de code**, pas une expérience :

- `_build_result` appelle `split_athlete_name` sans condition, et n'affecte
  `is_relay` qu'**après** ;
- `mapping.get_or_create_athlete` ne reçoit ni ne lit `is_relay` ;
- hors `scrapers/`, `is_relay` n'alimente que `Participation.is_relay` et
  `Course.is_relay`.

Même avec une détection de relais parfaite, le nom d'équipe serait découpé à
l'identique. La mutilation (§12.3) est un défaut distinct, désormais corrigé
(#63, cf. §12.3).

**Ne pas refonder ce verdict sur l'expérience du panel réimporté avec
`is_relay` forcé à `True`** : elle est dégénérée. `is_relay` entre dans
`UNIQUE(name, event_date, event_type, is_relay)`, donc un basculement uniforme
préserve la partition **par construction** et ne teste rien. L'élargissement
mesuré ensuite en version *partielle* (383 lignes basculées sur 10 courses) n'a
produit ni scission ni redistribution — mais c'est un résultat **de panel**,
pas une propriété structurelle.

**À lire avant tout élargissement de la détection de relais** : l'absence de
scission de `Course` supposerait `qualify_event_name` injective en son
qualifiant. Elle ne l'est pas — elle court-circuite la qualification quand le
qualifiant est déjà contenu dans le nom d'épreuve. Contre-exemple vérifié à
l'exécution : `"Duo & Trio de X"` avec les contests « Duo » et « Trio » rend la
même identité de course, tandis qu'un vocabulaire élargi donnerait des
`is_relay` divergents → `Course` scindée, participations redistribuées sous
`UNIQUE(course_id, bib_number)`. Vérification à faire sur le corpus visé :
chercher les épreuves dont **deux** libellés de contest sont contenus dans le
nom d'épreuve.

## 13. Angles morts — ce que ce document ne dit pas **(amendement)**

Cette liste a la même valeur que celle des faits. Ce qui suit n'a **pas** été
regardé, ou l'a été trop peu pour fonder quoi que ce soit.

**De portée du panel :**

1. **Rien hors de France**, sauf 392745 (Grèce) et 406211 (épreuve
   internationale en France). Aucune conclusion de ce document ne porte sur le
   monde ; RaceResult est un produit allemand à diffusion européenne.
2. **Rien avant 2024, rien en cours de déroulement.** La coupure du §1 suit
   l'ancienneté : elle a été mesurée, mais son bord exact n'est pas connu.
3. **Les deux façades tierces n'ont été confrontées qu'à 2 épreuves chacune.**
   Leur résolution d'`eventId` est vérifiée (§8) ; leur comportement d'API l'est
   par l'apex, pas par la façade.
4. **Aucun balayage exhaustif d'`eventId`** : la tentative de la revue est
   tombée sur un rate-limit RaceResult. Sonder **en série, ~3 s de délai**.

**De portée des mesures :**

5. **Les listes `hidden` de 409725, 405100, 392745 et 409130 n'ont jamais été
   ouvertes** (§11.2). Pour ces quatre épreuves, on ne sait pas ce que la source
   publie hors des listes publiées.
6. **Aucune épreuve mesurée n'expose plus de 5 segments** (§11.1) : le chemin
   déplafonné de `build_splits` n'est exercé par aucune donnée réelle.
7. **Aucune épreuve mesurée n'expose les branches `.text` sous
   `temps`/`arrivee`/`finish`, ni `Temps.*`** (§6.2).
8. **La branche DNF du repli `.text`** n'est exercée par aucune donnée réelle du
   panel : test unitaire négatif seulement.
9. **Les gardes i18n resserrées ne sont exercées par aucune donnée du panel** :
   0 écart entre l'ancienne règle et la nouvelle sur 176 691 cellules et
   834 libellés. Elles protègent de formes **non observées**.
10. **Aucune recherche active de collisions de fusion** entre listes, ni de
    représentativité des fixtures.
11. **Les mesures réseau de ce document ne sont pas rejouables** : aucun script
    ni trace de sonde n'est versionné. Une seule a été revérifiée
    indépendamment (380823).

**De portée du domaine :**

12. **392745 (course cycliste à étapes) est hors domaine triathlon** et le
    reste : 95 lignes sans temps ni statut, vocabulaire GC (maillots, écarts
    d'équipe) volontairement non traité.
13. **409130 (24H Rollers)** publie 826/898 lignes sans chrono, légitimement
    (listes d'inscrits et de qualifs). Conséquence réelle : ces `Course`
    basculent « en cours » pour `cache.is_fresh` → TTL 10 min, donc
    re-scraping perpétuel. Non corrigé, à arbitrer.
14. **Genève (405215)** : club renseigné sur 132/4226 lignes seulement. À
    vérifier **à la source** avant de conclure à un défaut de mapping ; ce n'a
    pas été fait.

**Nommés par la revue complète de branche (amendement) :**

15. **Une clé de groupe de niveau 0 qui serait un statut.** `_iter_groups`
    (`raceresult.py:799-802`) traite inconditionnellement la profondeur 0 comme
    un contest : un `{'#2_Abandons': […]}` produirait `contest="Abandons",
    statut=""` — le statut est **perdu**. Le relecteur a sondé les 9 épreuves du
    panel d'origine : **aucune clé de niveau 0 reconnue comme statut**. Latent.
    *Portée réduite par le §3.1* : la moitié « `Course` fantôme » du défaut est
    désormais fermée par construction — à `Contest != "0"` le libellé de groupe
    n'est plus consulté, et à `Contest == "0"` un `Abandons` absent de `contests`
    disqualifie le groupement. Il ne reste que la perte du statut.

    **Corrigé (issue #64)** : la garde de vocabulaire à la profondeur 0 est bien
    posée, mais **croisée avec `contests`** — un libellé n'est reclassé en statut
    que s'il est reconnu par `derive_status_from_label` **et** absent de
    `contests`. Ce croisement lève précisément l'objection ci-dessus : un contest
    légitimement nommé d'après un jeton de statut figure dans `contests`, il reste
    un contest ; seul un statut étranger aux contests (jamais un vrai contest) est
    reclassé. La reclassification ne peut pas dégrader `_groupes_zero_fiables` : un
    libellé absent de `contests` disqualifiait déjà `fiable_zero`. Design :
    `2026-07-22-raceresult-statut-niveau-0-design.md`.
16. **`split_athlete_name` (`utils.py:96-125`) est partagé et sa sémantique a
    changé** en tâche 1 : « Jean DE LA TOUR » passe de `("TOUR", "Jean DE LA")` à
    `("DE LA TOUR", "Jean")`. **Wiclax et TimePulse l'appellent aussi.** Un
    `rescrape-db` peut donc créer des `Athlete` doublons sous
    `UNIQUE(nom, prenom, birth_date)` pour les patronymes composés **déjà en
    base**. Jamais analysé : `task-1-report` concluait « aucune régression » sur
    la seule foi d'une suite verte, ce qui ne dit rien des données persistées.
    **Vérification à faire avant tout re-scrape de masse** : requêter les
    `Athlete` existants dont `nom` ou `prenom` porte plusieurs tokens en
    majuscules, et mesurer combien changeraient de clé.
17. **Une épreuve mêlant des listes `Contest="0"` et `Contest!="0"`** n'a été
    rencontrée sur aucune épreuve sondée. Les lignes des premières y sortiraient
    sans qualifiant tandis que les secondes seraient nommées : rien ne garantit
    qu'aucun dossard ne se retrouve dans les deux. Le §3.1 n'est **pas** vérifié
    sur cette forme.

    **Suivi #65** : cette forme mixte est désormais **épinglée par des tests de
    caractérisation** (`test_scrape_event_all_mixte_contest_zero_*`), qui figent
    le comportement actuel — voie `!="0"` qualifiée, voie `"0"` corroborée ou
    repliée sur le nom nu. Ils détecteront toute dérive future ; ils ne
    **valident** rien, faute d'épreuve réelle.
18. **Le critère du §3.1 est fondé sur 2 épreuves en `Contest="0"`** (409130,
    380823), soit toutes celles du panel — mais deux seulement. Le caractère
    « tout ou rien » est le comportement correct sur ces deux-là ; il n'est pas
    établi au-delà.
19. **Le repli « aucun qualifiant » du §3.1 porte son propre risque silencieux,
    et c'est l'angle mort symétrique du défaut qu'il corrige.** Le point 3 range
    toutes les lignes d'une épreuve `Contest="0"` non corroborée dans une `Course`
    unique. Si une telle épreuve avait à la fois un libellé étranger (qui
    disqualifie le groupement) **et** des contests réellement disjoints se
    partageant des dossards, la non-qualification les fusionnerait : `_prefer`
    arbitrerait alors entre deux personnes différentes portant le même dossard,
    et en écraserait une **sans trace**.

    Sur 409130 c'est sans effet — union = 529 = autant de personnes distinctes,
    **mesuré**. Mais c'est une propriété de cette épreuve, **pas une garantie de
    construction** : rien dans le code ne détecte ce cas.

    Le choix reste le bon : il échange une duplication **prouvée** (302 dossards
    sur une épreuve réelle) contre une collision **jamais observée**. Mais les
    deux branches du §3.1 sont silencieuses, et il serait malhonnête de n'en
    déclarer qu'une. Signal à guetter si le cas se matérialise : un import dont
    le total de participants est nettement inférieur à la somme des lignes
    publiées, sans doublon apparent.

    **Suivi #65** : ce signal est désormais **émis** — `scrape_event_all` loggue
    un `warning` quand une clé de fusion écrase deux identités d'athlète
    distinctes (`_identites_incompatibles`). L'angle mort est rendu **observable**,
    pas fermé : le comportement de fusion reste inchangé (le compromis du §3.1
    reste le bon). Muet sur tout le panel réel, le signal ne se déclenche que sur
    la forme non observée décrite ici.
