# Design — scraper Competitor / WTC (ironman.com)

- **Issue** : [#54](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/54) (sous-issue de #33, section B)
- **Date** : 2026-07-26
- **Effort estimé** : M (conforme à l'issue — deux sauts et un schéma propriétaire)
- **Sondage de référence** : `2026-07-26-competitor-ironman-sondage.md`, qui
  **prime** sur ce document.

## Contexte

7 occurrences dans le Sheet des adhérents. `ironman.com` n'est qu'une vitrine :
les résultats viennent d'une iframe `labs-v2.competitor.com`, moteur commun à
toutes les épreuves IRONMAN et IRONMAN 70.3. Le provider est donc nommé
**`competitor`**, comme le demande l'issue — c'est le moteur réel, et le nommer
`ironman` figerait la marque plutôt que la technique.

## Architecture

Module `backend/app/scrapers/competitor.py`, fonctions (pas de classe), une
seule fonction publique.

```
scrape_event_all(url)
  ├─ _uuid_depuis_url(url)          → uuid si l'URL est déjà sur competitor.com
  ├─ _resoudre_uuid(client, url)    → sinon GET ironman.com + regex d'iframe
  ├─ _fetch_next_data(client, uuid) → GET labs-v2 → __NEXT_DATA__ → pageProps
  ├─ _choisir_edition(props, uuid)  → l'édition (année) à importer
  ├─ _lignes(client, edition_id)    → proxy OData, pagination suivie, dédoublonnée
  └─ _build_result(ligne, …)        → un ScrapedResult par ligne
```

Un seul `httpx.Client(follow_redirects=True, timeout=30, headers=HEADERS)` en
context manager pour tout l'import, comme chronoplace et raceresult.

### Portée : quelle édition importer

Une URL désigne une **série** (21 éditions pour IRONMAN France), et le site
n'expose **aucune URL par année** (§3 du sondage). Décision :

| URL collée | Édition importée |
| --- | --- |
| page `ironman.com/races/<slug>/results` | la plus récente publiée |
| `…/results/event/{uuid de série}` | la plus récente publiée |
| `…/results/event/{uuid d'édition}` | **cette édition-là** |

Le troisième cas donne une adressabilité par année que le site n'offre pas, pour
zéro requête supplémentaire : `subevents` est de toute façon lu. C'est aussi ce
qui rend le rattrapage d'une édition ancienne possible depuis la CLI.

Importer les 21 éditions d'un coup a été écarté : ici une édition est une
**année**, pas une épreuve sœur — ce serait ~30 000 participations et 21
requêtes pour une seule URL collée. Le parallèle avec Chronoplace (« toutes les
épreuves de l'événement ») ne tient pas.

### Portée : l'Open Division est incluse

Le rendu serveur ampute `latestResults` des athlètes ODIV (§6 : 62 perdus sur
1810 à IRONMAN France 2025). On **ne réutilise donc jamais `latestResults`** :
le classement est systématiquement redemandé au proxy sans filtre de catégorie.

Le coût est d'une requête par édition ; le gain est double — les participants
ODIV sont des finishers réels avec temps et splits, et toutes les éditions
deviennent comparables entre elles (les anciennes, elles, ne pouvaient être
obtenues que par requête libre).

### Mapping vers `ScrapedResult`

| Champ | Source | Note |
| --- | --- | --- |
| `athlete_name` / `athlete_firstname` | `wtc_ContactId.lastname` / `.firstname` | déjà découpé ; repli `split_athlete_name(fullname)` |
| `club` | — | **absent de la source** (§10) |
| `category` | `_wtc_agegroupid_value_formatted` | `M30-34`, `ODIV` |
| `gender` | `wtc_AgeGroupId.wtc_gender_formatted` | **pas** `ContactId.gendercode`, faux 77 fois sur 1585 (§8) |
| `bib_number` | `wtc_bibnumber`, repli `wtc_bibnumber_v2` | |
| `event_name` | `subevent.wtc_name` | « 2025 IRONMAN France Nice » — porte l'année |
| `event_date` | `subevent.wtc_eventdate` (ISO) | repli `wtc_eventdate_formatted` (`m/d/Y`) |
| `event_type` | `classify_event_type(event_name)` | |
| `total_time` | `wtc_finishtimeformatted` | via `normalize_time` |
| splits | les 5 slots positionnels | cf. ci-dessous |
| `rank_overall` / `_category` / `_gender` | `wtc_finishrankoverall` / `…group` / `…gender` | `99999` → `None` |
| `status` | `wtc_dq` > `wtc_dns` > `wtc_dnf` > `wtc_finisher` | `""` si aucun drapeau |
| `is_relay` | `bool(_wtc_teamresult_value)` | **non mesuré** (§12.1) |
| `distance_km` | — | les distances de la source sont *parcourues*, pas nominales (§11) |
| `raw_data` | la ligne entière | |

**Splits** : les 5 slots positionnels suffisent (triathlon canonique), pas de
`segments`. Table `_SPLIT_FIELDS`, avec l'asymétrie de la source assumée en
commentaire — T1 est `wtc_transition1timeformatted`, T2 est
`wtc_transitiontime2formatted`.

Deux sentinelles neutralisées à la lecture : rang `99999` → `None`, temps
`"0:00:00"` → `""`.

**Non-finisher** : un DNF/DNS/DSQ garde ses splits partiels (ils sont réels)
mais perd `total_time` et ses trois rangs — même « nettoyage de la maison » que
raceresult, et c'est ce qu'exige le garde-fou cross-provider
`test_scrape_event_all_status_jamais_incoherent`. Les lignes **sans aucun
drapeau** (§9) gardent `status = ""` : le scraper ne se prononce pas et laisse
`mapping.derive_status` trancher sur la présence d'un temps.

### Erreurs

`ValueError` nue, traduite en 422 par `import_service`, dans quatre cas :

- page sans iframe Competitor (URL de course nue, ou page hors « Results ») ;
- page sans `__NEXT_DATA__`, ou bloc illisible ;
- `subevents` vide — c'est le seul détecteur d'épreuve introuvable, la source
  répondant 200 sur un uuid inconnu (§3) ;
- classement vide.

Une erreur HTTP en cours de pagination **remonte** : dégrader en silence
figerait un import tronqué dans le cache 30 jours.

### Enregistrement dans le registre

`CompetitorProvider`, `_HOSTS = ("ironman.com", "competitor.com")`, match sur
`urlparse(url).hostname` avec test égalité-ou-vrai-sous-domaine (patron
RaceResult). `competitor.com` couvre `labs-v2.competitor.com` et les façades
suivantes. Ajouté en fin de `PROVIDERS` : aucune ambiguïté avec les autres.

## Correctif collatéral : `classify.py`

`_detect_size` testait `"ironman"` (→ XL) **avant** `"70.3"` / `"half"` (→ L),
donc « 2025 IRONMAN 70.3 Vichy » sortait `triathlon-xl` — un half classé en
format long. Le marqueur de format explicite prime désormais sur le jeton de
marque. « Ironman France », sans marqueur, reste `triathlon-xl`.

Le module est partagé par tous les providers, d'où des cas de non-régression
ajoutés à `test_classify.py` (dont `Ironman France 2025` → `triathlon-xl`, déjà
asserté par `test_wiclax.py`).

## Limite fonctionnelle assumée

**La source ne publie aucun club** (§10). Une participation importée depuis
Competitor porte `club = ""` et ne sera donc **jamais marquée TCN** par
`app/core/club.is_tcn`. L'import reste utile — l'épreuve et ses participants
entrent en base, et un athlète déjà connu par ailleurs est rattaché par son
identité — mais le dashboard `scope=club` ne verra pas ces résultats.

Ouvrir l'iframe `/clubpoints/event/{uuid}`, qui porte des points club, est la
piste à instruire si ce rattachement devient nécessaire. Hors périmètre de #54.

## Tests

Fixtures (extraits réels du 2026-07-26) dans `backend/tests/fixtures/` :

- `competitor_ironman_results.html` — les 3 iframes de la page ironman.com ;
- `competitor_serie_im_france.html` — page Next.js, 3 éditions, `latestResults`
  **sans ODIV** (c'est le point du test) ;
- `competitor_results_2025.json` — classement libre : finisher, DNF, DNS, ODIV ;
- `competitor_results_2025_page1.json` / `_page2.json` — pagination `@odata.nextLink` ;
- `competitor_results_2024.json` — édition ancienne, sans les champs de confort.

40 tests unitaires dans `backend/tests/test_competitor.py` (client httpx factice,
patron `test_chronoplace.py`), couvrant : résolution d'uuid et rejet des iframes
odiv/clubpoints, uuid inconnu en 200, choix d'édition (série vs année), dates,
mapping complet, genre lu sur la catégorie, sentinelles, non-finisher, absence
de club, ODIV importée sans rang, `latestResults` ignoré, pagination et sa borne,
dédoublonnage, et le triptyque de registre (nominal / sosies / `provider_names`).

Réseau réel : `competitor` ajouté à `LIVE_URLS` de `test_integration_scrapers.py`.

## Hors périmètre

- `scrape()` athlète-unique, listé dans l'issue : c'est un reliquat de rédaction,
  cette voie a été supprimée du projet (`ScraperProtocol` n'expose que
  `matches()` + `scrape_event_all()`).
- L'iframe `/clubpoints/`.
- Les épreuves non-triathlon de la marque (`pageProps.sport == "Running"`).
