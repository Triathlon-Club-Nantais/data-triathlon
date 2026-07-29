# Phase 0 — Research : scraper MYLAPS Sporthive

**Feature**: 004-sporthive-scraper | **Date**: 2026-07-29

Toutes les mesures citées viennent du sondage
`docs/superpowers/specs/2026-07-29-sporthive-sondage.md` (7 événements,
32 courses, 10 360 participations). Aucune question de la Technical Context n'est
restée en `NEEDS CLARIFICATION`.

---

## D1 — Le segment `races/{n}` de l'URL est purement ignoré

**Décision**: `_parse_url` n'extrait que l'identifiant d'événement. Le segment de
course, comme le segment de dossard, est lu puis **jeté**.

**Rationale**: la spec impose d'importer tout l'événement (FR-005), donc le
scraper n'a jamais besoin de résoudre la course pointée. Ce choix supprime *par
construction* le piège n° 1 du sondage : il n'existe aucun chemin de code où le
`1` de `/races/1` puisse être passé à l'API comme identifiant de course — ce qui
importerait une épreuve de 2015 sans erreur. FR-004 est satisfait sans garde
défensive à maintenir. C'est exactement ce que fait ok-time avec `/race/{id}`.

**Alternatives rejetées**:
- *Résoudre le segment en `activeRaceId` pour vérifier qu'il appartient bien à
  l'événement* : code mort, puisque toutes les courses sont importées de toute
  façon. Une garde qui ne garde rien finit par être retirée par erreur.
- *Importer la seule course pointée* : écarté au cadrage (cf. Clarifications de
  la spec).

---

## D2 — Détection par un seul host

**Décision**: `_HOSTS = ("sporthive.com",)`.

**Rationale**: `_host_match` accepte l'hôte exact **et** tout vrai sous-domaine,
donc cette entrée unique couvre `results.sporthive.com` (la forme du Sheet) comme
`sporthive.com` (la forme vers laquelle la redirection 307 mène, et donc celle
qu'un membre copie aujourd'hui depuis son navigateur). Aucun `matches` à écrire.

**Alternatives rejetées**: lister les deux hôtes — redondant, `_host_match`
gérant déjà la relation de sous-domaine.

**Note**: l'hôte de l'API (`eventresults-api.speedhive.com`) n'est **pas** un
hôte de détection. Une URL Speedhive collée par un utilisateur n'est pas une URL
de résultats Sporthive et ne doit pas router ici.

---

## D3 — Trois formes d'URL, un seul motif

**Décision**: un motif unique sur le chemin, tolérant un préfixe de langue et le
segment `s/` de la forme actuelle :

```
/(?:<lang>/)?events/(?:s/)?(?P<event_id>\d+)(?:/.*)?
```

**Rationale**: les formes mesurées sont `results.sporthive.com/events/{id}/…`
(celle du Sheet), `sporthive.com/events/s/{id}/…` (cible de la redirection) et
`results.sporthive.com/en/events/{id}/…` (servie en 200, sans redirection). Les
suffixes `/races/{n}`, `/bib/{b}` et `/bib/{b}/split` sont tous absorbés par
`(?:/.*)?` — ils ne portent aucune information utile (D1).

Une URL Sporthive dont le chemin ne livre pas d'identifiant lève une `ValueError`
nommant la forme attendue (FR-003).

