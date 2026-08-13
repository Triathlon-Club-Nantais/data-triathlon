# prolivesport.fr (issue #269)

prolivesport.fr est une SPA Angular adossée à une API JSON publique
(`api.prolivesport.fr/apiws`), ouverte par un token codé en dur dans le bundle
(`access-token: AUTH_PLSWS_V2`). Quatre routes servent l'import :
`event/detail/{eventId}/` (nom + date), `result/raceList/{eventId}/` (les
courses), `result/indiv/{eventId}/{race}/` (les lignes) et
`result/splitDetail/{eventId}/` (les points de passage). Il n'existe **aucune
alternative** à ce couple `raceList` + `indiv` : les routes d'apparence plus
propre repérées dans le bundle (`/events/{id}/races`,
`/events/{id}/races/{raceId}/results`) répondent
`{"success":false,"message":"wrong param"}` — elles ne sont pas déployées. Vérité
d'API mesurée (36 lignes du Sheet, 5 groupes d'URL, 4 `eventId`, 28 courses) :
`docs/superpowers/specs/2026-08-11-prolivesport-fanout-sondage.md`.

## Le piège central : `race` n'est pas un filtre

`GET result/indiv/{eventId}/{race}/` **ignore silencieusement** le segment `race`
sur une partie des événements et renvoie l'**événement entier**. Mesuré :
`indiv/979/Triathlon M/` rend 815 lignes dont 479 ne sont pas des Triathlon M ;
`indiv/1060/CHTRI XS/` rend les 11 courses de l'événement ; `indiv/1082/M/` et
`indiv/1082/PO-PU/`, eux, honorent le filtre. La corrélation observée — le filtre
tombe dès que le code de course porte un **espace ou un tiret bas** — est parfaite
sur le panel, mais **l'implémentation ne s'y fie pas** : la seule vérité est le
champ `race` porté par chaque ligne, et le regroupement se fait toujours côté
client (`_lignes_par_course`).

S'y fier était le défaut que #269 corrige, et il pesait bien plus lourd que les
courses manquantes : le scraper mono-course versait l'événement entier dans une
`Course` unique, soit ~4 000 participations aux rangs, temps et types d'épreuve
faux — et l'événement stocké **autant de fois** qu'il avait de lignes dans le
Sheet (l'événement 979 en avait deux, `race=Triathlon M` et `race=Triathlon S`,
recevant les mêmes 815 lignes sous deux libellés). À comparer aux **7
participations TCN** que le fan-out seul rapporte. Les deux ne sont pas
séparables : sans regroupement côté client, le fan-out **multiplierait** le
défaut au lieu de le corriger, en produisant N courses portant chacune
l'événement entier.

## Fan-out par course (#269)

