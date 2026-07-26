# Scraper `fftri.t2area.com` (T2Area / FFTRI officiel) — design

Issue : [#51](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/51)
(sous-issue de #33, section B, point 4 de l'ordre d'attaque).
Date : 2026-07-26.

## 1. Ce qu'est la source

`fftri.t2area.com` est la plateforme de résultats officielle de la FFTRI : un
Joomla qui rend **le classement complet en HTML server-rendered**, sans SPA, sans
API à rétro-concevoir, sans Playwright. Une seule requête ramène toutes les
lignes — 901 sur La Baule M 2022 — et il n'y a **aucune pagination**.

Hiérarchie d'URL, la profondeur du chemin dit à quel niveau on est :

```
/calendrier/<événement>.html                          événement (N épreuves)
/calendrier/<événement>/<épreuve>.html                épreuve   (N éditions)
/calendrier/<événement>/<épreuve>/<année>.html        édition   ← le classement
/calendrier/<événement>/<épreuve>/<année>/<clé>.html  fiche individuelle
```

### 1.1 Position vis-à-vis du chronométreur amont

La FFTRI ne chronomètre pas : elle republie. Chaque classement porte une mention
« Résultats produits par X », et **X est souvent un chronométreur qu'on lit mieux
à la source** (dossards partout, splits de tous les participants, statuts francs).
La règle est donc : *quand l'URL source est connue et supportée, elle prime.*

Mais cette délégation **ne peut pas être automatisée** — c'est un fait de la
source, vérifié : la mention ne lie que la **page d'accueil** du chronométreur
(`http://my3.raceresult.com/`, `https://www.prolivesport.fr/`), jamais l'épreuve.
Ni la fiche d'épreuve ni la fiche d'événement ne portent de lien de résultats.
Aucun identifiant d'épreuve n'est récupérable, donc aucune URL source n'est
constructible.

Ce qu'on fait à la place : le href de la mention est passé à
`registry.detect_provider()` — il le reconnaît tel quel — et **un avertissement
est journalisé quand le chronométreur est un provider supporté**. L'opérateur
sait qu'une meilleure source existe ; il reste seul à pouvoir en fournir l'URL.

Le sondage montre que ce cas est minoritaire, et que la valeur du scraper tient
justement aux autres :

| Édition sondée | Lignes | Clé de fiche | Chronométreur | Chez nous |
| --- | ---: | --- | --- | --- |
| La Baule M 2022 | 901 | `bib-*` | IPITOS | §C de #33 — **verrou TLS, inaccessible** |
| La Baule M 2019 | 859 | `bib-*` | IPITOS | idem |
| Ardèche L 2019 | 535 | `bib-*` (532) + licence (3) | ChronoRace | §C de #33 — non implémenté |
| Vichy L 2024 | 502 | `bib-*` | RaceResult | **supporté** → avertissement |
| Gravelines Duathlon L 2025 | 171 | `id-*` | ProLiveSport | **supporté** → avertissement |
| Embrun XL 2025 | 163 | licence + `id-*` | EventiCom | absent de #33 |
| Lac du Bouchet L 2025 | 117 | licence `A*` | AltiChrono | absent de #33 |

Cinq éditions sur sept ne sont importables **que** par ce scraper. AltiChrono et
EventiCom sont deux chronométreurs que #33 ne recense pas encore : à y remonter.

## 2. Décisions

Trois arbitrages structurent le module. Ils ont été tranchés sur données réelles,
pas sur hypothèse.

### 2.1 Splits : membres TCN uniquement

Le classement **ne contient aucun split**. Ils vivent sur la fiche individuelle,
soit **une requête HTTP par participant** — 901 sur La Baule, plusieurs minutes
pour une seule épreuve et des heures sur un `rescrape-db` complet.

Retenu : la fiche n'est chargée que pour les lignes dont la colonne Club passe
`core.club.is_tcn`. Coût réel sur La Baule M 2022 : **25 requêtes** (1 classement
+ 24 membres TCN sur 901 lignes). Le coût réseau est borné par l'effectif du
club, pas par la taille de l'épreuve.

Contrepartie assumée : le scraper devient conscient du club — une première dans
cette couche. Il **réutilise** la définition unique de `core/club.py`, il ne la
réimplémente pas : la règle de #76 est respectée.

### 2.2 URL acceptées : édition, fiche athlète, épreuve

- fiche individuelle → **troncature** vers son édition (le cas réel du Sheet) ;
- édition → traitée directement ;
- épreuve sans année → 1 GET, on prend l'**année maximale** des liens `.edition` ;
- événement → `ValueError` explicite.

L'événement est écarté sciemment : ses épreuves ont des dernières éditions
d'années différentes (La Baule : `triathlon-m` en 2022, `triathlon-jeunes-1` en
2024), un fan-out dont l'année retenue varierait d'une épreuve à l'autre n'a pas
de sens lisible. Un appel = **une** `Course`.

### 2.3 Dossard : `bib-NNN` seulement

La source n'affiche jamais de dossard, mais la clé de la fiche individuelle en
est parfois un — et c'est visible dans le href de la colonne « Détails » :

```
…/2022/bib-566.html      → dossard « 566 »
…/2025/A44719.html       → licence FFTRI  → bib_number vide
…/2025/id-1153352.html   → identifiant interne → bib_number vide
```

`bib_number` ne contient donc **jamais autre chose qu'un vrai dossard** ; la clé
brute part dans `raw_data`. Les éditions sans dossard retombent sur
l'appariement par athlète déjà en place (`import_service._match_without_bib`) :
une ligne par athlète et par épreuve chez FFTRI, le ré-import reste idempotent.
Aucun doublon de dossard relevé sur les 1938 lignes des éditions à clé `bib-*`.

Écarté : remplir `bib_number` avec la licence ou l'identifiant interne. Le front
les afficherait tels quels en « #A44719 » — le champ mentirait sur son contenu.

## 3. Flux

```
URL entrante
 └─ _parse_url            profondeur du chemin → (événement, épreuve, année)
 └─ _resolve_edition      année absente → GET de l'épreuve, année max des éditions
 └─ GET du classement     <table id="resultList">, N lignes, pas de pagination
 └─ _parse_header         nom d'épreuve + date depuis le <h1>
 └─ _parse_rows           une ligne → un ScrapedResult
 └─ _fetch_splits         pour les seules lignes is_tcn : GET de la fiche
 └─ list[ScrapedResult]
```

Garde : une édition inexistante répond **303 vers l'accueil** (donc 200 après
redirection). L'absence de `#resultList` lève une `ValueError` — jamais un
classement vide silencieux.