**Alternatives rejetées**: chercher l'identifiant n'importe où dans l'URL — c'est
le motif de sous-chaîne interdit par le registre (SSRF #49).

---

## D4 — Pagination : arrêt sur `last`, plafond dur, complétude vérifiée

**Décision**: boucler sur `page` avec `size=10`, s'arrêter quand la réponse porte
`last: true` ou un `content` vide ; lever si le plafond `_MAX_PAGES` est atteint ;
puis **vérifier** que le nombre de participants lus est au moins égal au
`classificationsCount` annoncé par `/events/{id}/races`.

**Rationale**: trois gardes distinctes pour trois défaillances distinctes, sur le
modèle de `runnerbreizh._require_complete_ranking` :

1. `last` est le critère nominal, publié par la source.
2. Le plafond couvre le cas où l'invariant d'arrêt serait faux : mieux vaut lever
   que rendre indéfiniment des lignes probablement dupliquées. Un import refusé se
   rejoue (`rescrape-db --urls-from -`) ; une épreuve tronquée marquée fiable, non.
3. La vérification finale couvre le cas d'une page intermédiaire servie vide :
   la boucle s'arrêterait proprement, les rangs lus resteraient contigus, et
   `quality.analyze` ne verrait **aucune** anomalie — l'épreuve sortirait
   `is_reliable=true` alors qu'il lui manque la moitié de son classement.

La comparaison est un **plancher** (`lus < annoncé` → refus), jamais une égalité :
une course en cours peut gagner des classés entre l'appel `/races` et la fin de
la pagination. Le surplus est journalisé, pas refusé. Sur le panel, l'égalité est
vérifiée 32 fois sur 32.

`_MAX_PAGES = 1000` (10 000 participants) : le pire cas mesuré est 269 pages
(Algiers Urban Trail, 2 685 classés), et un marathon de 10 000 arrivants reste
sous le plafond.

**Alternatives rejetées**:
- *Borner la boucle sur `totalPages`* : c'est borner sur un total annoncé, la
  faute que runnerbreizh a payée. Le total sert à **vérifier**, pas à cadencer.
- *Se fier à `count`/`offset`* (l'énoncé de l'issue) : silencieusement ignorés
  par le serveur, la boucle relirait les 10 mêmes lignes indéfiniment.
- *Demander `size=50`* : rejeté en 400 par le serveur.

---

## D5 — Statut : `validity` seul

**Décision**: `status = derive_status_from_label(participant["validity"])`. Les
booléens `dns` et `dsq` ne sont **jamais** lus.

**Rationale**: sur les 10 360 lignes du panel, `dns` et `dsq` valent `false`
10 360 fois, y compris sur les 35 lignes dont `validity == "DNS"`. `validity`
porte les trois valeurs réelles (`DNF` 129, `DNS` 35, `DQ` 8), et
`utils.derive_status_from_label` les traduit déjà toutes les trois — `dq` y
figure depuis T2Area. Un `validity` absent rend `""`, ce qui laisse
`mapping.derive_status` appliquer son heuristique (finisher si temps total).

**Alternatives rejetées**: croiser `validity` avec `overallPosition == 0` — la
corrélation est parfaite (172/172) mais redondante ; deux sources pour une même
information finissent par diverger.

---

## D6 — Temps : chip prioritaire, fractions tronquées, `00:00:00` = absent

**Décision**: un helper `_time(raw)` unique, appliqué au temps total comme aux
durées de segment : tronquer la fraction de seconde, normaliser, puis rendre `""`
si le résultat est `00:00:00`.

**Rationale**: la source publie `HH:MM:SS` **ou** `HH:MM:SS.fffffff` selon la
course (et `HH:MM:SS.fff` sur les segments). `utils.normalize_time` ancre son
motif `HH:MM:SS` sur la fin de chaîne : il rendrait `00:57:33.2510000` **tel
quel**, fraction comprise, et cette valeur partirait en base. La troncature doit
donc précéder l'appel.

`00:00:00` vaut « pas de temps » — c'est la valeur portée par les non-finishers,
même convention que T2Area. La rendre vide fait que `derive_status` ne classe pas
un abandon en finisher.

Priorité `chipTimeOfParticipant` puis `gunTimeOfParticipant` : le temps réel est
celui de l'athlète. La priorité inverse changerait le temps de 7 435 lignes du
panel. 2 925 lignes n'ont pas de chip (tout le cross UK) et 2 092 pas de gun
(tout Windsor) : aucune des deux colonnes n'est utilisable seule. 73 lignes n'ont
ni l'une ni l'autre et sortent sans temps.

---

## D7 — Segments : depuis `type`, libellés en français

**Décision**: un segment par entrée de `legs`, dans l'ordre publié, rangé dans
`ScrapedResult.segments` (chemin générique). Le libellé vient d'une table fermée
appliquée à `leg["type"]` :

| `type` (source) | Libellé stocké |
| --- | --- |
| `Swimming` | `natation` |
| `Transition` | `transition` |
| `Cycling` | `vélo` |
| `Running` | `course à pied` |

**Rationale**: trois raisons de ne pas lire `sportName`, qui serait le choix
naïf : il est saisi par le chronométreur, il n'est pas normalisé (`SWIM` /
`Swim` / `T1`), et il est **absent de 5 635 des 24 042 legs** (23 %) — tout le
cross UK et tout l'Algiers Urban Trail. `type` est présent 24 042 fois sur
24 042 et pris dans un vocabulaire de 4 valeurs.

