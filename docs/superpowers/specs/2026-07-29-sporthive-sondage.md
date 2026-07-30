# MYLAPS Sporthive — sondage de l'API réelle

Issue : [#53](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/53)
(sous-issue de #33, section B). Sondage effectué le **29/07/2026**.

Ce document est la **vérité de terrain** : il prime sur l'énoncé de l'issue, sur
le design et sur le plan. Toute divergence se tranche en re-sondant, pas en
raisonnant.

## Ce que l'issue annonçait, et ce qui est faux

L'issue #53 (18/07/2026) et la ligne correspondante de l'epic #33 décrivent un
endpoint qui **n'existe plus**. Trois de leurs affirmations ne tiennent pas.

| Énoncé de l'issue / #33 | Observation du 29/07/2026 |
| --- | --- |
| API sur `eventresults-api.sporthive.com` | **Mort.** Le DNS résout encore (65.52.128.33, Azure App Service) mais le host ne présente plus qu'un certificat `*.azurewebsites.net` : le domaine custom a été délié côté Azure. Toute requête TLS échoue en `Hostname mismatch` — pas un défaut de magasin de CA, un certificat qui ne couvre pas le nom. L'API vit désormais sur **`eventresults-api.speedhive.com`**, MYLAPS ayant fondu Sporthive dans Speedhive. |
| Route `…/races/{raceId}/classifications/search?count=50&offset=0` | **404.** La route actuelle est `GET /sporthive/races/{raceId}/participants`. `classifications` n'existe plus sous aucune forme. |
| Pagination « par offset, `count=50` » | **Faux deux fois.** Les paramètres sont `page`/`size` (pagination Spring), et `size` est **plafonné à 10** côté serveur. `count`/`offset` sont acceptés sans erreur mais **silencieusement ignorés** — le piège est qu'on croit paginer par 50 en relisant toujours les 10 mêmes lignes. |
| « `scrape()` + `scrape_event_all()` » | Hors convention actuelle : `scrape_event_all()` est **la seule** voie d'import depuis la suppression du scraping athlète-unique (AGENTS.md, « Conventions scrapers »). |

En revanche l'issue a raison sur l'essentiel : l'API est **publique** (aucune
clé, aucun cookie, aucun `Origin` exigé), **propre**, et sans Playwright.

### Comment l'endpoint réel se retrouve

Ce n'est pas devinable : `results.sporthive.com` redirige en 307 vers
`sporthive.com/events/s/{eventId}/…`, qui sert un shell Vite de 2 Ko. La
configuration des endpoints est servie par la page elle-même :

```
GET https://sporthive.com/api/clientSettings   →  { "eventResultApiUrl": "https://eventresults-api.speedhive.com", … }
```

Le chemin de base `/sporthive/` et les routes se lisent dans le bundle
(`SporthiveEventResultsApiClient`). Si l'API redéménage, c'est
`clientSettings` qu'il faut relire — pas le code du scraper.

## Panel sondé

**7 événements, 32 courses, 10 360 participations, 1 063 requêtes HTTP.** Le
panel a été descendu intégralement (aucun échantillonnage) : toutes les courses
de chaque événement, toutes les pages de chaque course.

| Clé | Événement | Date | `eventType` | Pays | Courses | Participations |
| --- | --- | --- | --- | --- | ---: | ---: |
| `sheet-tri-sud-vendee` | Triathlon Sud Vendee Dimanche | 22/09/2024 | Triathlon | FR | 6 | 955 |
| `triathlon-touraine` | Triathlon de la Touraine 2023 | 24/06/2023 | Triathlon | FR | 3 | 582 |
| `royal-windsor` | Royal Windsor Triathlon 2024 | 09/06/2024 | Triathlon | GB | 4 | 2 019 |
| `monsal-trail` | Monsal Trail Sunday | 27/10/2024 | Running | GB | 2 | 429 |
| `uk-cau-cross` | UK CAU Inter Counties Cross Country | 07/03/2026 | Running | UK | 14 | 2 852 |
| `algiers-urban-trail` | ALGIERS URBAN TRAIL 2025 | 27/06/2025 | Running | DZ | 1 | 2 685 |
| `oeiras-trail` | Oeiras Trail | 19/11/2023 | Running | PT | 2 | 838 |

Le panel est volontairement international : Sporthive est une plateforme MYLAPS
mondiale, et c'est **hors de France** que les conventions de la source divergent
le plus (libellés de legs, temps publiés, catégories).

## L'URL réellement présente dans le Sheet

Une seule occurrence sur les 785 liens :

```
https://results.sporthive.com/events/7237011278055708416/races/1/bib/426
```

Elle pointe le dossard 426 du **Triathlon S** de Sud Vendée 2024 — un
**« TRI CLUB NANTAIS »**, donc un membre du TCN au sens de `core/club.py`.

## Les routes de l'API

Base : `https://eventresults-api.speedhive.com/sporthive`

| Route | Rend |
| --- | --- |
| `GET /events/{eventId}` | Métadonnées : `eventName`, `date`, `location`, `countryCode`, `eventType`, `uniqueKey`. |
| `GET /events/{eventId}/races` | Liste des courses (tableau nu, non paginé) : `id`, `activeRaceId`, `raceName`, `classificationsCount`, `distanceInMeter`. |
| `GET /races/{raceId}/participants?page=N&size=10` | Le classement, paginé. |
| `GET /races/{raceId}/bibs/{bib}` | Une participation isolée. |
| `GET /races/{raceId}/teams?page=N&size=10` | Les **clubs** représentés sur une course individuelle (`ACA TRIATHLON`…), avec leur nombre de classés. |

Il n'existe **aucun export CSV** côté Sporthive : `/races/{id}/csv` et
`/events/{id}/csv` répondent 404 (ces routes n'existent que pour le volet
Speedhive motorsport, sous `/api/v0.2.3/eventresults/`). La pagination à 10 est
donc incontournable.

Erreurs : 404 propre avec message explicite (`Event with id X is not found`,
`Sporthive Race with X is not found`), y compris sur un identifiant non
numérique. Aucun 500, aucune page HTML d'erreur.

## Piège n° 1 — `races/{n}` de l'URL n'est *pas* un `raceId`

C'est le piège structurant de ce provider, et il est silencieux.

Dans `…/events/7237011278055708416/races/1`, le `1` est l'**`activeRaceId`** :
un ordinal **local à l'événement**. Le `raceId` que l'API attend est le champ
`id`, un snowflake à 19 chiffres (`7242234087144997120`). Les deux ne se
recoupent jamais : sur les 32 courses du panel, `id == segment d'URL` **0 fois**,
`activeRaceId == segment d'URL` **32 fois**.

Or `GET /races/1` **répond 200** — et rend une course de 2015 (`Overall`, 1 173
classés, événement `6065829728579747840`) qui n'a aucun rapport. Un scraper qui
prendrait le segment d'URL pour un `raceId` importerait donc une épreuve
étrangère sous la `source_url` demandée, sans la moindre erreur. Même famille de
piège que le listing générique d'ok-time (`_resolve_event_id`).

La résolution passe obligatoirement par `GET /events/{eventId}/races`, puis par
un match sur `activeRaceId`. À noter : l'ordinal n'est pas toujours petit ni
contigu — Royal Windsor numérote `489741…489744`, l'Algiers Urban Trail `494091`,
le cross UK `1..13` **plus** `127`. Il est en revanche unique au sein d'un
événement (32/32).

## Piège n° 2 — `size` est plafonné à 10

```
GET /races/{id}/participants?size=50
→ 400 {"defaultMessage":"The size value cannot be greater than 10", …}
```

Le message d'erreur fuit la signature du contrôleur
(`SporthiveParticipantController.getParticipantsForRace(String, String, String, Boolean, int, int)`).
`count`/`offset` — les paramètres annoncés par l'issue — ne déclenchent aucune
erreur mais ne changent **rien** : la réponse reste `size=10, page=0`.

Conséquence directe, mesurée sur le panel : **une participation coûte un
dixième de requête**. Importer l'événement du Sheet en entier (955
participations, 6 courses) demande ≈ 100 requêtes ; le cross UK (2 852) en
demande ≈ 293. C'est un ordre de grandeur au-dessus de tous les autres providers
JSON du projet (ok-time : 1 requête pour l'événement entier ; RaceResult : 1 par
liste). Ce coût est le fait dominant du cadrage.

