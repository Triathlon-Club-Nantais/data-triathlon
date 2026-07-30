# Phase 0 — Research : scraper MYLAPS Sporthive

**Feature**: 004-sporthive-scraper | **Date**: 2026-07-29

Toutes les mesures citées viennent du sondage
`docs/superpowers/specs/2026-07-29-sporthive-sondage.md` (7 événements,
32 courses, 10 360 participations). Aucune question de la Technical Context n'est
restée en `NEEDS CLARIFICATION`.

**Révision du 30/07/2026** — la session de clarification `### Session 2026-07-30`
de la spec a tranché cinq points qui touchent D4, D5 et D6, et en ajoute deux
(D14, D15). Les décisions ci-dessous intègrent ces arbitrages ; l'ancienne
version de D4 (refus global sur classement incomplet) est **caduque**.

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

## D4 — Pagination : arrêt sur `last`, plafond dur, complétude vérifiée par course

**Décision**: boucler sur `page` avec `size=10`, s'arrêter quand la réponse porte
`last: true` ou un `content` vide ; **lever** si le plafond `_MAX_PAGES` est
atteint ; puis **vérifier** que le nombre de participants lus est au moins égal au
`classificationsCount` annoncé par `/events/{id}/races` — et, si la vérification
échoue, **écarter cette seule course** plutôt que l'événement entier (FR-008).

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

**Granularité — deux portées, pas une** (arbitrage du 30/07, FR-008 / FR-009) :

| Défaillance | Portée | Mise en œuvre |
| --- | --- | --- |
| Classement incomplet (garde 3) | la **course** seule | exception interne `_IncompleteRanking`, rattrapée par la boucle de `scrape_event_all`, journalisée, course suivante |
| `_MAX_PAGES` atteint (garde 2) | l'**événement** | `ValueError` propagée : l'invariant d'arrêt est faux, rien ne dit qu'il le serait moins sur la course suivante |

L'exception interne est un type **privé** du module, pas une `ValueError` filtrée
sur son message : trier des défaillances au motif d'un texte se casse à la
première reformulation, et l'infra emballe déjà les `ValueError` du scraper
(`import_service._scrape_all`).

La course écartée est journalisée en `logger.warning` avec son intitulé, son
`activeRaceId` et les deux décomptes (FR-008a). Ce journal est la **seule** trace :
le bilan de la CLI compte des épreuves (une par `source_url`), donc l'épreuve
ressort en succès avec 5 courses sur 6. C'est le prix accepté de l'écart par
course, et la raison pour laquelle le message de log doit être exploitable seul.

**Alternatives rejetées**:
- *Borner la boucle sur `totalPages`* : c'est borner sur un total annoncé, la
  faute que runnerbreizh a payée. Le total sert à **vérifier**, pas à cadencer.
- *Se fier à `count`/`offset`* (l'énoncé de l'issue) : silencieusement ignorés
  par le serveur, la boucle relirait les 10 mêmes lignes indéfiniment.
- *Demander `size=50`* : rejeté en 400 par le serveur.
- *Refuser l'événement entier sur une course tronquée* (version précédente de
  cette décision) : écarté au cadrage du 30/07. Une course durablement tronquée
  côté source rendait l'événement définitivement non importable, membres du TCN
  des cinq autres courses compris.
- *Remonter la course écartée jusqu'au bilan de la CLI* : demanderait un canal
  d'avertissement par épreuve dans `ScrapedResult` puis dans `import_service` et
  `batch` — un contrat traversé pour un cas non observé au panel (principe VI).

---

## D5 — Statut : `validity` seul, complété par le rang quand aucun temps n'est publié

**Décision**: `status = derive_status_from_label(participant["validity"])`. Les
booléens `dns` et `dsq` ne sont **jamais** lus. Quand `validity` ne dit rien
**et** qu'aucun temps n'a pu être retenu, le scraper **tranche lui-même** sur le
rang (FR-014a) :