## 4. Lecture du classement

En-tête stable sur les 7 éditions sondées (2019 → 2026), colonnes lues par
position :

| Colonne | Champ | Note |
| --- | --- | --- |
| Clt | `rank_overall`, `status` | `DNF`, `DQ` → `derive_status_from_label` |
| Clt/F | `rank_gender` | rempli pour les femmes seules (0 contre-exemple sur 1574 lignes) |
| Temps | `total_time` | `00:00:00` → `""` |
| Nom | `athlete_name`, `athlete_firstname` | `split_athlete_name` |
| Club | `club` | libellé fédéral |
| CAT | `category`, `gender` | préfixe `M`/`F` (`MHAN`, `MT1` compris) |
| Clt/CAT | `rank_category` | |
| Détails (href) | `bib_number` | cf. §2.3 |

**`00:00:00` vaut temps absent**, et ce n'est pas cosmétique : un DNF sort avec
`00:00:00` dans la colonne Temps (La Baule 2022, EPP Arnaud). Laissé tel quel, il
ferait basculer l'heuristique de `mapping.derive_status` sur « finisher ». Le
statut est de toute façon posé explicitement depuis la colonne Clt.

**`DQ` manque à `_STATUS_TOKENS`** (`utils.py` connaît `dsq`, `disq`, mais pas
`dq`) : sans l'ajouter, un disqualifié de La Baule serait compté DNF. Une ligne
à ajouter, avec son test.

`event_name`, `event_date` et l'année viennent du `<h1>` :

```
Résultats du Triathlon de La Baule - M - 2022 - édition du 18-09-2022
             └────── event_name ──────┘          └── event_date ──┘
```

Deux regex **indépendantes** : un libellé inattendu ne doit pas faire perdre la
date, qui entre dans l'identité de la `Course`. Le nom est déjà qualifié par
l'épreuve (« - M ») → pas de `qualify_event_name`.

`event_type` via `classify_event_type` sur le slug d'épreuve, vérifié sur les
slugs réels : `swim-run-m` → `swimrun-m`, `triathlon-xs-jeunes` → `triathlon-xs`,
`triathlon-s-open` → `triathlon-s`, `bike-run-s-open-eq` → `bike-run`.

`raw_data` conserve la clé de fiche brute, la ligue, le lien club et le
chronométreur — de quoi diagnostiquer sans re-scraper.