La réponse est une page Spring : `content`, `number`, `size`, `totalElements`,
`totalPages`, `first`, `last`, `numberOfElements`. `last: true` est un critère
d'arrêt franc, et `page` au-delà du dernier rend `content: []` sans erreur.

### `classificationsCount` est une garde de complétude fiable

Sur les **32 courses du panel, sans exception**, le nombre de participations
lues est exactement égal au `classificationsCount` annoncé par
`/events/{id}/races`. C'est le pendant du total de runnerbreizh : de quoi
vérifier après coup qu'une pagination n'a pas été tronquée par une page servie
vide — sans jamais s'en servir pour *borner* la boucle.

## Champs d'une participation

Mesuré sur les 10 360 lignes. « présence » = champ non nul.

| Champ | Présence | Remarque |
| --- | ---: | --- |
| `name` | 10 360 | Nom complet, conventions variables (cf. plus bas). |
| `bib` | 10 360 | Toujours présent. |
| `overallPosition` | 10 360 | **`0` vaut « pas classé »**, pas « premier ». |
| `gender` | 10 360 | `M` 4 090 / `F` 2 027 / **`U` 4 243** (41 %). |
| `legs` | 10 360 | Toujours une liste, jamais vide. |
| `categoryPosition` | 9 981 | |
| `genderPosition` | 8 594 | |
| `gunTimeOfParticipant` | 8 268 | Absent sur **tout** Royal Windsor (0/1 349). |
| `raceCategory` | 7 504 | Libellés hétérogènes : `S2M`, `V1F`, `O45-49`, `M 50`, `Female Vet 70`. |
| `chipTimeOfParticipant` | 7 435 | Absent sur tout le cross UK. |
| `teamName` / `teamId` | 4 592 | Le **club** (44 % des lignes). |
| `country` | 3 639 | `FRA`, `UK`, `DE`… codes non homogènes (3 et 2 lettres). |
| `teamRank` / `teamScore` | 1 740 | Classement par équipes (cross UK). |
| **`validity`** | **172** | Le statut. Absent = finisher. |