Le chemin `segments` plutôt que les 5 slots positionnels : les courses d'enfants
publient 4 legs (une seule transition), et un mapping positionnel y ferait
atterrir la course à pied dans le slot `t2`. `segments` prime sur les slots dans
`mapping.build_splits` et n'a pas de plafond.

Libellés français : le vocabulaire source est **fermé et normalisé**, donc la
traduction est sûre — contrairement à un libellé libre, qu'on rendrait verbatim
comme le fait ok-time. Le principe I demande le français pour ce qui est visible
par l'utilisateur, et ces libellés deviennent des en-têtes de colonne dans le
front (`lib/utils/splits.ts`, chemin générique). Un `type` inconnu — hypothèse
non observée — serait rendu verbatim plutôt que perdu.

Les deux transitions d'un triathlon portent le même libellé : `build_splits`
désambiguïse déjà en `transition (2)`, sans écrasement silencieux.

**Alternatives rejetées**:
- *Inclure les `participantSplits` intra-leg* : écarté au cadrage. Deux
  granularités dans un même dict, sans équivalent chez les autres fournisseurs.
- *Mapper vers `swim`/`t1`/`bike`/`t2`/`run`* : ne survit pas aux courses à
  4 legs ni aux mono-sports.

---

## D8 — Le leg fantôme des non-finishers est écarté

**Décision**: un segment dont la durée est vide après `_time()` n'est pas
enregistré.

**Rationale**: un non-finisher publie un leg unique de type `Running`,
`legDuration: "00:00:00"`, dont le seul split s'appelle `Start`. C'est ce qui
explique les 81 « participants à 1 leg » d'une course de triathlon. Le filtrer
par la durée plutôt que par le statut couvre aussi, sans cas particulier, un leg
non chronométré chez un finisher. `build_splits` ignore de toute façon les
segments à valeur vide, mais filtrer en amont garde `raw_data` lisible.

---

## D9 — `event_type` : le `eventType` de la source en appoint

**Décision**: `classify_event_type(raceName, contexte=f"{eventName} {eventType}")`.

**Rationale**: c'est le point le plus contre-intuitif du plan, et il est mesuré.
Le classifieur consulte son contexte uniquement quand l'intitulé ne nomme aucun
sport, et retombe sinon sur `triathlon`. Or les intitulés étrangers ne nomment
souvent aucun sport :

| `raceName` | contexte = `eventName` seul | contexte = `eventName` + `eventType` |
| --- | --- | --- |
| `Senior Men` | **`triathlon`** | `course-a-pied` |
| `Under 13 Girls` | **`triathlon`** | `course-a-pied` |
| `Triathlon S` | `triathlon-s` | `triathlon-s` |
| `Trail 10K` | `trail` | `trail` |

Sans cet appoint, les 2 852 participations du cross UK entreraient en base
classées `triathlon` — s'afficheraient comme telles et **survivraient** au filtre
`federal_only=true`, qui existe précisément pour les exclure. Le champ
`eventType` de la source (`Triathlon`, `Running`) est l'information manquante, et
`Running` est reconnu par le classifieur.

