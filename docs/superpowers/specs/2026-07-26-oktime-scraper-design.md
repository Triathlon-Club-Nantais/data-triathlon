# ok-time.fr — scraper sur API JSON WordPress (issue #52)

Statut : design approuvé, prêt à planifier.
Sous-issue de #33, section B (nouveaux moteurs).

`classement.ok-time.fr` est une SPA React, mais toutes les données transitent par
une API JSON WordPress publique. **Un seul appel** rend l'événement entier :

```
GET https://ok-time.fr/wp-json/gmcap/v1/evenements/{eventId}/results
```

Ni Playwright, ni parsing HTML sur le chemin nominal.

## 1. Vérité d'API — panel de référence

Tout ce qui suit est **mesuré**, sur un panel constitué depuis le sitemap du site
(370 événements, dont 32 multisports) le 2026-07-26 :

**21 événements, 99 courses, 12 644 participations.**
Triathlons (Lacanau, Mimizan, du Lac, Hostens, Brive, Palmyre), duathlons
(Périgueux, Neuville), swimruns (Côte Beauté, Val de Vienne), bike & run,
trails et courses sur route. Aucun champ divergent d'un événement à l'autre :
le schéma est stable.

### 1.1 Forme de la charge

```jsonc
{
  "success": true, "evenement_id": 48555,
  "evenement_title": "Triathlon de Lacanau 2026 (Samedi 02 mai)",
  "count": 5,
  "data": [{
    "title_course": "Triathlon L Individuel", "epreuve_id": 59697,
    "date_course": "02/05/2026", "distance_course": "110,000",
    "status": "finish",
    "runners": [{
      "nom": "Valentin ROUVIER", "sexe": "M", "dossard": 1217, "club": "",
      "categorie": "Senior", "categorie_abbrev": "SE",
      "temps_finish": "03:31:57", "temp-reel": null,
      "classement_general": 1, "classement_categorie": 1, "classement_sexe": 1,
      "rgpd": "O", "abandon": "N", "disqualifie": "N", "pris_depart": "O",
      "points_de_passage": [{"id": "11|1", "nom": "NATATION", "time": "00:23:56"}, …]
    }]
  }]
}
```

### 1.2 Mesures qui commandent le design

| Observation | Mesure |
| --- | --- |
| `points_de_passage` en temps **cumulés**, croissants | 4 512 / 4 522 participations à ≥ 2 points |
| … exceptions : ordre incohérent à la source (Mimizan : `Vélo 01:30:46` puis `T2 01:30:19`) | 10 |
| Le dernier point **n'est pas** toujours l'arrivée (épreuves finissant sur « Départ CAP2 ») | 392 / 4 541 divergent de `temps_finish` |
| `id` de point de passage **non sémantique** : `12|2` vaut « T2 » ici, « VELO » là | 5 structures d'id pour un même motif triathlon |
| Statuts explicites : `pris_depart='N'` / `abandon='O'` / `disqualifie='O'` | 617 / 160 / 52 (1 participation cumule les deux premiers) |
| `classement_general = 0` chez des finishers valides (= non classé) | 1 336 / 11 816 |
| `rgpd: "N"` → nom anonymisé à la source (`"T... B..."`), club vidé | 66 |
| Mojibake cp1252 dans `nom` (`AnaÃ¯s` pour `Anaïs`), concentré sur les 4 événements les plus anciens du panel | 173 participations / 156 noms distincts |
| … mojibake dans `club` ou `categorie` | 0 |
| Entités HTML brutes dans les titres (`&#8211;`, `&#038;`) | tous les titres concernés |
| `club` renseigné | 6 012 / 12 644 (0 à Lacanau 2026, 1 214/1 336 à Mimizan) |
| `temps_finish` toujours `hh:mm:ss`, `"00:00:00"` quand absent | 12 644 |
| Courses à `status: ""` — **aucun** participant chronométré | 11 courses / 1 035 participations |
| Courses à `status: "finish"` entièrement non chronométrées (courses enfants) | 3 courses / 52 participations |

### 1.3 Erreurs de l'API

Distinguées à la source, donc traduisibles en messages utiles :

| Cas | Réponse |
| --- | --- |
| Id inconnu | `404` — `"Ce post n'est pas un evenement."` |
| Événement sans résultats publiés | `400` — `"Aucun fichier_gmcap défini pour cet evenement."` |
| Id d'**épreuve** au lieu d'événement (`59697`) | `404` — seul l'id d'événement est accepté |

L'API n'expose que deux routes (`/evenements/{id}/results`, `/runner/{id}`) : il
n'existe pas de route par épreuve. Une URL pointant une épreuve rapporte donc
toujours l'événement entier.