73 lignes n'ont **ni** `chipTime` **ni** `gunTime`. Aucune des deux colonnes
n'est donc utilisable seule : il faut un temps avec repli sur l'autre.

Format des durées : `HH:MM:SS` **ou** `HH:MM:SS.fffffff` (`00:57:33.2510000`,
7 décimales) selon la course — et `HH:MM:SS.fff` sur les `legDuration`.
`normalize_time()` de `utils.py` ne reconnaît **aucune** de ces formes
fractionnaires (son motif `HH:MM:SS` est ancré `$`) et les rendrait telles
quelles, fractions comprises. Il faut tronquer la fraction avant de normaliser.

## Piège n° 3 — le statut est dans `validity`, pas dans `dns`/`dsq`

Les objets portent **trois** champs qui semblent tous dire le statut :

```json
{ "validity": "DNF", "dns": false, "dsq": false }
```

Sur les 10 360 lignes du panel, **`dns` et `dsq` valent `false` 10 360 fois** —
y compris sur les 35 lignes dont `validity` vaut `"DNS"`. Ces deux booléens sont
morts : s'y fier raterait **100 %** des statuts.

Le seul porteur est `validity`, et son vocabulaire est :

| `validity` | Lignes | Constante projet |
| --- | ---: | --- |
| absent (`null`) | 10 188 | `finisher` |
| `DNF` | 129 | `STATUS_DNF` |
| `DNS` | 35 | `STATUS_DNS` |
| **`DQ`** | 8 | `STATUS_DSQ` — noter `DQ`, **pas** `DSQ` |

`utils.derive_status_from_label()` traduit déjà les trois jetons, `dq` compris
(il avait été ajouté pour T2Area) : rien à écrire, seulement à appeler.

Corrélation parfaite et exploitable : `validity` non nul ⟺ `overallPosition == 0`
(172/172 dans les deux sens). Un non-finisher porte en outre un `chipTime` à
`00:00:00` — valeur qui vaut **temps absent**, exactement comme chez T2Area.

Et un non-finisher publie un **leg fantôme** : une entrée unique de type
`Running`, `legDuration: "00:00:00"`, dont le seul split s'appelle `Start`.
C'est ce qui explique les « 81 participants à 1 leg » d'une course de triathlon.
Il ne doit produire ni temps ni split.

## Les legs : `type` fait foi, `sportName` ment

Chaque participation porte une liste ordonnée de `legs` :

```json
{ "sportName": "SWIM", "type": "Swimming", "legDuration": "00:09:46",
  "totalDuration": "00:09:46", "distanceInMeters": 750, "rank": 2,
  "participantSplits": [ { "splitName": ".75 km", "splitDuration": "00:09:45.551", … } ] }
```