Le `&race=` de l'URL est **ignoré** sur le chemin nominal : le fan-out énumère
`raceList`. Contrat du patron Klikego (#156) — `cache_probe(sub_url)` saute une
course fraîche (comptée dans `heats_cached` + `cached_urls`, jamais notifiée à
`on_heat_start`), échec isolé par course dans `trace.failures`,
`on_heat_start(slug, label, index, total)` avec `total` = nombre **à scraper**.
Trois particularités du fournisseur s'y ajoutent :

- **Une réponse qui déborde de la course demandée est l'événement entier**, et
  elle est réutilisée pour toutes les autres courses. Sur l'événement 1060, un
  seul GET rend les 11 courses : en refaire 11 de 14,7 Mo serait absurde.
- **`on_heat_start` est notifié pour chaque course à scraper**, y compris celles
  servies par une réponse déjà en main : la progression compte les courses
  importées, pas les requêtes émises.
- **Une course d'abord en échec puis rattrapée** par une réponse « événement
  entier » plus tardive sort de `trace.failures` : la laisser alors que ses
  participations sont importées casserait l'invariant
  `enumerated = imported + cached + len(failures)` dont `import_service` déduit
  `heats_imported`.

`scrape_event_all(url)` reste l'échappatoire `--single-heat` : une seule course,
celle que l'URL désigne — **filtrée elle aussi**, sans quoi l'échappatoire
reconstruirait le fourre-tout.

## URL canonique de sous-unité

`_sub_source_url` produit
`index.php?chap=event&sub=liveV3&eventId={id}&race={quote(race)}`, employée à la
fois comme clé de `cache_probe` et comme `ScrapedResult.source_url`. La forme
doit être **identique caractère pour caractère** à celle des liens du Sheet :
`Course` est retrouvée par égalité exacte de `source_url`
(`course_repository.get_latest_by_source_url`), donc un `+` au lieu de `%20`
créerait un doublon au lieu de réécrire la `Course` existante.

Conséquence assumée de la réparation par re-scrape seul, sans purge : les
`Course` nées des formes **nue** (`/V2/result/1060`) et **positionnelle**
(`/result/1082/4`, où `4` désignait la 5ᵉ entrée du `raceList` — donc une course
différente dès que la source réordonne) portent des `source_url` que le fan-out
ne produira **plus jamais**. Elles restent en base avec leur contenu fourre-tout
jusqu'à suppression manuelle ; les 26 lignes en forme `?race=` sont, elles,
réécrites en place.

## Reprise sur les 500 intermittents

Les réponses « événement entier » pèsent jusqu'à 14,7 Mo et la source rend des
**500 à corps vide** dessus : mesuré 3 échecs d'affilée sur `indiv/1082/M_relay/`
puis succès, 4 sur `indiv/1082/S_Light/`. D'où `_ESSAIS_INDIV = 5`, sans
temporisation entre les essais (les 500 arrivent immédiatement, ils ne signalent
pas une surcharge à laisser passer) — et seuls les **5xx** sont rejoués, un 4xx ou
un `success: false` disent quelque chose de la requête. Sans cette reprise **et**
l'isolation d'échec par course, les plus gros événements échoueraient
régulièrement en entier.

## Ce que porte chaque course

`event_type` vient de `classify_event_type(race)` — le code de la course, plus le
jeton de l'URL : les 815 lignes de l'événement 979 étaient toutes typées
`triathlon-m`, XS et S comprises. Le nom est qualifié par la course
(`qualify_event_name`) : sans quoi les courses fusionnent en une seule `Course` et
leurs dossards entrent en collision (#21). Les splits viennent d'**un seul**
`splitDetail` pour l'événement, filtré par course : construire la carte pour une
course et l'appliquer aux autres effaçait les splits de `CHTRIMAN 113` et
`CHTRIMAN 226` sur l'événement 1060, la carte étant bâtie pour « CHTRI 6-7 ans »
qui n'en publie aucun.

## `/fftri/<slug>` : une page de série, non résoluble

Trois lignes du Sheet sont de la forme `/fftri/grand-prix-duathlon`. C'est une
page de **série** (un Grand Prix et ses étapes), pas une épreuve — même nature
que le cas Competitor / ironman.com : dans le bundle, ce chemin est un `href`
codé en dur. La coquille SPA de 80 Ko ne porte aucun `eventId` ni aucune mention
du sport, le contenu est rendu côté navigateur, et le repli Playwright a été
supprimé avec sa dépendance (#102). L'API de série existe
(`pls-erp/FFTRI/GP/get-stage/`, `ranking-team-general/`, `ranking-team-stage/`)
mais est derrière un **JWT codé en dur dans le bundle, expiré depuis le
2025-04-07** ; sans en-tête conforme elle rend `HTTP 412`.

La résolution slug → `eventId` n'est donc **pas atteignable**, et le seul livrable
honnête est un message d'erreur qui dit ce qu'est l'URL. `_parse_url` lève une
`ValueError` explicite, que `import_service` traduit en
`ProviderNotSupportedError` **en conservant le message** — sans elle, l'opérateur
lisait « Fournisseur de chronométrage non supporté » alors que ProLiveSport
*est* supporté. La correction des 3 lignes se fait **dans le Sheet**, en pointant
l'étape voulue.

## Rôles de split ambigus : champs cumulés écartés, résolution par candidat unique (#280)

Un rôle (`swim`/`t1`/`bike`/`t2`/`run`) peut avoir plusieurs champs candidats
— mesuré sur l'événement 979 : `bike` reçoit `Bike`, `BikeStart` **et**
`BikeEnd` (les trois contiennent la sous-chaîne `"bike"`), `run` reçoit `Run`
**et** `RunStart`. Le sondage
(`docs/superpowers/specs/2026-08-12-prolivesport-splits-sondage.md`, constat
n°3) établit que le champ nommé exactement par la discipline (`Bike`, `Run`)
est une durée de section fiable (la somme des 5 champs canoniques colle au
temps total à 2 s près), tandis que les variantes `*Start`/`*End` sont des
points cumulés depuis le départ — la même information sous une autre forme,
pas une donnée supplémentaire (`BikeStart` == `Swim`+`T1`, `BikeEnd` ==
`Swim`+`T1`+`Bike`, `RunStart` == `Swim`+`T1`+`Bike`+`T2`, à 1 s près).

**Règle retenue** : un champ dont le libellé finit par `start`/`end`
(`_est_cumule`) n'entre jamais en candidature pour un rôle — il n'ajoute
aucune information que la durée directe ne porte déjà. Sur 979, ceci laisse
`Bike` seul candidat pour `bike`, `Run` seul candidat pour `run` : les deux se
résolvent normalement dans leur slot positionnel, comme n'importe quel rôle à
candidat unique, et `bike_time`/`run_time` sont peuplés (vérifié en réseau
réel, dossard 245 : `00:51:31`/`00:30:25`, la valeur citée par l'issue).

Le repli en `ScrapedResult.segments` reste le garde-fou pour une ambiguïté
**réelle** — deux candidats non cumulés pour un même rôle, jamais mesurée à ce
jour sur le panel du sondage : aucun slot positionnel n'est alors renseigné
pour **toute la course** (y compris les rôles non ambigus), tous ses champs
partent dans `segments`, triés par suffixe numérique de champ, avec le
libellé source conservé tel quel. Le « tout ou rien » vient de
`services/mapping.build_splits`, qui fait primer `segments` en entier sur les
5 slots dès qu'il est renseigné : laisser un rôle non ambigu dans son slot
alors que `segments` est actif le ferait disparaître de
`Participation.splits`. Détail : `docs/superpowers/specs/2026-08-12-prolivesport-splits-design.md`
(règle affinée après revue humaine du rendu frontend — le repli `segments`
systématique sur 979 produisait un tableau à 14 colonnes pour 2 des 28 courses
du panel, alors que le sondage donnait déjà de quoi trancher).

Les libellés génériques sans rapport avec les 5 rôles connus (`SplitN` sur
1082/1079, `SportN` sur les événements duathlon comme 1060) restent hors
`splits`/`segments` quand ils n'accompagnent aucune ambiguïté — deviner leur
discipline romprait le principe de simplicité. Ils restent lisibles dans
`raw_data` (`timeT9`, `timeSport2`…), ce qui suffit au critère « rien n'est
perdu ».