## 5. Splits (fiches TCN)

Les libellés de l'accordéon **changent selon le sport** :

```
Triathlon : Général | Natation | Transition 1 | Vélo | Transition 2 | Course à Pied
Duathlon  : Général | CàP 1    | Transition 1 | Vélo | Transition 2 | CàP 2
```

D'où un mapping **par libellé normalisé**, jamais par position :

| Libellé | Slot |
| --- | --- |
| `natation`, `cap 1` | `swim_time` |
| `transition 1` | `t1_time` |
| `velo` | `bike_time` |
| `transition 2` | `t2_time` |
| `course a pied`, `cap 2` | `run_time` |

C'est exactement ce qu'attend `_SPLIT_KEYS_BY_SPORT` : un duathlon ressort en
`course1` / `bike` / `course2`, un aquathlon (Natation / T1 / CàP) en `swim` /
`t1` / `run`. Un mapping positionnel aurait rangé le 3ᵉ segment de l'aquathlon
dans `bike`.

Filet : **si un libellé n'est pas dans la table, toute la fiche bascule sur
`segments`** — la liste ordonnée étiquetée, déplafonnée, qui prime sur les 5
slots. Rien n'est perdu silencieusement sur un sport au découpage inattendu, et
le cas nominal garde les clés canoniques que le front sait afficher.

Un split à `00:00:00` est traité comme absent : La Baule 2022 ne chronomètre pas
les transitions, et une transition affichée à 0 s serait un faux.

## 6. Intégration

`T2AreaProvider` ajouté à `PROVIDERS` dans `registry.py`, `matches` sur
`hostname == "fftri.t2area.com"` (allowlist explicite, comme RaceResult et
Chronoplace : T2Area sert d'autres fédérations sur d'autres sous-domaines, hors
périmètre). Aucune ambiguïté avec un provider existant → pas de contrainte
d'ordre dans la liste. `provider_names()` l'expose automatiquement à
`--provider` / `--only-provider`.

L'appel à `registry.detect_provider()` du §1.1 se fait par **import local dans la
fonction** : `registry` importe `t2area` au chargement du module, l'inverse au
niveau module créerait un cycle. Même procédé que les helpers Klikego appelés
depuis `registry`.

Erreurs remontées en `ValueError` — la CLI les collecte déjà en
`BatchFailure(url, label, message)` et les liste sous « Épreuves en erreur ».

## 7. Tests

- `tests/fixtures/t2area_*.html` — trois classements réduits à ~10 lignes (un à
  clé `bib-`, un à clé licence, un duathlon) et deux fiches individuelles
  (triathlon, duathlon). Pas de fixture de 130 Ko.
- `tests/test_t2area.py` — troncature d'URL aux 4 profondeurs, lecture des
  colonnes, `DNF` / `DQ`, `Clt/F` féminin seul, `00:00:00` → `""`, dossard
  présent/absent, splits triathlon et duathlon, bascule `segments` sur libellé
  inconnu, absence de `#resultList` → `ValueError`, avertissement quand le
  chronométreur est supporté.
- `tests/test_registry.py` — détection du host.
- `tests/test_scrapers_utils.py` — `DQ` → `DSQ`.
- `tests/test_integration_scrapers.py` — 1 test `integration` sur La Baule M
  2022, assertions souples : plus de 800 lignes, rangs contigus depuis 1, au
  moins un club TCN.

## 8. Limites assumées

1. **Noms tout en majuscules** — 69 lignes sur 163 à Embrun 2025 (`ADAMEC
   MATHIS`). `split_athlete_name` en fait un nom sans prénom : c'est sa limite
   documentée et irréductible sans information supplémentaire. Pas d'heuristique
   locale au scraper, qui divergerait du reste du code. Impact club faible : les
   licenciés français sortent en casse propre (`ACCENT Baptiste`).
2. **Doublon de `Course` inter-provider** — une même épreuve déjà importée depuis
   son chronométreur portera un nom différent ; `UNIQUE(name, event_date,
   event_type)` ne les fusionnera pas. Hors périmètre de #51.
3. **Relais / épreuves `-eq`** — `is_relay` déduit du slug (`-eq`, `relais`,
   `duo`), **non vérifié sur données réelles** : aucune épreuve équipe sondée n'a
   de classement publié.
4. **Splits des non-TCN** — jamais chargés (§2.1). Un membre qui rejoint le club
   après coup n'aura ses splits qu'au prochain `rescrape-db`, une fois son
   libellé de club à jour.
