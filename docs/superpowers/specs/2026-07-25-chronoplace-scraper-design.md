# Scraper chronoplace.fr — design

- **Issue** : [#57](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/57) (sous-issue de #33, section B)
- **Date** : 2026-07-25
- **Effort estimé** : M (revu à la baisse après sondage réel — voir « Pagination »)

## Contexte

`chronoplace.fr` est un chronométreur sarthois (dép. 72) présent 2 fois dans le
Sheet des adhérents. Volume faible, mais la source colle bien au modèle : les
splits triathlon y sont **déjà séparés côté serveur**, colonne par colonne.

Les deux liens du Sheet :

| URL | État |
| --- | --- |
| `/classement/spaycific-races-2025/epreuve/494` | 200 — « Spay'cific Triathlon S », 219 participants, dont un TCN (dossard 49) |
| `/classement/spay-swimrun-2025/epreuve/566` | **404** — le slug a changé ; l'épreuve vit sous `/classement/spaycific-races-2025/epreuve/566` |

## Sondage de la source (fetch réel)

Application Laravel + Livewire, HTML server-rendered.

### Pagination : query string, pas Livewire

L'issue posait le choix « rétro-concevoir le protocole Livewire (snapshot +
checksum) **ou** parser le PDF de classement complet ». Le sondage écarte les
deux : le composant synchronise ses paramètres avec l'URL, ce que déclare son
propre `wire:effects` :

```json
{"url":{"search":{"as":"search"},"sortField":{"as":"sortField"},
         "perPage":{"as":"perPage"},"paginators.page":{"as":"page"}}}
```

Un GET suffit donc à tout obtenir :

| Requête | Lignes rendues dans le DOM |
| --- | --- |
| `…/epreuve/494` | 50 (défaut) |
| `…/epreuve/494?page=2` | 50 (rangs 51→100) |
| `…/epreuve/494?perPage=all` | **219 — le classement complet** (1,2 Mo) |

`all` est la valeur officielle du sélecteur « Tout » (`<option value="all">`).
**Décision : une requête `?perPage=all` par épreuve.** Ni POST `/livewire/update`
(snapshot + checksum à re-signer à chaque déploiement du site), ni PDF (parsing
hétérogène, pas de dossard fiable).

### `wire:snapshot` : des métadonnées propres, en JSON

L'attribut `wire:snapshot` du composant `classement-table` contient un JSON déjà
structuré, préférable aux attributs `data-track-*` dispersés dans le markup :

```json
{"data":{"epreuveId":494,"isTeam":false,"perPage":50,
  "affichageDonnees":[{"categorie":false,"genre":true,"club":true,"nb_tours":false,
    "clasmt_genre":false,"ecart":false,"dossard":true,"temps":true,
    "T_natation":true,"T_velo":true,"T_course_a_pied":true,"T1":true,"T2":true},{"s":"arr"}],
  "analyticsContext":[{"event_slug":"spaycific-races-2025","event_year":"2025",
    "event_type":"Triathlon","department":"72","epreuve_id":"494",
    "epreuve_name":"Spay'cific Triathlon S"},{"s":"arr"}]}}
```

On y lit `isTeam`, l'inventaire des colonnes (`affichageDonnees`) et le contexte
(`event_year`, `event_type`, `epreuve_name`). Les tableaux Livewire sont sérialisés
en `[valeur, {"s":"arr"}]` → on prend l'élément 0.

### Colonnes dynamiques, mais nommées

Les colonnes affichées varient d'une épreuve à l'autre ; chaque `<th>` porte sa
clé dans `wire:click="sortBy('<clé>')"` :

| Épreuve sondée | Colonnes (`sortBy`) |
| --- | --- |
| 494 — Spay'cific Triathlon S | `position, dossard, nom, genre, club, T_natation, T1, T_velo, T2, T_course_a_pied, temps` |
| 566 — SwimRun | `position, dossard, nom, categorie, nb_tours, temps, ecart` |
| 722 — 24h VTT (`isTeam:true`) | `position, nom, categorie, nb_tours, temps, ecart` |

Vocabulaire fermé, connu d'avance via `affichageDonnees` : `position, dossard,
nom, genre, club, categorie, clasmt_genre, nb_tours, ecart, temps, T_natation,
T1, T_velo, T2, T_course_a_pied`.

Lignes correspondantes :

```
1  90 MARTIN Malo  M  ENTENTE HAUTE BRETAGNE TRIATHLON  00:10:53 00:00:48 00:31:01 00:00:52 00:04:33 01:01:26
2  81 MENARDAIS FERDINAND / COMPAIN LENA  Relais Mixte  15  02:05:37  +5:16
1     S1 NEO factory  DÉCOUVERTE  61  24:16:30  --
```

### Date de l'épreuve : absente de la page de classement

Ni `<time>`, ni meta, ni JSON-LD. Elle figure en revanche sur l'annuaire des
résultats, filtrable :

```
GET /recherche?module=classement&annee=2025&categorie=12
→ « Spay'cific Races · 21 septembre 2025 · Spay, Base du Houssay à Spay »
  + href="/classement/spaycific-races-2025/epreuve/494"