Vérifié sur les 11 intitulés distincts du panel : aucune classification correcte
ne régresse, deux erreurs sont corrigées.

**Alternatives rejetées**:
- *Modifier le classifieur* : il est partagé par tous les fournisseurs et par la
  migration de re-classement ; changer son repli au fil d'un nouveau provider est
  hors périmètre (principe VI).
- *Concaténer `raceName` et `eventName`* : l'erreur explicitement documentée dans
  `AGENTS.md` — elle classait le « Trail 12 km » d'un « Triathlon de X » en
  triathlon.

---

## D10 — `is_relay` décidé au niveau de la course, sur son intitulé

**Décision**: une course est un relais si son intitulé, normalisé sans accents,
contient `relais`, `relay`, `equipe`, `team` ou `duo`. La valeur s'applique à
toutes ses participations.

**Rationale**: décider par course et non par participant, sinon `Course.is_relay`
et `Participation.is_relay` divergent selon l'ordre de lecture (précédent
ok-time). Contrairement à ok-time, aucun repli sur la forme des noms n'est
possible : la source ne publie **pas** de séparateur de coéquipiers — elle publie
une ligne unique par équipe, dont le nom est libre (`LA COUSINADE`,
`Three Feet in the Thames`). L'intitulé de course est le seul signal.

Sur le panel, le motif capte les 4 courses de relais (`Relais Triathlon S/M`,
`Olympic Team Relay`, `Sprint Team Relay`) sans aucun faux positif sur les 28
autres.

**Limite assumée**: une course de relais dont l'intitulé ne le dirait pas sortirait
en individuel, et ses noms d'équipe seraient découpés en prénom/nom. Non observé
au panel.

---

## D11 — Identité : pas de découpage sur un nom d'équipe

**Décision**: sur une course de relais, le nom entier va dans `athlete_name`,
`athlete_firstname` reste vide. Ailleurs, `split_athlete_name(name)`.

**Rationale**: mêmes raisons qu'ok-time (#63) : découper `LA COUSINADE`
fabriquerait un athlète « COUSINADE, LA ». Les `tags` de la source, qui semblent
offrir un découpage tout fait, sont un index de recherche tokenisé sur les
espaces — piège n° 4 du sondage — et produisent la même forme pour une équipe que
pour une personne.

Le découpage garde la limite connue de `split_athlete_name` sur les noms
entièrement majuscules (`ABDELHAMID MOUSSAOUI`), irréductible sans information
supplémentaire que la source ne publie pas.

---

## D12 — Scalaires : zéro et `U` valent « absent »

**Décision**: `_rank(v) = normalize_rank(v) or None` ; `gender` retenu seulement
s'il vaut `M` ou `F`.

**Rationale**: `overallPosition == 0` signifie « non classé » (172 lignes du
panel, toutes non-finishers) ; `normalize_rank` rendrait `0`, qui s'afficherait
comme une place. `gender: "U"` couvre 4 243 lignes (41 %) et n'est pas rendu par
le front : mieux vaut vide qu'une valeur qu'il ne sait pas afficher — même
traitement que le `X` d'ok-time.

---

## D13 — Aucune fixture réseau dans les tests unitaires

**Décision**: fixtures JSON réduites sous `backend/tests/fixtures/sporthive_*.json`,
extraites du panel réel ; `httpx.Client` monkeypatché ; un test `integration`
sépare la vérification du schéma réel.

**Rationale**: principe III, non négociable. Les fixtures couvrent les cas que le
panel a rendus nécessaires : un triathlon à 5 legs, une course d'enfants à
4 legs, un mono-sport sans `sportName`, un non-finisher de chaque type
(`DNF`/`DNS`/`DQ`), une course de relais, une pagination multi-pages, et une
pagination tronquée pour la garde de complétude.