`sportName` est saisi par le chronométreur et **n'est pas normalisé** : `SWIM` /
`TRANSITION` / `BIKE` / `RUN` sur les épreuves françaises, `Swim` / `T1` /
`Bike` / `T2` / `Run` à Windsor, et **`null` sur 5 635 des 24 042 legs** (23 %)
— tout le cross UK et tout l'Algiers Urban Trail.

`type` en revanche est **toujours présent** (24 042/24 042) et pris dans un
vocabulaire fermé : `Swimming`, `Cycling`, `Running`, `Transition`. C'est le
seul discriminant fiable.

Séquences observées, par course :

| Séquence de `type` | Courses concernées |
| --- | --- |
| `Swimming > Transition > Cycling > Transition > Running` | tous les triathlons (adultes et relais) |
| `Swimming > Transition > Cycling > Running` | **courses enfants** (6-9 ans, 10-13 ans) — une seule transition |
| `Running` | trail, cross, course à pied ; et les lignes non-finisher |

La séquence à 4 legs interdit un mapping **positionnel** vers les slots
`swim/t1/bike/t2/run` : la course à pied des enfants atterrirait dans le slot
`t2`. Le mapping doit se faire sur `type`, ou passer par le chemin générique
`segments` (`ScrapedResult.segments`), qui porte déjà les libellés verbatim chez
ok-time, RaceResult et Chronoplace et qui est déplafonné.

Les `participantSplits` intra-leg (jusqu'à 2 par leg, libellés `.75 km`,
`2.5 km`, `4.8km`, `Start`, `Finish`) sont une granularité **supplémentaire**,
sous les legs. Les retenir multiplierait le nombre de clés de splits sans
équivalent chez les autres providers.

## Les clubs — et le TCN

`teamName` porte le club sur les courses individuelles : `TRI VELOCE SAINT
SEBASTIEN`, `LES SABLES VENDEE TRI`. **686 clubs distincts** sur le panel, dont
**`TRI CLUB NANTAIS` (29 participations)** — libellé déjà dans la liste blanche
de `core/club.py`, donc `is_tcn()` le reconnaît sans rien ajouter.

Deux réserves mesurées :

- le champ est absent sur 56 % des lignes (aucun club déclaré) ;
- sur le cross UK, `teamName` porte un **comté** (`YORKSHIRE`, `KENT`) et non un
  club — sans conséquence pour nous, mais c'est un champ « équipe », pas un
  champ « club » au sens strict.

## Les relais : une ligne par équipe, pas par équipier

Sur les courses `Relais Triathlon S/M` (Sud Vendée, Touraine) et `Team Relay`
(Windsor), la source publie **une seule ligne par équipe** :

```json
{ "name": "LA COUSINADE", "bib": "438", "teamName": null, "overallPosition": 1,
  "chipTimeOfParticipant": "01:01:50" }
```

Le `name` est un **nom d'équipe** (`LA COUSINADE`, `LES TRIATHLETES DE ST
GILLES`, `EQUIPE 460`, `Three Feet in the Thames`), et `teamName` est nul. C'est
l'inverse exact de runnerbreizh, qui publie une ligne par équipier avec temps
partagé — et le corollaire est que ces lignes ne décrivent **aucune personne** :
les passer à `split_athlete_name()` fabriquerait un athlète « COUSINADE, LA ».

L'API expose bien `/races/{id}/teams/{teamId}/participants`, mais le `teamId`
d'une ligne de relais est nul : la composition des équipes n'est pas publiée par
cette route.

## Piège n° 4 — les `tags` ne découpent pas les noms

Chaque participation porte un tableau `tags` qui **semble** offrir un découpage
prénom / nom tout fait :

```json
"tags": [ {"tag":"117","tp":"b"}, {"tag":"eliott joussemet","tp":"n"},
          {"tag":"eliott","tp":"n"}, {"tag":"joussemet","tp":"n"},
          {"tag":"tri veloce saint sebastien","tp":"t"} ]
