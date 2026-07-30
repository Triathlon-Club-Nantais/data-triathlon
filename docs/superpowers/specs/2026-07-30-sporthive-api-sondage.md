# MYLAPS Sporthive — sondage de l'API réelle

Issue : [#53](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/53)
(sous-issue de #33, section B). Sondage effectué le **30/07/2026**.

Ce document est la **vérité de terrain** : il prime sur l'énoncé de l'issue, sur
le design et sur le plan. Toute divergence se tranche en re-sondant, pas en
raisonnant.

## Ce que l'issue annonçait, et ce qui est faux

L'issue #53 décrit une API qui **n'existe plus** — son host ne résout même pas.

| Énoncé de l'issue | Observation du 30/07/2026 |
| --- | --- |
| `GET eventresults-api.sporthive.com/api/events/{e}/races/{r}/classifications/search` | **Faux.** `eventresults-api.sporthive.com` est en **NXDOMAIN**. L'API vit sur `eventresults-api.speedhive.com`, préfixe `/sporthive/`, et la route `classifications/search` n'existe pas (404). |
| « pagination par offset, `count=50&offset=0` » | **Faux.** Pagination par `page`/`size`, et `size` est **plafonné à 10** (400 explicite au-delà). Aucun `offset`, aucun export en masse. |
| « `scrape()` + `scrape_event_all()` » | Hors convention actuelle : `scrape_event_all()` est **la seule** voie d'import (cf. AGENTS.md, « Conventions scrapers »). |
| `results.sporthive.com` comme host | Exact mais incomplet : ce host **redirige en 307** vers `sporthive.com/events/s/{id}`. Les deux sont à déclarer. |

Le reste tient : l'API est publique, sans authentification, sans clé, CORS
ouvert, et **aucun Playwright n'est nécessaire** — il n'a servi qu'à découvrir
les appels, la page elle-même étant une SPA Vue au HTML vide.

## Panel sondé

11 événements, 6 pays, 2 familles d'identifiants, 2 sports. 400 requêtes au
total sur les trois passes ; 678 participants lus **exhaustivement** (5 courses
entières), ~2 850 échantillonnés.

| Identifiant | Événement | Pays | Date | Courses | Classés |
| --- | --- | --- | --- | --- | --- |
| `7191895923677191680` | Triathlon de Vertou 2024 | FR | 05/05/2024 | 5 | 504 |
| `7237009246536171776` | Triathlon Sud Vendée | FR | 21/09/2024 | 6 | 978 |
| `bdea2f10-…-ef7f1926a06f` | 2026 Europe Triathlon Junior Cup Izvorani | RO | 18/07/2026 | 3 | 93 |
| `7231281843239281664` | Finishers Triathlon Knokke Heist | BE | 25/08/2024 | 2 | 493 |
| `7338183832632903680` | Tri Amsterdam 2025 | NL | 15/06/2025 | 8 | 3 137 |
| `7316756412581806080` | East Fife Tri Festival 2025 | GB | 13/04/2025 | 7 | 321 |
| `6950078574858030336` | London Triathlon 2022 | GB | 07/08/2022 | 8 | 3 389 |
| `6952284220845495552` | ACCURO Jersey Triathlon | UK | 17/07/2022 | 8 | 344 |
| `7183110323454187008` | NN Marathon Rotterdam 2024 | NL | 13/04/2024 | 10 | 43 212 |
| `7239978275824695296` | Obvion Run 2024 | NL | 15/09/2024 | 6 | 1 442 |
| `231903c7-…-2694dbdafa8f` | MASAFAT Relay Race | SA | 31/07/2026 | 8 | 0 |

**Vertou 2024 est le cas de référence** : 10 km de Nantes, **37 participations
« TRI CLUB NANTAIS »** — libellé déjà dans la liste blanche de
`app/core/club.py`. C'est sur lui et sur Sud Vendée que portent les mesures
exhaustives ci-dessous.

Deux mises en garde sur le panel :

- **Vertou a changé de chronométreur** : depuis 2025 l'épreuve est chez Chronos
  Metron (Wiclax, déjà supporté). Sporthive ne couvre ici que les éditions
  ≤ 2024. Ne pas conclure d'un panel FR étroit que le provider est marginal —
  MYLAPS est international, et l'API est la même partout.
- **`countryCode` n'est pas fiable comme code ISO** : `UK` pour Jersey (contre
  `GB` pour East Fife), et côté participant `country` mélange ISO-2 (`NL`, `IL`)
  et ISO-3 (`FRA`). Non consommé par `ScrapedResult`, donc sans conséquence,
  mais à ne pas recycler en clé.

## Les URLs

Le routeur Vue (extrait du bundle `main.js`) déclare exactement quatre formes
sous `/events` :

```
/events/:eventId                     ← Speedhive motorisé, PAS Sporthive
/events/s/:eventId
/events/s/:eventId/race/:raceId
/events/s/:eventId/race/:raceId/bib/:bibId
/events/s/:eventId/race/:raceId/team/:teamId
```

Le `s` de `/events/s/` sépare l'endurance (Sporthive) du motorisé (Speedhive) :
`/events/3632319` — identifiant court, sans `s` — est une épreuve motorisée,
servie par une **autre** API (`/api/v0.2.3/eventresults/`). Ne pas confondre les
deux : c'est la seule chose que le path distingue.

**Deux familles d'identifiants coexistent**, sur les mêmes routes et la même API :

- **snowflake** — 19 chiffres, `7191895923677191680` : le fonds historique ;
- **GUID** — `bdea2f10-1510-481c-b5ef-ef7f1926a06f` : les événements récents.

Les deux sont vivants et interchangeables du point de vue de l'API. Un scraper
qui exigerait `\d+` refuserait tous les événements récents — dont
`2026 Europe Triathlon Junior Cup Izvorani`, vérifié rendu à 49 classés.

`results.sporthive.com/events/{id}[/races/{n}]` est l'ancienne façade : elle
répond **307** vers `sporthive.com/events/s/{id}`. Son segment `/races/{n}`
porte un **index** (`/races/3`), pas un identifiant de course — il n'est
exploitable par aucune route de l'API et doit être ignoré, pas traduit.

## L'API

Base : `https://eventresults-api.speedhive.com/sporthive`. Trois routes suffisent.

| Route | Rend |
| --- | --- |
| `GET /events/{eventId}` | `eventName`, `date`, `location`, `countryCode`, `eventType`, `hidden` |
| `GET /events/{eventId}/races` | liste de courses : `id`, `raceName`, `distanceInMeter`, `classificationsCount`, `teamsCount`, `raceImportType` |
| `GET /races/{raceId}/participants?size=10&page=N&useContinuationToken=false` | page de classement |

`GET /races/{raceId}` existe aussi (métadonnées d'une course seule) mais
n'apporte rien de plus que l'entrée correspondante de `/races`.

`eventType` vaut `Triathlon` ou `Running` sur le panel — un **contexte** de
classification utile, jamais un type d'épreuve au sens du modèle (une course
`Duathlon Jeunes 10-13 Ans` vit sous un événement `Triathlon`).

### La pagination est le coût dominant

`size` est plafonné à **10**, refus explicite au-delà :

```
400 — "The size value cannot be greater than 10"
```

Aucune échappatoire mesurée : `classifications`, `csv`, `export`,
`participants/csv` → 404 ; `useContinuationToken=true` rend la même page de 10.
La réponse est une page Spring classique (`content`, `totalElements`,
`totalPages`, `first`, `last`, `number`, `size`, `numberOfElements`).

**Une requête par tranche de 10 participants** : c'est le budget à assumer.

| Épreuve | Participants | Requêtes (event + races + pages) |
| --- | --- | --- |
| Triathlon de Vertou 2024 | 504 | **54** |
| Triathlon Sud Vendée | 978 | 103 |
| Tri Amsterdam 2025 | 3 137 | 318 |
| NN Marathon Rotterdam 2024 | 43 212 | **4 328** |

Les épreuves du club sont dans la première ligne ; le marathon est là pour
borner le pire cas, pas pour être importé.

## Le participant

Clés observées : `pk`, `id`, `vid`, `apid`, `tags`, `name`, `bib`, `gender`,
`raceCategory`, `categoryPosition`, `numberOfParticipantsInCategory`,
`overallPosition`, `genderPosition`, `genderPositionCount`,
`gunTimeOfParticipant`, `chipTimeOfParticipant`, `dns`, `dsq`, `validity`,
`legs`, `teamName`, `teamId`, `teamRank`, `teamScore`, `teamContribute`,
`country`, `city`, `customValues`, `activeEventId`, `activeRaceId`,
`activeLocation`, `distanceInMeter`, `date`.

Couverture mesurée sur 1 107 participants échantillonnés (11 événements) :

| Champ | Couverture | Note |
| --- | --- | --- |
| `name` | 1107/1107 | jamais scindé en prénom/nom |
| `bib` | 1107/1107 | toujours présent, contrairement à runnerbreizh |
| `legs` | 1107/1107 | voir plus bas — le contenu, lui, varie |
| `overallPosition` | 1099/1107 | `0` chez les non-finishers |
| `gender` | 1053/1107 | `M` / `F` / absent |
| `chipTimeOfParticipant` | 932/1107 | |
| `raceCategory` | 925/1107 | `S2M`, `V4M`, `REX`… ou libellé long (`Juniori Masculin`) |
| `gunTimeOfParticipant` | 814/1107 | |
| `country` | 630/1107 | |
| `teamName` | **295/1107** | le club — voir la nuance ci-dessous |

**Ni date de naissance ni âge** : seule `raceCategory` situe la classe d'âge.
`customValues` est **vide sur tout le panel** (0/678 sur les courses lues
intégralement) — ne rien en attendre.

### `name` est un seul champ, en « Prénom NOM »

`Nathan FRADIN`, `Pol LE BOT`, `Abdi Nageeye`. `utils.split_athlete_name` traite
déjà les deux conventions et les particules ; rien à écrire de spécifique. En
relais, ce champ porte le **nom d'équipe** (`LES BESTIOLES`, `TEAM CACAHOUETE`),
entièrement en majuscules : il tombe alors en nom sans prénom, comme chez
runnerbreizh. Limite connue, pas un bug.

### Les temps portent des fractions à 7 décimales

Trois graphies coexistent, **dans un même panel** :

```
"02:04:45"            (8 caractères)
"00:31:34.000"        (12)
"00:40:58.7230000"    (16)
```

`utils.normalize_time` reconnaît la première et **renvoie les deux autres
telles quelles** (aucune de ses regexes n'accepte de partie fractionnaire).
Stocker `00:40:58.7230000` casserait toute comparaison de temps côté front. La
fraction doit être **tronquée avant** l'appel, pas après.

### Les statuts sont dans `validity` — jamais dans `dns` / `dsq`

C'est le piège central de cette source. Les booléens `dns` et `dsq` sont
**présents sur chaque participant et à `false` sur les 1 746 participants
sondés**, y compris ceux que le site affiche disqualifiés.

L'information est dans `validity`, absente (`null`) chez les finishers :

| `validity` | Occurrences | Sens |
| --- | --- | --- |
| `null` | 1 732 | finisher |
| `DNS` | 11 | non-partant |
| `DNF` | 2 | abandon |
| `DQ` | 1 | disqualifié — noter le libellé, **`DQ` et non `DSQ`** |

Vérification croisée : **les 14 participants à `validity` non nulle sont
exactement les 14 sans aucun temps** (ni gun ni chip), et leur
`overallPosition` vaut `0`. La correspondance est parfaite sur le panel — mais
c'est `validity` qui porte le sens, l'absence de temps n'en est que le corollaire.

Sur la seule course « Vertou 2024 — Triathlon S » (285 lus intégralement) :
11 `DQ`, 1 `DNF`, 0 `DNS`.

Se fier à `dsq` aurait donc classé finisher **la totalité** des non-finishers du
panel.

### `teamName` est le club, sauf quand c'est une sélection

Sur les épreuves françaises, `teamName` est bien le club — `LES SABLES VENDEE
TRI`, `PONTIVY TRI`, `TRI CLUB NANTAIS`. Sur une épreuve internationale, le même
champ porte la **sélection nationale** (`Israel` à Izvorani). La source ne
distingue pas les deux : c'est un champ « team/club » unique. Aucune
conséquence pour le TCN (`core.club.is_tcn` compare à une liste blanche, à
l'égalité), mais ne pas présenter ce champ comme « club » sans réserve.

Sur les courses françaises lues intégralement, il manque chez ~35 % des
participants (90/285 à Vertou S, 121/320 à Sud Vendée ARRIVÉE) : un club vide
n'est pas une anomalie de scraping.

## Les `legs` : hétérogènes en surface, positionnels en substance

Chaque participant porte une liste `legs`, un objet par discipline **ou par
transition**, dans l'ordre de course :

```json
{"sportName": "SWIM", "type": "Swimming", "legDuration": "00:10:47",
 "totalDuration": "00:10:47", "distanceInMeters": 750, "kmh": 4.17,
 "rank": 1, "totalPosition": 1, "participantSplits": [...]}
```

`legDuration` est la durée **du segment** (différentielle), `totalDuration` le
cumul — mais ce dernier vaut `00:00:00` sur une partie du panel : ne pas s'en
servir.

Les libellés sont **incohérents d'une épreuve à l'autre** — 9 signatures
distinctes sur 1 746 participants, pour ce qui est le même triathlon :

| Occurrences | Signature `(sportName, type)` |
| --- | --- |
| 634 | `((None, 'Running'),)` — mono-sport, voir plus bas |
| 301 | `Swim/T1/Bike/T2/Run` avec `type` corrects |
| 285 | `SWIM/TRANSITION/BIKE/TRANSITION/RUN` — **les deux transitions portent le même libellé** |
| 197 | `Swim/Transition 1/Bike/Transition 2/Run`, `type` = `Other` **partout**, y compris la natation |
| 84 | `swim/transition/bike/transition2/run` |
| 80 | `swim/T1/bike/T2/run` |
| 63 | `RUN/TRANSITION/BIKE/TRANSITION/RUN` — **un duathlon** |
| 59 | `SWIM/TRANSITION/BIKE` — épreuve arrêtée au vélo (« Après Vélo ») |
| 43 | `SWIM` seul (« Après Natation ») |

Trois conclusions, chacune structurante :

1. **Ni `sportName` ni `type` n'est fiable pris isolément.** La casse varie
   (`SWIM`/`Swim`/`swim`), les transitions n'ont pas de libellé stable, et
   `type` vaut `Other` pour une natation sur 197 lignes. Router les splits *par
   libellé* — comme le fait T2Area — donnerait un résultat différent d'une
   épreuve à l'autre pour la même discipline.
2. **L'ordre, lui, est constant** : natation, T1, vélo, T2, course, tronqué à
   droite quand l'épreuve est plus courte. C'est exactement la sémantique des
   **5 slots positionnels** de `ScrapedResult` (`swim/t1/bike/t2/run`), que
   `services/mapping.build_splits` ré-étiquette ensuite selon `event_type` —
   le duathlon (63 lignes ci-dessus) devenant `course1/t1/bike/t2/course2` sans
   qu'aucun code de scraper n'ait à le savoir.
3. **Le libellé verbatim serait ici un piège, pas un service.** Deux legs
   nommés `TRANSITION` dans la même épreuve entreraient en collision dans
   `splits` ; `build_splits` les désambiguïserait en `TRANSITION (2)`, ce qui
   n'apprend rien à personne. Le chemin `segments` reste le bon défaut pour
   ok-time ou RaceResult, dont les libellés sont *signifiants* — il ne l'est
   pas pour Sporthive.

### Mono-sport : la vraie information est un cran plus bas

Sur une course à pied, il n'y a **qu'un seul leg**, et son `legDuration` ne veut
rien dire (`00:06:33` pour un marathon couru en `02:04:45`, `distanceInMeters`
à `0`). Les points de passage sont dans son `participantSplits` :

```
5k 00:14:34 | 10k 00:14:33 | 15k 00:14:42 | 20k 00:14:43 | 21.1k 00:03:15
| 25k 00:11:28 | 30k 00:14:56 | 35k 00:14:43 | …          (10 splits)
```

`splitName` y est **signifiant** (`5k`, `21.1k`) et unique : c'est le cas où
`segments` s'impose, à l'inverse du multisport. Un scraper qui prendrait
`legDuration` du leg unique publierait un temps faux.

Les legs multisports portent eux aussi des `participantSplits` (`.75 km` sous
`SWIM` à Vertou), un niveau de détail sous la discipline : hors périmètre.

## Relais : une ligne = une équipe

À Vertou (« Relais - Triathlon S », 10 lignes lues intégralement) comme à Sud
Vendée, une équipe occupe **une seule ligne** : `name` porte le nom d'équipe,
`teamName` et `teamId` sont `null`, `raceCategory` vaut `REX`/`REM`, et les
`legs` sont ceux de l'équipe.

C'est l'inverse de runnerbreizh (une ligne par équipier, rangs dupliqués) : rien
ici ne fait sortir l'épreuve `is_reliable=false`. Ces courses se reconnaissent à
leur `raceName` (`Relais - …`, `… Relay`).

`teamsCount` sur une course et l'endpoint `GET /races/{raceId}/teams` sont un
**autre** objet : un classement par équipes agrégé (`id`, `name`,
`classificationsCount`), qui double le classement individuel plutôt que de le
compléter. Non consommé.

## Courses vides et courses techniques

`Tussentijden` (Tri Amsterdam) porte `classificationsCount: 0` et
`raceImportType: 3` — sa page de participants rend une page vide, sans erreur.
MASAFAT Relay Race a ses 8 courses à 0 (épreuve à venir). Une course sans
classement n'est **pas** une anomalie : elle est à ignorer silencieusement, et
un événement dont *toutes* les courses sont vides doit se solder par une erreur
parlante plutôt que par un import à 0 participant.

## Ce qui existe déjà et qu'il ne faut pas réécrire

- `utils.split_athlete_name` — les deux conventions de nom, particules comprises.
- `utils.normalize_time` — après troncature de la fraction (voir plus haut).
- `utils.normalize_rank`, `utils.qualify_event_name` — le nom de course qualifie
  le nom d'événement (`Triathlon de Vertou 2024 - Triathlon S`), sans quoi les
  5 courses de Vertou fusionneraient et leurs dossards entreraient en collision
  (issue #21).
- `classify.classify_event_type(texte, contexte=…)` — le `raceName` classe,
  `eventName`/`eventType` servent d'appoint. Ne **pas** concaténer les deux
  (piège ok-time : un « Trail 12 km » d'un « Triathlon de X » classé
  `triathlon`, survivant à `federal_only=true`).
- `core.club.is_tcn` — jamais de liste de libellés dans le scraper (issue #76).
- `services/mapping.build_splits` — le ré-étiquetage par sport des 5 slots.
- `registry.HostMatchedProvider` — détection par host, jamais par sous-chaîne
  d'URL (issue #49).

## Méthode

Les trois passes de sondage sont conservées dans le scratchpad de la session
(`sondage.py`, `sondage2.py`, `sondage3.py`) : découverte des endpoints par
capture réseau Playwright sur la SPA, puis appels directs en `urllib`. Les
mesures exhaustives (validity, relais, couverture de champs) portent sur les
4 courses lues intégralement ; les mesures de forme (signatures de legs, clés)
sur l'échantillon des 11 événements.
