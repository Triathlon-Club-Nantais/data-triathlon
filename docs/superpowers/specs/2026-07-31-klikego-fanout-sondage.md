# Sondage — impact du fan-out Klikego sur le Sheet du club

**Date** : 2026-07-31

**Contexte** : issue #156, spec `specs/005-klikego-fanout/spec.md`, arbitrage A1 (URL Klikego = événement entier, `?heat=` ignoré). Cette page mesure ce que le fan-out produirait sur le Sheet actuel, avant `/speckit-plan`, pour décider si une curation post-merge est nécessaire.

Ce fichier est un **sondage** au sens d'AGENTS.md § « La troisième catégorie : le sondage » : il consigne ce qui a été mesuré sur le terrain à la date ci-dessus, et **prime** sur la spec, le plan et le design en cas de divergence — toute correction se fait en re-sondant.

## Méthode

1. Téléchargement du CSV public du Sheet (`sheet_source.DEFAULT_SHEET_URL`), extraction des URLs Klikego et Breizh Chrono par la même colonne que `import-sheet`.
2. Pour Klikego, groupement des lignes par `event_id` (dernier segment de path) — la clé sur laquelle porte le fan-out.
3. Pour chaque événement Klikego unique, `GET /resultats/{event_id}` et énumération de **tous** les heats publiés depuis le `<el-select name="heat">` (les `<el-option value="X">`).

   > ⚠️ Un premier passage utilisait `re.findall(r'heat=([^&<>\s"\']+)', html)` — le même regex que `klikego._detect_heat` d'aujourd'hui. Sur `www.klikego.com`, cette regex ne capture que le heat courant (celui affiché dans la page) et jamais les autres options du `<el-select>`. Ce détail est structurant : **l'énumération du fan-out doit se faire depuis `<el-option>`**, pas depuis les `?heat=` de href — c'est le premier constat concret pour `/speckit-plan`.

4. Comparaison par événement : quels heats étaient importés avant (heats spécifiés par les lignes `?heat=X` + heat auto-détecté pour une ligne nue) vs. quels heats seraient importés après fan-out (tous les heats à la source).

5. Breizh Chrono **écarté du sondage** : le code du scraper (`breizhchrono.py:205-248` pour `resultats.breizhchrono.com`, `breizhchrono.py:369-425` pour `live.breizhchrono.com`) montre que le fan-out y est **déjà en place** — sans `?heat=`, `_fetch_all_heats` énumère et boucle. Aucun impact attendu sur les 153 lignes Breizh Chrono du Sheet.

## Panel

- **Sheet** : 785 lignes de résultats, 464 sans lien, 321 avec un lien.
- **Klikego / Breizh Chrono** : 277 lignes (124 + 153) — les seuls providers concernés par la mécanique de heats à fan-outter.
- **Klikego** : 124 lignes, 45 événements distincts.
- **Breizh Chrono** : 153 lignes, ventilé sur les 3 façades (`www` : 93, `live` : 49, `resultats` : 11). **Hors périmètre du sondage** (fan-out déjà en place).

Détail des données brutes : `/home/mherrmann/.claude/jobs/38e6ce82/tmp/sheet_links.json` (extraction Sheet) et `.../heats.json` (énumération heats).

## Résultats — Klikego

| Segment | Événements | Heats à la source (total) | Heats importés aujourd'hui | Heats nouveaux après fan-out |
|---|---|---|---|---|
| Événements multi-heats (2+) | 39 | 240 | 42 | **+198** |
| Événement mono-heat (1) | 1 | 1 | 1 | 0 |
| Pages sans `<el-select>` (inscription / challenge) | 5 | — | — | — |
| **Total Klikego** | **45** | **~241** | **~43** | **+198** |

Les 5 événements sans `<el-select>` sont :

- 3 URLs d'inscription (`/inscription/…`), pas des pages de résultats. Elles échouent aujourd'hui à l'import et continueront d'échouer après fan-out (comportement inchangé).
- 1 page `/specific/t24/resultats-challenge.jsp` (T24, un moteur différent — Klikego re-marque).
- 1 URL de résultats sans classement à la date du sondage (`duathlon-juvigne-2026/1764126877210-1`, événement à venir ou classement pas encore publié).

### Ventilation par taille d'événement

| Nb heats à la source | Événements | Exemples |
|---|---|---|
| 1 | 1 | `runbike-des-vignes-2025` |
| 2 | 7 | `swimrun-des-20-plages-…`, `tri-at-bain-2026` |
| 3 | 6 | `laquarantec`, `duathlon-du-donjon` |
| 4 | 6 | `triathlon-inizys`, `triathlon-du-pays-de-quimperle` |
| 5 | 2 | `biathlon-de-damgan` |
| 6 | 3 | `saint-gilles-croix-de-vie`, `red-ouf-swimrun-baie-de-quiberon` |
| 7 | 2 | `35eme-triathlon-de-laval`, `triathlon-de-coetquidan` |
| 8 | 7 | `chatelaillon-plage`, `sillon-x-race`, `mesquer-quimiac`, `chateau-gontier`, … |
| 11 | 1 | `val-andre-8eme` |
| 13 | 1 | `coteaux-du-vendomois-2026` |
| 14 | 2 | `coteaux-du-vendomois-2025`, `ha-frenchman-carcans-2025` |
| 16 | 1 | `diaoulman-pontivy-2026` |
| 18 | 1 | `medoc-atlantique-frenchman-carcans-2026` |