```

C'est un **index de recherche**, pas une structure : `tp:"n"` marque la chaîne
complète *et* chacun de ses tokens séparés par des espaces, en minuscules. La
preuve par les cas réels : `Victor LE MAUFF` → `['victor le mauff', 'victor',
'le', 'mauff']` (aucune notion de particule), et une équipe donne exactement la
même forme : `LA COUSINADE` → `['la cousinade', 'la', 'cousinade']`. Le nombre de
tags `n` varie de 2 à 7 selon le nombre d'espaces, et un double espace produit un
token vide (`Gemma  Cox` → `['gemma', '', 'cox']`).

Le découpage doit donc passer par `utils.split_athlete_name()` sur `name`, avec
sa limite connue. Les conventions observées sont d'ailleurs contradictoires
entre pays — `Eliott JOUSSEMET` (Prénom NOM), `Oliver Scott` (Prénom Nom),
`ABDELHAMID MOUSSAOUI` (tout en majuscules, ordre indéterminé) — et la source ne
publie **aucun** champ séparé qui les départagerait.

## Piège n° 5 — les sous-classements dupliquent des participations

Le cross UK publie 14 courses, dont `Senior Men` (294 classés) **et** `Senior
Men 9 to count` (90 classés). Vérification faite sur les dossards : les **90 sont
tous** dans les 294. C'est un classement par équipes dérivé du même classement
individuel, exposé comme une course à part entière — mêmes coureurs, mêmes
temps, `teamRank`/`teamScore` en plus.

Importer sans discernement toutes les courses d'un événement crée donc, pour ces
cas, une seconde `Course` et une seconde participation par athlète concerné.
Rien dans le JSON ne marque une course comme « dérivée » : ni un type, ni un
drapeau — seul le `raceName` le suggère, en anglais et sans convention.

## Ce que la source ne publie pas

- **Aucune date de naissance** — seule `raceCategory` situe l'âge, avec des
  libellés qui changent d'un pays à l'autre.
- **Aucun genre fiable sur 41 % des lignes** (`gender: "U"`).
- **Aucune ville de participant** ; `activeLocation` est présent mais à
  `latitude: 0.0, longitude: 0.0` sur la totalité du panel.
- **Aucun temps de passage horodaté** — que des durées.
- **Aucun export CSV**, donc aucun contournement du plafond de 10.

## Métadonnées d'épreuve exploitables

`GET /events/{eventId}` donne tout ce dont `ScrapedResult` a besoin :

- `eventName` → nom d'épreuve, à qualifier par `raceName` via
  `utils.qualify_event_name()` (chaque course a son classement et réutilise les
  dossards — cf. issue #21) ;
- `date` (ISO `2024-09-22T00:00:00`) → `event_date`, sans parsing FR ;
- `location` (`L'Aiguillon sur Mer (85)`) et `countryCode` ;
- `eventType` (`Triathlon`, `Running`) — trop grossier pour `event_type` : c'est
  `raceName` (`Triathlon S`, `Trail 10K`, `Senior Men`) qui porte le format, avec
  `eventName` en **contexte** au sens de `classify_event_type(texte, contexte=…)` ;
- `distanceInMeter` **par course** → `distance_km` sans extraction textuelle.

## Ce qui existe déjà et qu'il ne faut pas réécrire

