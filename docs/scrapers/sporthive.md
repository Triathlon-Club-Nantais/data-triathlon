# Sporthive (MYLAPS)

**Sporthive** (MYLAPS, issue #53) se lit sur une **API JSON publique** — aucune
clé, aucun cookie, ni Playwright ni parsing HTML. Elle vit sur
`eventresults-api.speedhive.com/sporthive`, MYLAPS ayant fondu Sporthive dans
Speedhive : l'hôte annoncé par l'issue est **mort** (son certificat ne couvre
plus le nom) et la route `classifications/search` n'existe plus. Si l'API
redéménage, l'adresse fait autorité dans `GET sporthive.com/api/clientSettings`,
pas dans le code. Le provider déclare le seul host `sporthive.com` — le
sous-domaine `results.` en découle — et **jamais** l'hôte d'API, qu'on appelle
sans le reconnaître.

Trois profondeurs d'URL désignent le même événement et sont toutes acceptées :
événement (`/events/{id}`), course (`/events/{id}/races/{n}`) et dossard
(`…/bib/{b}[/split]`), avec le préfixe de langue (`/en/events/…`) et le segment
`s/` vers lequel mène la redirection 307. Un import remonte toujours à
l'**événement entier** : le Sheet ne porte qu'un lien par épreuve, et un membre
inscrit sur un autre format y serait invisible.

**Deux familles d'identifiants** cohabitent sur ces mêmes routes : le
**snowflake** à 19 chiffres du fonds historique, et le **GUID** des événements
récents (`bdea2f10-1510-481c-b5ef-ef7f1926a06f`). L'API ne les distingue pas et
la page d'accueil publie les deux. Un motif `\d+` refusait donc tout le fonds
récent **avant tout appel**, en affirmant l'URL illisible alors que le site la
sert. La branche GUID reste **strictement** formée (8-4-4-4-12) : l'élargir à
`[^/]+` laisserait passer `/events/abc` et déclencherait une requête qui ne peut
que 400 — c'est le refus qui nomme la forme attendue.

Quatre pièges, tous mesurés, à ne jamais réintroduire :

- **`races/{n}` n'est pas un `raceId`** mais un ordinal *local* (`activeRaceId`).
  `GET /races/1` répond **200** et rend une épreuve de 2015 sans rapport : la
  prendre pour la course demandée importerait une épreuve étrangère sous la
  `source_url`, sans la moindre erreur. `_parse_url` rend donc l'identifiant
  d'événement **et rien d'autre** — un `str` nu, pas un couple : le piège est
  fermé par construction, pas par une garde à maintenir. Le vrai identifiant est
  le champ `id` (snowflake à 19 chiffres) de `/events/{id}/races` ; sur 32
  courses sondées, `id` égale le segment d'URL **0 fois**, `activeRaceId` **32
  fois**.
- **`size` est plafonné à 10** côté serveur (`size=50` → 400), et
  `count`/`offset` — les paramètres annoncés par l'issue — sont acceptés mais
  **silencieusement ignorés** : paginer avec eux relit les dix mêmes lignes
  indéfiniment. D'où ≈ 100 requêtes pour l'épreuve du Sheet (955 classés), et
  aucun export CSV pour y échapper. L'arrêt se fait sur `last` puis sur une page
  vide, jamais sur `totalPages` : borner sur un total annoncé est la faute que
  runnerbreizh a payée — le total sert à **vérifier** après coup
  (`classificationsCount`, égalité constatée 32 fois sur 32).
- **le statut vit dans `validity`** (`DNF`/`DNS`/`DQ` — noter `DQ`), et les
  booléens `dns`/`dsq` sont **morts** : `false` sur 10 360 lignes sur 10 360, y
  compris les 35 en `DNS`. S'y fier rate 100 % des statuts.
- **`legs[].sportName` ment** : saisi par le chronométreur, non normalisé
  (`SWIM`/`Swim`/`T1`) et `null` sur 23 % des legs. `legs[].type` prime donc
  (24 042/24 042) — d'où les libellés `natation`/`transition`/`vélo`/`course à
  pied`, rangés dans `segments` (chemin générique) et non dans les 5 slots
  positionnels : une course d'enfants publie **4** legs et un mapping positionnel
  ferait atterrir sa course à pied en `t2`. Mais `type` **peut valoir `Other`**,
  et il ne discrimine alors rien : sur les cinq legs de la course « Standard »
  de Jersey (177 classés), natation comprise, et sur les deux transitions
  d'Izvorani 2026. Rendu verbatim, cela publiait `Other`, `Other (2)` …
  `Other (5)` après désambiguïsation par `build_splits` — cinq fois le même
  non-mot là où `sportName` nomme correctement. D'où le **repli** : `type`
  d'abord, `sportName` quand `type` se tait, le `type` brut si les deux se
  taisent (mieux vaut un libellé pauvre qu'un temps perdu).

**Deux portées d'échec**, et c'est le choix structurant du module. Une course au
classement incomplet est **écartée** (`_IncompleteRankingError`, type privé rattrapé
par la boucle, journalisé avec intitulé, ordinal et les deux décomptes) : les
autres courses de l'événement s'importent. Refuser l'événement entier rendait
une course durablement tronquée côté source définitivement non importable,
membres du TCN des cinq autres courses compris. L'**événement** est refusé
(`ValueError`) sur URL illisible, événement inconnu (404), plafond de pagination
atteint, ou **aucune course importable** — ce dernier garde-fou parce que
`import_service._require_event_name` ne lève pas sur une liste vide et que
`batch` compte « aucun résultat » en succès : un import à zéro course passerait
sinon pour réussi. Contrepartie assumée de l'écart par course : le bilan CLI
comptant des épreuves, une épreuve ressort en succès à 5 courses sur 6, et seul
le `logger.warning` en garde la trace.

Deux règles de valeurs qui ne se devinent pas. Le **statut est tranché sur le
rang** quand `validity` se tait *et* qu'aucun temps n'est retenu : `finisher` si
classé, `DNF` sinon — sans quoi les 73 lignes sans `chipTime` ni `gunTime` mais
**classées** par la source s'afficheraient en abandon, le travers déjà payé sur
ok-time. Et une course annoncée à **zéro classé est sautée sans requête** : une
`Course` vide n'a aucune participation sans `total_time`, donc `cache` la déclare
terminée — et comme les six courses d'un événement partagent une `source_url`,
elle peut devenir celle qui répond pour tout l'événement et geler son re-scrape
30 jours.

Détails de lecture : temps en `HH:MM:SS`, `HH:MM:SS.fffffff` ou `HH:MM:SS.fff`
selon la course — la fraction se tronque **avant** `normalize_time`, dont le
motif est ancré en fin de chaîne et qui rendrait `00:57:33.2510000` tel quel ;
`00:00:00` vaut temps absent ; `overallPosition: 0` vaut rang absent ;
`gender: "U"` (41 % des lignes) sort vide. `eventType` de la source sert
d'**appoint** au classifieur (`classify_event_type(raceName, contexte=…)`) : sans
lui, `Senior Men` ne nommant aucun sport, les 2 852 lignes du cross UK entraient
en `triathlon` et **survivaient** à `federal_only=true`. Les relais publient
**une ligne par équipe** (l'inverse de runnerbreizh) au nom libre
(`LA COUSINADE`) : `is_relay` est décidé sur l'intitulé de **course**, et le nom
d'équipe n'est jamais passé à `split_athlete_name`. Les `tags`, qui semblent
offrir un découpage prénom/nom, sont un index de recherche tokenisé. `location`
et `countryCode` de l'événement sont conservés en `raw_data["city"]` /
`["country"]` (même clé que runnerbreizh), **non** branchés sur le géocodage ;
la nationalité du participant, que `country` écraserait, vit en
`raw_data["athlete_country"]`.

Trois limites assumées : les **sous-classements** dupliquent des participations
(le cross UK publie `Senior Men` *et* `Senior Men 9 to count`, dont les 90
dossards sont tous dans les 294) et rien dans le JSON ne les marque — tout est
importé, dans des `Course` distinctes ; `qualify_event_name` ne qualifie **pas**
« Triathlon S » de « Triathlon Sud Vendee Dimanche », son court-circuit testant
la sous-chaîne (sans conséquence #21 ici, les 6 noms restant distincts) ; et une
course de relais dont l'intitulé ne le dirait pas sortirait en individuel.

Sondage de l'API réelle (fait autorité — 7 événements, 32 courses, 10 360
participations, 1 063 requêtes) :
`docs/superpowers/specs/2026-07-29-sporthive-sondage.md`, **addendum du
30/07/2026** compris — re-sondage sur 11 événements / 6 pays d'où viennent les
deux corrections ci-dessus (familles d'identifiants, `type: "Other"`). Spec,
plan et tâches : `specs/004-sporthive-scraper/`.