## Nature des heats nouveaux — catégories qui vont apparaître

Une lecture qualitative des 198 heats nouveaux révèle **trois familles** systématiques :

### 1. Heats jeunes / kids / aquathlons juniors (majorité du volume)

Beaucoup d'événements grand format publient des courses jeunes séparées : « frenchkid-aquathlon-2015-fille », « triathlon-poussin », « triathlon-pupilles », « duathlon-kids-2013-2014 ». Sur les gros événements comme Ha' Frenchman Carcans, ces heats représentent 9 des 14 heats totaux ; Diaoulman Pontivy en publie 10 sur 16.

**Question ouverte au porteur** : ces heats sont-ils **pertinents pour le club** ? Le TCN a-t-il des licenciés jeunes qui y participent ? Si non, ce sont ~90 courses supplémentaires qui vont apparaître en base sans jamais avoir de participant TCN et polluer le catalogue.

### 2. Relais / duo systématiques

Presque tout triathlon individuel a son pendant relais : `triathlon-m-relais`, `triathlon-s-relais`, `duathlon-s-en-relais`. Aujourd'hui, un import sur `?heat=triathlon-m` ne prenait que l'individuel ; après fan-out, le relais suit. **A priori pertinent** — le club a probablement des équipes en relais.

### 3. Formats supplémentaires du même sport

Sur Mesquer, l'import du seul `swim-run-m-duo` cache un `swim-run-s-duo`, un `swim-run-s-indiv` et 3 heats triathlon (S indiv, XS indiv, XS relais). Sur Val-André 8e, l'import du `aquakids-2` cache 10 autres heats dont le triathlon-m adulte. **Ce cas est exactement l'intention de la feature** : le fan-out corrige un défaut de couverture.

## Cas de bord détectés

- **`ha-frenchman-triathlon-carcans-2025/1354050643080-22`** : 14 heats, dont 9 heats `frenchkid-aquathlon`. Après fan-out, ~9 courses jeunes vont apparaître.
- **`medoc-atlantique-frenchman-triathlon-carcans-2026/1354050643080-23`** : 18 heats, dont 12 heats jeunes / meta (`start-challenge-xs-m-l`, `super-challenge-xs-m-l-xxl` — probablement des classements agrégés, à valider au scrape).
- **`diaoulman-pontivy-2026/1480410135917-17`** : 16 heats, dont 7 heats « demi-finale-triathlon-cadets-…-centre-ouest » (compétitions régionales officielles) et 3 heats « duathlon-kids ».
- **`triathlon-des-coteaux-du-vendomois-2026/1695506183783-4`** : 13 heats. Le Sheet spécifie `?heat=triathlon-m-individuel` (donc historiquement 1 seul heat) — après fan-out : 13 heats dont 3 jeunes et un `vendoman` (challenge inter-épreuves, format long).
- **`triathlon-et-swimrun-mesquer-quimiac-2026`** (celui de l'issue #153/#154) : 8 heats à la source. Aujourd'hui seul `swim-run-m-duo` est importé par le premier import fan-out — après la feature #156, les 8 seront importés.
- **Doublons multi-années du même événement** : Mesquer apparaît 3 fois (2024/2025/2026) avec 8, 8 et 8 heats respectivement — ces 24 courses sont trois événements distincts (`event_id` distincts), pas trois passes du même. Aucun impact d'unicité.

## Verdict

Le fan-out ne peut **pas** être livré comme un simple correctif : sur le Sheet actuel, il ferait passer la base de **~43 courses Klikego à ~241** (facteur ×5,6), avec une majorité de heats **jeunes** dont l'utilité pour le club est incertaine.

Décision à prendre par le porteur avant `/speckit-plan` :

1. **Livrer tel quel** et accepter le déluge de courses jeunes / hors périmètre. Nettoyer manuellement après coup. Simple à implémenter, mais pollue le catalogue et alourdit tous les affichages qui listent les épreuves.
2. **Filtrer à l'import** par un critère (âge minimum, motif de heat, présence d'un membre TCN) — nouveau paramètre de la spec.
3. **Livrer et documenter un mode « heat unique »** (l'échappatoire A3) pour maintenir le comportement historique quand on veut cibler une course précise, et **ne pas déclencher le fan-out automatique sur la ligne du Sheet** — chaque nouvelle ligne serait alors ajoutée manuellement pour son heat, comme aujourd'hui. Ça remet en cause A1.

## Recommandations pour `/speckit-plan`

Trois points concrets que ce sondage établit et qui doivent transiter jusqu'au plan :

1. **L'énumération des heats se fait via `<el-option value="X">` dans `<el-select name="heat">`**, pas via `?heat=…` dans les href. Le regex de `klikego._detect_heat` d'origine était incomplet (il ne trouve que le heat courant) — c'est structurant pour l'implémentation.
2. **Breizh Chrono est hors scope de la V1 fan-out** : `_fetch_all_heats` (statique) et `_parse_live_heats` (live) sont déjà en place et bouclent sur tous les heats sans `?heat=`. Le fan-out du provider ne concerne que **Klikego**.
3. **Le volume de heats jeunes / hors-périmètre est le vrai enjeu**, pas la mécanique technique du fan-out. Trancher ce point avant `/speckit-plan` évite de coder deux fois.