- `utils.derive_status_from_label()` — traduit `DNF` / `DNS` / `DQ` tels quels.
- `utils.split_athlete_name()` — les deux conventions de casse.
- `utils.qualify_event_name()` — la qualification par course.
- `classify.classify_event_type(texte, contexte=…)` et `extract_distance_km()`.
- `core/club.is_tcn()` — `TRI CLUB NANTAIS` y est déjà.
- `registry.HostMatchedProvider` — détection par host, `_HOSTS` seul à déclarer.
  Les deux hosts à couvrir sont `results.sporthive.com` et `sporthive.com` (la
  redirection 307 mène du premier au second, et une URL copiée depuis le
  navigateur porte aujourd'hui le second).

## Arbitrages de cadrage — tranchés le 29/07/2026

Aucun n'était tranchable par le sondage seul : ce sont des arbitrages produit.
Ils sont consignés ici parce qu'ils s'appuient sur les mesures ci-dessus ; la
spec les reprend et fait foi sur leur formulation.

1. **Périmètre d'un import → tout l'événement.** Une URL désigne une course
   (`/races/{n}`), mais l'import remonte à l'événement et importe **toutes** ses
   courses, comme ok-time et Chronoplace. Motif : le Sheet ne porte qu'un lien
   par épreuve, et un membre du TCN inscrit sur un autre format y serait sinon
   invisible. Coût accepté : ≈ 100 requêtes pour l'épreuve du Sheet, ≈ 293 pour
   le pire cas du panel.
2. **Sous-classements (piège n° 5) → tout importer.** Aucun filtre : la source
   ne publie aucun critère, et deviner sur le `raceName` écarterait un jour une
   vraie course, silencieusement. Les participations dupliquées vivent dans des
   `Course` distinctes, sans collision de dossard. Limite connue et assumée.
3. **Relais → importés avec `is_relay=True`**, le nom d'équipe en
   `athlete_name`. Le classement reste complet ; la contrepartie est que des
   fiches d'athlète portent un nom d'équipe.
4. **Splits → legs seuls**, via le chemin générique `segments`, libellés depuis
   `type` (fiable à 100 %). Les `participantSplits` intra-leg ne sont pas
   stockés : ils mêleraient deux granularités dans un même dict, sans équivalent
   chez les autres providers.
5. **Temps → `chipTime` prioritaire, repli `gunTime`** (temps réel de l'athlète,
   convention usuelle du projet). Les 73 lignes qui n'ont ni l'un ni l'autre
   sortent sans temps total, donc en `DNF` par l'heuristique de `derive_status`
   si `validity` ne dit rien.

---

## Addendum du 30/07/2026 — re-sondage sur un panel élargi

Sondage complémentaire de **11 événements / 6 pays**, mené indépendamment (le
détail des mesures est en tête de ce document pour le panel du 29 ; celui du 30
portait sur 1 746 participations échantillonnées et 678 lues intégralement). Il
**confirme** tout ce qui précède, sauf deux points, tranchés ici en re-sondant
comme le veut la règle du dépôt.

### 1. Deux familles d'identifiants d'événement, pas une

Le panel du 29 (7 événements) ne portait que des identifiants **snowflake** à
19 chiffres, d'où la lecture d'URL en `\d+`. Le fonds **récent** est identifié
par **GUID** :

| Événement | Identifiant | Servi par |
| --- | --- | --- |
| Triathlon Sud Vendee Dimanche | `7237011278055708416` | `/events/{id}`, `/events/{id}/races`, `/races/{id}/participants` |
| 2026 Europe Triathlon Junior Cup Izvorani | `bdea2f10-1510-481c-b5ef-ef7f1926a06f` | **les mêmes routes** |

Les deux familles cohabitent sans distinction côté API, et la page d'accueil de
`sporthive.com` publie les deux formes. Un motif `\d+` refusait donc tout le
fonds récent **en amont de tout appel**, avec un message affirmant que l'URL
était illisible alors que le site la sert. La lecture d'URL accepte désormais
les deux, la branche GUID restant strictement formée (8-4-4-4-12) : élargir à
`[^/]+` laisserait passer `/events/abc` et déclencherait une requête qui ne peut
que 400 — c'est le refus qui nomme la forme attendue.

### 2. `type` peut valoir `Other` — et alors il ne discrimine rien

Le panel du 29 concluait « `type` est pris dans un vocabulaire fermé
(`Swimming`, `Cycling`, `Running`, `Transition`) ». Le vocabulaire est plus
large : `Other` existe, et le panel élargi le trouve à deux endroits.

| Épreuve | Legs concernés | `type` | `sportName` |
| --- | --- | --- | --- |
| ACCURO Jersey Triathlon, course « Standard » (177 classés) | **les cinq**, natation comprise | `Other` | `Swim`, `Transition 1`, `Bike`, `Transition 2`, `Run` |
| 2026 Europe Triathlon Junior Cup Izvorani (93 classés) | les deux transitions | `Other` | `transition`, `transition2` |

Rendre ce `type` verbatim publiait cinq disciplines sous le libellé `Other` —
puis `Other (2)` … `Other (5)` après désambiguïsation par `build_splits` : cinq
fois le même non-mot là où la source nomme correctement ses legs.

La règle du 29 **tient** et reste première : `type` est le champ normalisé,
présent sur 24 042 legs sur 24 042, là où `sportName` est nul sur 23 % d'entre
eux et jamais normalisé. Elle est seulement complétée d'un repli : quand `type`
ne dit rien (`Other`, vide) et que `sportName` dit quelque chose, c'est le
libellé publié qui gagne, normalisé par la même table (casse et suffixes
positionnels `transition2`, `T1`, `Transition 1` tous mesurés). Quand ni l'un ni
l'autre ne dit rien, le `type` brut est conservé — mieux vaut un libellé pauvre
qu'un temps perdu.