```

`categorie` est un id numérique (`12` = Triathlon), lisible dans le `<select>` de
`/classements`. Sans filtre de catégorie, la liste est paginée (≈12 événements
par page) — le filtre ramène le résultat à une page.

## Architecture

Un module `app/scrapers/chronoplace.py`, un point d'entrée public
`scrape_event_all(url)`, httpx + BeautifulSoup. Pas de Playwright.

```
scrape_event_all(url)
  ├─ _parse_url(url)                  → (slug, epreuve_id | None)
  ├─ _fetch_epreuve(slug, id)         → GET …?perPage=all
  │     ├─ _parse_snapshot(html)      → dict (isTeam, affichageDonnees, analyticsContext)
  │     ├─ _list_epreuves(html)       → [(id, nom), …] (onglets de l'événement)
  │     ├─ _event_name(html)          → texte du <h1>
  │     └─ _parse_table(html)         → [dict de cellules par clé de colonne]
  ├─ _fetch_event_date(slug, year, type) → date | None (1 GET /recherche)
  └─ pour chaque autre épreuve de l'événement : _fetch_epreuve + _parse_table
```

Une URL sans `/epreuve/<id>` (`/classement/<slug>`) est acceptée : le site rend
alors la première épreuve de l'événement, et la suite du flux est identique
puisque les épreuves sœurs sont de toute façon toutes importées.

### Portée : toutes les épreuves de l'événement

Une URL pointe une épreuve, mais la page liste les épreuves sœurs via des onglets
`<a href="/classement/<slug>/epreuve/<id>">`. `scrape_event_all` les importe
**toutes** — le modèle l'autorise (une `source_url` porte N `Course`, cf. les
heats Breizh Chrono), et un seul lien du Sheet suffit alors à couvrir l'événement
complet (triathlon **et** swimrun pour Spay'cific Races). Coût : une requête par
épreuve.

### Mapping vers `ScrapedResult`

| Colonne source | Champ | Note |
| --- | --- | --- |
| `position` | `rank_overall` | `normalize_rank` |
| `clasmt_genre` | `rank_gender` | rarement affichée |
| `dossard` | `bib_number` | absente sur certaines épreuves (24h VTT) |
| `nom` | `athlete_name` / `athlete_firstname` | `split_athlete_name` (convention « NOM Prénom ») |
| `genre` | `gender` | `M` / `F` |
| `club` | `club` | souvent vide |
| `categorie` | `category` | `Solo Homme`, `Relais Mixte`, `EXPERT`… |
| `temps` | `total_time` | `normalize_time` |
| `T_natation` | `swim_time` | slot positionnel |
| `T1` | `t1_time` | |
| `T_velo` | `bike_time` | |
| `T2` | `t2_time` | |
| `T_course_a_pied` | `run_time` | |
| `nb_tours`, `ecart` | `raw_data` seulement | ni temps ni split |

Les slots restent positionnels : `services/mapping.build_splits` les ré-étiquette
selon `event_type`. `raw_data` conserve toutes les cellules brutes.

**Colonnes lues par clé, jamais par position** : on construit `{index → clé}`
depuis le `thead` (`sortBy('…')`), puis on lit les `<td>` par index. Une colonne
inconnue est ignorée sans décaler les autres. Le markup contient des marqueurs
`<!--[if BLOCK]><![endif]-->` (Livewire) à retirer avant parsing ; `thead` et
`tbody` partagent les mêmes conditions d'affichage, donc l'alignement en-tête ↔
cellule est garanti.

**Valeurs non-temps** : la colonne `ecart` vaut `--` ou `+5:16`, que
`normalize_time` laisse passer tel quel. Elle n'est pas mappée en temps ; toute
valeur ne correspondant pas à `HH:MM:SS`/`MM:SS` est ignorée pour `temps` et les
splits. Les durées > 24 h (`24:16:30`, 24h VTT) sont conservées telles quelles.

### Identité de la course

- `event_name` = texte du `<h1>` : « Spay'cific Races 2025 - Spay'cific Triathlon S ».
  Le nom de l'épreuve **doit** y figurer : `Course` est unique par
  `(name, event_date, event_type, is_relay)`, donc deux épreuves d'un même
  événement classées dans le même type (« Trail 10 km » / « Trail 21 km »)
  fusionneraient sous un nom d'événement seul. Replis : meta `description` privée
  de son préfixe « Résultats », puis slug en Title Case.
- `event_type` = `classify_event_type(epreuve_name)` — déjà correct sur les cas
  réels (`Spay'cific Triathlon S` → `triathlon-s`, `SwimRun` → `swimrun`). Repli
  sur `analyticsContext.event_type`, qui décrit l'**événement** et non l'épreuve
  (l'événement Spay'cific est typé « Triathlon » alors qu'il porte un swimrun).
- `event_date` : `_fetch_event_date` interroge
  `/recherche?module=classement&annee={event_year}&categorie={id}`, retient la
  carte dont le lien contient le slug, et parse la date française via
  `utils.parse_fr_date`. Table statique `{libellé de catégorie → id}` (17 entrées,
  relevée dans le `<select>` de `/classements`). Catégorie inconnue, slug
  introuvable ou requête en erreur → `event_date = None` : la date est un bonus,
  jamais un motif d'échec de l'import.
- `is_relay` : `isTeam` du snapshot, ou catégorie contenant `relais` / `duo` /
  `equipe` (normalisée sans accents). Le nom d'équipe passe par
  `split_athlete_name` comme sur TimePulse.
- `status` : aucun label DNF/DNS/DSQ observé sur les quatre épreuves sondées — le
  scraper **ne se prononce pas** (`status = ""`) et laisse
  `mapping.derive_status` appliquer son heuristique. On ne devine pas un
  vocabulaire qu'on n'a pas vu ; à compléter si une épreuve réelle en expose un.

### Enregistrement dans le registre

`ChronoplaceProvider` (nom `chronoplace`, `matches` = host `chronoplace.fr`),
ajouté à `PROVIDERS` dans `scrapers/registry.py`. Aucune interaction avec les
autres providers : le host est disjoint, la position dans la liste est libre.

## Cas limite assumé : slug obsolète → 404

Le site exige la paire `slug` + `id` exacte : `/classement/<slug faux>/epreuve/494`
et `/classement/epreuve/494` renvoient tous deux 404. Le lien
`spay-swimrun-2025/epreuve/566` du Sheet est donc mort.

Reconstruire le slug à partir du seul id supposerait de balayer l'annuaire année
par année en ouvrant chaque événement — disproportionné pour un provider à 2
occurrences. **Décision : lever un `ValueError` explicite** (« épreuve
introuvable : slug obsolète ou épreuve retirée »). Le contenu n'est pas perdu
pour autant : l'autre lien du Sheet importe les deux épreuves de l'événement.

## Tests

Fixtures HTML réelles, réduites à quelques lignes chacune, dans `tests/fixtures/` :
épreuve 494 (splits triathlon), 566 (swimrun, catégories relais), 722 (`isTeam`,
sans dossard, temps > 24 h).

Unitaires (`tests/test_chronoplace.py`, sans réseau) :

- mapping en-tête → cellule, y compris colonnes absentes ;
- splits triathlon → slots `swim/t1/bike/t2/run` ;
- `event_name` depuis le `<h1>` et ses replis ;
- `event_type` par épreuve, y compris le swimrun d'un événement « Triathlon » ;
- `is_relay` via `isTeam` et via la catégorie ;
- `ecart` (`--`, `+5:16`) non pris pour un temps ; durée > 24 h préservée ;
- parsing du `wire:snapshot` (déballage des tableaux `[…, {"s":"arr"}]`) ;
- liste des épreuves sœurs depuis les onglets ;
- date : extraction depuis une fixture `/recherche`, et repli `None` si le slug
  est absent ;
- 404 → `ValueError` au message explicite ;
- `registry.detect_provider` → `chronoplace`.

Intégration (`-m integration`, réseau réel) : import de
`/classement/spaycific-races-2025/epreuve/494` — les deux épreuves remontent, les
splits sont peuplés, le TCN est présent ; et le lien mort `spay-swimrun-2025`
lève bien.

## Hors périmètre

- Modal de détail par coureur (`wire:click="showDetails(n)"`, tours intermédiaires) :
  nécessiterait le POST Livewire qu'on écarte, pour une donnée que le modèle ne
  stocke pas.
- Recherche par nom (`?search=`) : `scrape_event_all` importe toute l'épreuve, le
  filtrage club se fait en aval.
- Épreuves à venir / live (`/live`) : hors sujet, on importe des classements
  publiés.