## 2. Résolution de l'URL

Deux formes acceptées ; une seule requête API dans les deux cas.

| Forme | Traitement |
| --- | --- |
| `classement.ok-time.fr/<id>[/race/<raceId>]` | id lu dans le chemin ; `race/<raceId>` **ignoré** (l'API ne sait pas filtrer) |
| `ok-time.fr/evenement/<slug>/` | 1 GET HTML, id lu dans le lien `classement.ok-time.fr/<id>` de la page |

L'id de l'URL de classement **est** le post-id WordPress attendu par l'API
(vérifié sur 21 événements) : aucune table de correspondance à maintenir.

### 2.1 Les URLs du Sheet, et un effet de bord à connaître

Les 4 occurrences du Sheet ne se valent pas :

| URL | État au 2026-07-26 |
| --- | --- |
| `classement.ok-time.fr/48555/race/59697` | vivante |
| `ok-time.fr/course/format-s-individuel-3/` | **404** |
| `ok-time.fr/competition/t24-ile-de-re-2025/` | **404** |
| `ok-time.fr/course/triathlon-l/` | 200, mais redirigée vers le listing générique — aucun id |

Les préfixes `/course/` et `/competition/` sont des formes **obsolètes** du site,
qui publie aujourd'hui sous `/evenement/<slug>/`. Elles ne sont pas supportées :
il n'y a rien à en tirer, et les faire résoudre par recherche dans l'annuaire
coûterait une heuristique de correspondance pour trois URLs mortes.

**Conséquence à anticiper** : `ok-time.fr` devenant un host supporté, ces trois
URLs quittent `ignored_by_host` et deviennent des **épreuves en erreur** dans les
bilans CLI. C'est le comportement correct — une URL supportée qui échoue doit se
voir —, mais cela fera apparaître trois échecs stables à l'import de masse
jusqu'à correction du Sheet. Le message d'erreur les qualifie explicitement
d'URLs obsolètes, pour que le détail des échecs se lise sans enquête.

## 3. Une `Course` par épreuve de l'événement

L'API rend toutes les épreuves ; on les importe toutes, comme les heats Breizh
Chrono et les onglets chronoplace.

- **Nom** — `qualify_event_name(evenement_title, title_course)` →
  « Triathlon de Lacanau 2026 (Samedi 02 mai) - Triathlon L Individuel ».
  Sans le titre d'épreuve, les 5 épreuves de Lacanau, qui partagent date et
  type, fusionneraient sur `uq_course_identity` et leurs dossards entreraient en
  collision (issue #21).
- **Type** — `classify_event_type(f"{evenement_title} {title_course}")`, sur la
  **concaténation**. Le titre d'épreuve seul est trompeur : « Format M
  individuel » du SwimRun Côte Beauté sort en `triathlon-m`, « La Bourriquette »
  du Trail du Bourraid en `triathlon`. Vérifié sur les 99 courses : la
  concaténation corrige 5 courses et n'en dégrade aucune. Elle reste correcte
  quand les deux titres se contredisent — « Aquathlon 10 13 ans » dans
  « Triathlon de Lacanau » sort bien en `aquathlon`.
- **Date** — `date_course`, `dd/mm/yyyy` sur les 99 courses.
- **`distance_km`** — `distance_course`, virgule décimale (`"27,5"` → `27.5`),
  renseignée partout. Évite le repli sur l'extraction depuis le nom, qui lit
  « Course chronométrée 9,5 km » comme un 5 km.
- **`html.unescape`** sur les deux titres avant tout usage — nom, classification
  et détection de relais. Sans cela, `&#8211;` part en base tel quel.

### 3.1 Courses écartées : les listes d'engagés

Une course est **ignorée** si `status != "finish"` **et** qu'aucun de ses
participants n'a de temps. Les 11 courses concernées sont des épreuves inscrites
mais pas encore courues (Triathlon du Lac 2026) : les importer créerait 1 035
participations sans temps, que l'heuristique du projet classerait DNF.

La double condition est délibérée. Un `status` non `"finish"` ne suffit pas :
le comportement du champ sur une course **en cours** n'a pas été observé au
panel, et écarter sur ce seul critère risquerait de jeter des résultats
partiels. Exiger en plus l'absence totale de temps ne peut écarter qu'une liste
d'engagés.

## 4. Participants

### 4.1 Identité

`split_athlete_name` (convention « Prénom NOM ») — **sauf** nom d'équipe, où le
nom entier va dans `nom` et le prénom reste vide, suivant le précédent
RaceResult (#63, ne pas mutiler les noms d'équipe). Est traité comme équipe :

1. tout participant d'une course relais (cf. 4.2) ;
2. tout nom contenant `« / »`, quelle que soit la course.

La seconde garde, par valeur, rattrape le binôme isolé de « Format M
individuel » (1 nom sur 57) sans faire basculer la course entière.

Deux formes de nom d'équipe coexistent et sont toutes deux préservées entières :
`"GUILLON RÉMI / CHARPENTIER EMMANUEL"` (347 participations) et le nom d'équipe
pur `"TEAM TCC"`, `"FOULEE DU 86"`.

### 4.2 `is_relay`, décidé au niveau de la course

`is_relay` vaut, pour **toute** la course : le titre matche
`relais|équipe|duo|team`, **ou** la majorité des noms contiennent `« / »`.

Le titre seul ne suffit pas : les courses du Bike & Run de la pomme et de la
châtaigne (« Course S », « Course XS », « Course 10/13 ans ») sont des binômes
qui ne le disent pas — 100 % de leurs noms portent `« / »`. Et un simple « au
moins un » ne convient pas davantage : il basculerait « Format M individuel »
(1/57) en course de relais. Décider par course, et non par participant, garantit
que `Course.is_relay` et `Participation.is_relay` ne divergent pas selon l'ordre
des participants dans la charge.

### 4.3 Participants `rgpd: "N"`

La source publie leur temps et leur rang, mais ampute le nom (`"T... B..."`) et
vide le club. Ils sont importés sous une identité synthétique
**`« Anonyme <epreuve_id>-<dossard> »`**, prénom vide.

La clé d'épreuve est indispensable : `Athlete` est unique sur
(nom, prénom, date de naissance), donc un simple `« Anonyme 927 »` fusionnerait
les dossards 927 anonymes de deux courses différentes en un athlète unique
agrégeant les résultats de deux personnes. `epreuve_id` et `dossard` étant
stables, l'identité l'est aussi d'un re-scrape à l'autre.

Si ok-time levait l'anonymat plus tard, la réconciliation d'identité (#66)
rattacherait les participations au nom réel au prochain `rescrape-db`.

### 4.4 Réparation du mojibake

Sur `nom` uniquement — seul champ où il a été mesuré. On tente
`s.encode("cp1252").decode("utf-8")` et on ne retient le résultat que si la
conversion **aboutit** et **change** la chaîne ; sinon le nom part inchangé.

Sans réparation, `AnaÃ¯s MOUSQUET` et `Anaïs MOUSQUET` deviennent deux athlètes
distincts et un membre TCN peut échapper au rapprochement. Contrôle de
non-régression mesuré : les 1 061 noms accentués sains du panel traversent la
réparation intacts (aucun faux positif).

### 4.5 Statut et rangs

| Source | `status` |
| --- | --- |
| `pris_depart = "N"` | `DNS` |
| `abandon = "O"` | `DNF` |
| `disqualifie = "O"` | `DSQ` |
| course entièrement non chronométrée (`status="finish"`, aucun temps) | `finisher` |
| sinon | `""` — l'heuristique du projet tranche |

L'avant-dernière ligne vise les trois courses enfants (UNICEF, 52
participations) : courues et déclarées terminées, mais sans chronométrage
individuel. Sans elle, `mapping.derive_status` les classerait DNF en bloc, et le
front afficherait un badge d'abandon sur une course entière d'enfants. La
condition est bornée à la course entière : un participant sans temps dans une
course par ailleurs chronométrée reste traité par l'heuristique, faute de savoir
le distinguer d'un abandon non saisi.

Ordre de priorité : DNS avant DNF (1 participation du panel porte
`abandon="O"` **et** `pris_depart="N"` — ne pas être parti prime).

**Rangs** : `classement_general`, `_categorie`, `_sexe`, avec `0 → None` (1 336
finishers valides non classés). `normalize_rank` rendrait `0`, qui s'afficherait
comme une place.

**Temps total** : `temps_finish`, vide si `"00:00:00"`.

**Genre** : `M` / `F` tels quels ; `X` (relais mixtes, 323 participations) →
chaîne vide, plutôt qu'une valeur que le front ne sait pas rendre.

### 4.6 Splits : différenciation des cumulés

Les points de passage sont cumulés depuis le départ. On les convertit en
**durées de segment** — convention du projet, déjà appliquée par `klikego`
(détection de cumul + deltas) et `timepulse` — et on les range dans
`ScrapedResult.segments`, le chemin générique déplafonné, avec les **libellés de
la source**.

`segments` plutôt que les 5 slots positionnels, pour deux raisons mesurées :
les `id` de points de passage ne sont pas sémantiques (`12|2` vaut « T2 » sur
une épreuve et « VELO » sur une autre), donc aucun mapping fiable vers
swim/t1/bike/t2/run ; et 55 des 99 courses sortent du motif triathlon (2 à 4
points, libellés `CP1`/`CP2`, `RUN1`/`BIKE`/`RUN2`). Les libellés source
préservent l'information là où un remapping la devinerait.

**Garde sur les deltas négatifs** : si un delta sort négatif — les 10
participations de Mimizan à l'ordre incohérent —, la participation conserve ses
**valeurs cumulées brutes** plutôt qu'un temps absurde, et un log agrégé par
épreuve le signale (une ligne par épreuve, pas une par participation).

**Le temps total ne vient jamais du dernier point** : 392 participations ont un
dernier point différent de `temps_finish`, sur des épreuves dont le dernier
point est « Départ CAP2 ». `temps_finish` fait seul foi.

### 4.7 `raw_data`

La charge brute du participant, plus le contexte d'épreuve non porté par les
champs typés : `temp-reel`, `categorie_abbrev`, `heuredebut_course`,
`reference_epreuve`, `status` de course, et les points de passage **cumulés**
d'origine — de sorte qu'une erreur de différenciation reste diagnosticable sans
re-scraper.

## 5. Structure

Un module `backend/app/scrapers/oktime.py`, I/O séparée des fonctions pures
(seuls `_resolve_event_id` et `_fetch_results` touchent le réseau) :

| Fonction | Rôle |
| --- | --- |
| `_parse_url(url)` | → id direct, ou slug à résoudre |
| `_resolve_event_id(client, slug)` | 1 GET HTML → id |
| `_fetch_results(client, event_id)` | l'appel API, erreurs traduites |
| `_repair_mojibake(s)` | réparation cp1252 sûre |
| `_is_relay_course(titre, runners)` | drapeau au niveau course |
| `_athlete_identity(runner, is_relay, epreuve_id)` | → (nom, prénom) |
| `_status(runner, course_non_chronometree)` | → `STATUS_*` ou `""` |
| `_segments(points_de_passage)` | cumulés → durées, garde négative |
| `_build_result(...)` | un runner → `ScrapedResult` |
| `_course_results(...)` | une épreuve → `list[ScrapedResult]` |
| `scrape_event_all(url)` | orchestration |

Enregistrement dans `registry.py` : `OkTimeProvider`, allowlist sur le host
`ok-time.fr` et ses sous-domaines (`hostname`, pas `netloc` — cf. la garde
`RaceResultProvider` contre un host sosie). Aucun conflit d'ordre avec les
providers existants ; la place dans `PROVIDERS` est donc libre.

## 6. Tests

Unitaires **sans réseau**, sur fixtures JSON réduites extraites du panel — une
par comportement, pas une copie de 589 Ko :

- les deux formes d'URL, et le rejet des formes `/course/` et `/competition/` ;
- les deux formes d'erreur API (404 id inconnu, 400 sans résultats) ;
- cumulés → durées de segment ; delta négatif → repli sur les bruts ;
- dernier point ≠ arrivée → `total_time` vient de `temps_finish` ;
- `rgpd="N"` → identité synthétique, distincte entre deux épreuves ;
- mojibake réparé, **et** nom accentué sain laissé intact ;
- relais titré, binôme non titré (Bike & Run), binôme isolé en course
  individuelle, nom d'équipe pur ;
- rang `0` → `None` ; DNS / DNF / DSQ ; DNS prioritaire sur DNF ;
- course d'engagés (`status=""`, aucun temps) écartée ;
- course enfants non chronométrée → `finisher`, pas DNF ;
- entités HTML décodées dans le nom de `Course` ;
- classification sur la concaténation (le cas SwimRun « Format M individuel »).

Un test marqué `integration` sur l'événement réel 48555.

## 7. Hors périmètre

- **Les 3 URLs obsolètes du Sheet** (§2.1) : le Sheet est à corriger, pas le
  scraper.
- **Participants sans dossard** (30 au panel, dont 27 dans une course d'engagés
  écartée) : `Participation` étant unique sur `(course_id, bib_number)`, un
  `bib_number` nul échappe à l'upsert et se redouble au re-scrape. Limite
  connue du projet, déjà rencontrée sur Sportinnovation ; elle n'est pas
  spécifique à ok-time et ne se traite pas ici.
- **`club` absent sur certaines épreuves** (0/781 à Lacanau 2026) : vide à la
  source, comme Carnac 2025 chez Sportinnovation. Rien à corriger côté scraper.
- **Route `/runner/{id}`** : le scraping athlète-unique a été supprimé du
  projet ; seul l'import d'épreuve complète existe.