```python
status = derive_status_from_label(raw.get("validity", ""))
if not status and not total_time:
    status = STATUS_FINISHER if rank_overall is not None else STATUS_DNF
```

**Rationale**: sur les 10 360 lignes du panel, `dns` et `dsq` valent `false`
10 360 fois, y compris sur les 35 lignes dont `validity == "DNS"`. `validity`
porte les trois valeurs réelles (`DNF` 129, `DNS` 35, `DQ` 8), et
`utils.derive_status_from_label` les traduit déjà toutes les trois — `dq` y
figure depuis T2Area.

Un `validity` absent rendrait `""`, et `mapping.derive_status` appliquerait alors
son heuristique — « finisher si temps total, **sinon DNF** ». Or 73 lignes du
panel n'ont ni `chipTime` ni `gunTime` (D6) tout en étant **classées** par la
source : l'heuristique générique les afficherait en abandon dans la colonne Place
du front. C'est le travers déjà payé sur ok-time (`AGENTS.md` : « un seul temps
saisi à la main suffisait à désarmer le repli, faisant classer toute une course
d'enfants DNF »). Le scraper renseigne donc `status` explicitement — ce que le
contrat de `ScrapedResult` prévoit (`""` = « le scraper ne se prononce pas » ;
prolivesport le renseigne déjà) — au lieu de déléguer à un repli conçu pour les
sources muettes.

S'appuyer sur le rang n'est pas deviner : `overallPosition == 0` et `validity`
renseigné se recouvrent 172 fois sur 172 (D12), donc la source **dit** qui elle
classe. Et le couplage reste propre : `STATUS_FINISHER` / `STATUS_DNF` vivent
dans `scrapers/base.py`, la couche la plus basse — aucun import de `services/`
depuis un scraper (principe II).

**Alternatives rejetées**:
- *Croiser `validity` avec `overallPosition == 0` pour **déduire** le statut* :
  redondant, deux sources pour une même information finissent par diverger. La
  décision ci-dessus n'en fait rien de tel : le rang ne sert qu'à trancher le cas
  où la source est muette **et** sans temps.
- *Laisser l'heuristique générique s'appliquer* : version précédente de cette
  décision, écartée au cadrage du 30/07 (73 lignes classées en abandon).
- *Modifier `mapping.derive_status`* : partagé par les douze fournisseurs ;
  changer son repli au fil d'un nouveau provider est hors périmètre (principe VI).

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
ni l'une ni l'autre et sortent **sans temps mais classées finisher** dès lors que
la source leur donne un rang — le statut est tranché en D5, pas ici.

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

Les arbitrages du 30/07 ajoutent trois cas de test, tous construits à la main
depuis les fixtures existantes plutôt que capturés (aucun n'est présent au
panel) : une course à `classificationsCount: 0` (D14), un événement dont toutes
les courses sont écartées (D14), et un participant sans `chipTime` ni `gunTime`
ni `validity` mais avec un `overallPosition` non nul (D5).

---

## D14 — Course sans classé ignorée ; aucune course importable = échec

**Décision**: deux règles complémentaires, décidées au cadrage du 30/07
(FR-008b, FR-008c) :

1. Une course dont `classificationsCount` est nul ou absent est **ignorée sans
   requête de participants**, avec un `logger.info`. Aucune `Course` n'est créée.
2. Si, une fois toutes les courses traitées, la liste de `ScrapedResult` est
   **vide**, `scrape_event_all` lève une `ValueError` en français nommant la
   cause. Un import qui n'importe rien n'est jamais un succès.

**Rationale**: la règle 1 tient à un enchaînement mesurable dans le code
existant. Une `Course` sans aucune participation n'a jamais de participation sans
`total_time`, donc `cache.is_in_progress` la déclare terminée et
`cache.ttl_seconds` lui applique `CACHE_TTL_FINISHED_SECONDS` (30 j). Comme
`course_repository.get_latest_by_source_url` sélectionne **une** course par
`source_url` et que les six courses d'un événement Sporthive partagent la même,
une course vide peut devenir celle qui répond pour tout l'événement — et geler
son re-scrape un mois. Le coût d'une épreuve fantôme n'est donc pas seulement
cosmétique (listes, stats, carte) : elle bloque le rattrapage.

La règle 2 ferme le trou ouvert par l'écart au niveau de la course (D4) :
`import_service._require_event_name` ne lève **pas** sur une liste vide
(`any()` sur une liste vide est faux) et « aucun résultat » est un court-circuit
que `batch` compte en **succès**. Sans la règle 2, un événement intégralement
tronqué serait indiscernable au bilan d'un import réussi — l'inverse exact de ce
que `est_echec_total` garantit au niveau du lot.

Le message est en **français** : il traverse `ScraperError` (`import_service`),
que `register_exception_handlers` sérialise en `{"detail": …}` et que le front
réaffiche verbatim — cas mixte explicitement traité par le principe I.

**Alternatives rejetées**:
- *Paginer quand même une course annoncée à zéro classé pour vérifier* : une
  requête par course vide pour un cas non observé, et le plancher de D4 rattrape
  déjà l'incohérence inverse (count > 0, zéro ligne lue → course écartée). La
  clause « jamais d'épreuve sans participation » reste donc garantie deux fois.
- *Créer l'épreuve vide pour tracer que la course existe* : décrit ci-dessus, elle
  gèle le cache de l'événement entier.
- *Compter la course vide comme un échec de l'épreuve* : un événement dont une
  seule course n'est pas encore publiée deviendrait non importable — c'est le cas
  nominal d'un événement en cours de publication.

---

## D15 — Lieu et pays conservés en `raw_data`, non branchés sur le géocodage

**Décision**: `raw_data["city"] = event["location"]` (verbatim) et
`raw_data["country"] = event["countryCode"]`. Aucun autre usage (FR-022a).

**Rationale**: `location` vaut mieux que ce que la carte déduira du nom
d'épreuve — vérifié en exécutant `geocode_service.extract_city` sur le cas du
Sheet, qui rend `« Sud Vendee Dimanche »` là où la source publie
`« L'Aiguillon sur Mer (85) »`. Mais `ScrapedResult` **n'a pas** de champ ville :
lui en ajouter un toucherait un contrat partagé par les douze fournisseurs pour
le bénéfice d'un seul (principe VI). La clé `city` est celle que runnerbreizh
utilise déjà pour exactement cette raison — un futur branchement du géocodage
n'aura donc qu'une clé à lire, pas deux conventions à réconcilier.

Le `country` a son propre intérêt : `_nominatim_search` interroge Nominatim avec
`countrycodes=fr` et une requête `f"{city}, France"`, donc les épreuves
britanniques, allemandes et algériennes du panel ne sont pas géocodables — le
code pays est la seule donnée qui permette de le **savoir** plutôt que de
constater un échec de géocodage muet. Il est conservé tel que publié, sans
homogénéisation : le sondage relève des codes à 2 et 3 lettres (`FRA`, `UK`,
`DE`), et normaliser à l'aveugle ferait perdre l'information brute.

**Limite assumée**: le verbatim porte parfois un numéro de département
(`(85)`), donc il n'est pas directement injectable dans une requête Nominatim.
Le nettoyage appartiendra au futur consommateur, qui seul saura ce qu'il exige.

**Alternatives rejetées**:
- *Ajouter `city` / `country` à `ScrapedResult` et brancher le géocodage* : hors
  périmètre d'un nouveau provider, et changerait le comportement de la carte pour
  tous les autres.
- *Ne rien conserver* : le jour où la carte saura s'en servir, il faudrait
  re-scraper le panel (≈ 1 000 requêtes) pour une donnée déjà passée sous les
  yeux du scraper.
