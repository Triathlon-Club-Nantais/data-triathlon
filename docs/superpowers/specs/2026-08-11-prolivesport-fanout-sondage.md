# Sondage — fan-out ProLiveSport et filtre `race` de l'API

**Date** : 2026-08-11

**Contexte** : issue #269 (« problème de fanout sur prolivesport »). L'épique #195
a migré 6 scrapers vers le patron fan-out Klikego (#216-#221) ; ProLiveSport n'en
faisait pas partie et reste mono-course. Ce sondage mesure ce que le fan-out
changerait, et **découvre au passage un défaut d'intégrité bien plus grave que
l'absence de fan-out**.

Ce fichier est un **sondage** au sens d'AGENTS.md : il consigne ce qui a été
mesuré sur le terrain à la date ci-dessus, et **prime** sur la spec, le plan et le
design en cas de divergence — toute correction se fait en re-sondant.

## Méthode

1. Téléchargement du CSV public du Sheet (`sheet_source.DEFAULT_SHEET_URL`),
   extraction de la colonne des liens par `sheet_source.parse_sheet_csv`.
2. Groupement des URLs ProLiveSport par `eventId`, en rejouant la logique de
   `prolivesport._parse_url` (forme query et forme front `/result/{id}/{race}`).
3. Pour chaque événement : `GET /apiws/result/raceList/{eventId}/` pour énumérer
   les courses, puis `GET /apiws/result/indiv/{eventId}/{race}/` pour chacune.
4. **Regroupement des lignes retournées par leur champ `race`** — c'est ce
   regroupement qui a révélé le défaut principal.
5. Comptage des membres du club par `app.core.club.is_tcn` sur le libellé `club`.
6. Exécution du scraper actuel (`prolivesport.scrape_event_all`) sur deux URLs
   réelles du Sheet, pour constater ce qu'il produit aujourd'hui.
7. Lecture du bundle Angular `main.efcf24a0ec4c1fbe.js` pour inventorier les
   routes de l'API et chercher une résolution slug → `eventId`.

## Panel

- **Sheet** : 785 lignes avec lien, 464 sans.
- **ProLiveSport** : **36 lignes**, réparties sur **5 groupes d'URL** — 4 `eventId`
  résolus (979, 1060, 1079, 1082) et 3 lignes sans `eventId` du tout.
- **Formes d'URL rencontrées** :

  | Occurrences | Forme | Traitement actuel |
  | --- | --- | --- |
  | 26 | `/index.php?chap=event&sub=liveV3&eventId=…&race=…` | course ciblée |
  | 3 | `/index.php?…&page=…&race=…` | course ciblée (`page` ignoré) |
  | 1 | `/index.php?…&sex=…&race=…` | course ciblée (`sex` ignoré) |
  | 1 | `/V2/result/1060` (nue, sans course) | **1ʳᵉ course du `raceList`** |
  | 2 | `/result/1082/4`, `/result/1082/7` | **index positionnel** dans `raceList` |
  | 3 | `/fftri/grand-prix-duathlon` | `ValueError` → échec permanent |

- **Courses à la source** : 28 sur les 4 événements résolus. **11 ciblées**
  aujourd'hui, **17 jamais importées**.

## Constat n° 1 — le segment `race` de l'API n'est pas un filtre fiable

`GET /apiws/result/indiv/{eventId}/{race}/` **ignore silencieusement** le segment
`race` sur une partie des événements et renvoie **l'événement entier**. La seule
vérité est le champ `race` porté par chaque ligne de la réponse.

Mesures :

| Appel | Lignes rendues | Champ `race` des lignes |
| --- | --- | --- |
| `indiv/979/Triathlon M/` | 815 | `Triathlon M` 336, `Triathlon S` 278, `Triathlon XS` 201 |
| `indiv/1060/CHTRI XS/` | 3120 | les **11** courses de l'événement |
| `indiv/1082/M/` | 1156 | `M` 1156 — filtre honoré |
| `indiv/1082/M_relay/` | 4000 | **10** courses ; `M_relay` n'en est que 149 |
| `indiv/1082/PO-PU/` | 153 | `PO-PU` 153 — filtre honoré |

**Corrélation observée sur les 28 courses du panel** : le filtre est honoré quand
le code de course ne contient ni espace ni tiret bas, et échoue sinon.
`Triathlon M`, `CHTRI XS`, `M_relay`, `S_Light` → événement entier ; `M`, `S`,
`PO-PU`, `BE-MI`, `TREP`, `TRGP`, `Challenge`, `SUPP`, `SUPP2` → filtre honoré.
La corrélation est parfaite sur le panel, mais **l'implémentation ne doit pas s'y
fier** : la règle sûre est de filtrer côté client sur `ligne["race"]`, toujours.

## Constat n° 2 — ce que le scraper produit aujourd'hui (reproduit)

```
$ prolivesport.scrape_event_all(".../index.php?…&eventId=979&race=Triathlon%20M")
 -> 815 ScrapedResult, 1 seule source_url, event_type='triathlon-m'
    dont : Triathlon M 336 | Triathlon S 278 | Triathlon XS 201

$ prolivesport.scrape_event_all("https://www.prolivesport.fr/V2/result/1060")
 -> 3120 ScrapedResult, 1 seule source_url, event_type='triathlon'
    dont les 11 courses, de « CHTRI 6-7 ans » (25) à « CHTRIMAN 113 » (1113)
    splits tous vides
```

Conséquences en base, par ordre de gravité :

1. **Course fourre-tout** — 815 participations dans une `Course` typée
   `triathlon-m` dont 479 ne sont pas des Triathlon M. Les rangs, les temps et le
   type d'épreuve sont faux pour la majorité des participants. Sur l'événement
   1060 : 3120 participations, 11 courses confondues, `event_type` déduit de
   « CHTRI 6-7 ans » parce que l'URL est nue.
2. **Duplication entre lignes du Sheet** — l'événement 979 a 2 lignes
   (`race=Triathlon M` et `race=Triathlon S`). Les deux reçoivent **les mêmes 815
   lignes** et créent 2 `Course` distinctes : chaque participation de l'événement
   est stockée deux fois, sous deux libellés.
3. **URL nue = 1ʳᵉ course** — `_resolve_race("")` prend `races[0]`, soit
   « CHTRI 6-7 ans » sur l'événement 1060. Silencieux, et arbitraire.
4. **Index positionnel** — `/result/1082/4` désigne la 5ᵉ entrée du `raceList`
   (`TREP`), `/7` la 8ᵉ (`M`). Si la source réordonne ou ajoute une course, l'URL
   pointe ailleurs : identité de `Course` et clé de cache TTL instables.
5. **Splits par course** — `_build_split_map` filtre `splitDetail` sur le code de
   course, donc sur l'événement 1060 la carte est construite pour
   « CHTRI 6-7 ans » (aucun split publié) et appliquée aux 3120 lignes : **aucun
   split** alors que `CHTRIMAN 113` et `CHTRIMAN 226` en publient.

## Constat n° 3 — le fan-out seul rapporte peu ; c'est l'intégrité qui est en jeu

Courses manquantes et participations TCN réellement perdues, après regroupement
correct par `ligne["race"]` :

| Événement | Courses source | Ciblées | Manquantes | Participations TCN manquantes |
| --- | --- | --- | --- | --- |
| 979 — Quiberon 2024 | 3 | 2 | 1 (`Triathlon XS`) | 0 |
| 1060 — Chtriman 2025 Gravelines | 11 | 1 | 10 | **1** (`CHTRIMAN 226`) |
| 1079 | 3 | 2 | 1 (`XS`) | **4** |
| 1082 | 11 | 6 | 5 | **2** (`BE-MI`) |
| **Total** | **28** | **11** | **17** | **7** |

Le fan-out apporte donc **7 participations TCN** et 17 courses. À comparer aux
**~4 000 participations mal attribuées** que corrige le regroupement par course.
Les deux ne sont pas séparables : sans regroupement côté client, le fan-out
produit N courses portant chacune l'événement entier — il **multiplierait** le
défaut au lieu de le corriger.

## Constat n° 4 — l'API rend des 500 intermittents sur les gros événements

Les réponses « événement entier » pèsent jusqu'à **14,7 Mo**. Mesuré :

- `indiv/1082/M_relay/` : **3 × HTTP 500 corps vide**, puis succès au 4ᵉ essai.
- `indiv/1082/S_Light/` : **4 × HTTP 500** d'affilée, jamais obtenue sur ce
  passage ; obtenue plus tard en 5 essais.

Le code actuel appelle `r.raise_for_status()` : un 500 fait échouer l'import de
l'épreuve entière. Un fan-out sans reprise ni isolation d'échec par course
échouerait donc régulièrement, sur les événements les plus gros.

## Constat n° 5 — `/fftri/grand-prix-duathlon` n'est pas résoluble par scraping

Les 3 lignes du Sheet sur cette forme échouent aujourd'hui sur
`ValueError("URL prolivesport.fr sans identifiant d'événement.")`, que
`import_service` convertit en **`ProviderNotSupportedError`** (`import_service.py:185`
et `:268`) — message trompeur, ProLiveSport *est* supporté.

Ce qui a été mesuré sur la source :

- La page est une **coquille SPA Angular** de 80 Ko : aucun `eventId`, aucune
  mention de « duathlon » dans le HTML. Le contenu est rendu côté client, et le
  repli navigateur a été supprimé avec sa dépendance (#102).
- Dans le bundle, `fftri/grand-prix-duathlon` est un `href` **codé en dur** : c'est
  une page de **série** (Grand Prix FFTRI), pas une page d'épreuve — même nature
  que le cas Competitor / ironman.com.
- La série a bien une API dédiée (`pls-erp/FFTRI/GP/get-stage/`,
  `ranking-team-general/`, `ranking-team-stage/`), mais elle est derrière un
  **JWT codé en dur dans le bundle, expiré depuis le 2025-04-07**
  (`exp: 1744027608`). Sans en-tête : `HTTP 412 — Header non conforme`.
- Les routes d'apparence plus propre repérées dans le bundle
  (`/events/{id}/races`, `/events/{id}/races/{raceId}/results`) sont construites
  sur `apiws` et répondent `{"success":false,"message":"wrong param"}` : **non
  déployées**. Il n'existe pas d'alternative au couple
  `raceList` + `indiv`.

**Conclusion** : la résolution slug → `eventId` n'est pas atteignable. Le seul
livrable honnête est un **message d'erreur explicite** disant que l'URL désigne une
page de série et non une épreuve, et une correction des 3 lignes **dans le Sheet**.

## Ce que le sondage impose au plan

1. **Grouper par `ligne["race"]`, jamais faire confiance au filtre de l'API.** Une
   course = les lignes dont `race` vaut son code, et rien d'autre.
2. **Quand une réponse couvre plusieurs courses, la réutiliser pour toutes.** Sur
   l'événement 1060, un seul GET rend les 11 courses : refaire 11 GET de 14,7 Mo
   serait absurde. Détecter la couverture et court-circuiter les appels suivants.
3. **URL canonique de sous-unité** — comme les 6 scrapers de #195, elle sert à la
   fois de clé `cache_probe` et de `ScrapedResult.source_url`. `Course` est
   retrouvée par **égalité exacte** de `source_url`
   (`course_repository.get_latest_by_source_url`) : la forme produite doit être
   **identique caractère pour caractère** à celle des 26 lignes du Sheet
   (`?chap=event&sub=liveV3&eventId=979&race=Triathlon%20M`, `%20` et non `+`),
   sinon le re-scrape crée un doublon au lieu de réécrire la `Course` existante.
4. **Reprise sur 500 + isolation d'échec par course** — sans quoi les gros
   événements échoueront en entier (constat n° 4).
5. **Ne plus deviner la course depuis l'URL.** L'URL nue et l'index positionnel
   deviennent sans objet : le fan-out énumère `raceList`. `_resolve_race` peut
   disparaître avec le mode mono-course, hors échappatoire `--single-heat`.
6. **`event_type` par course** — `classify_event_type(race)` sur le code de
   chaque sous-unité, plus sur le jeton de l'URL.
7. **Splits par course** — `_build_split_map(splits, race)` est déjà par course :
   un seul `GET splitDetail/{eventId}/` suffit pour l'événement, à réutiliser pour
   toutes les sous-unités.

## Arbitrages tranchés par le porteur (2026-08-11)

1. **Toutes les courses sont importées, sans filtre** — même arbitrage que le
   fan-out Klikego (#156) : le scraper ne juge pas de la pertinence. Les courses
   jeunes (`CHTRI 6-7 ans`, `PO-PU`, `BE-MI`) et les fourre-tout administratifs
   (`SUPP` 9 partants, `SUPP2` 8, `Challenge` 57) entrent en base.
2. **La forme slug est traitée dans #269**, dans les limites du constat n° 5 :
   message d'erreur explicite, pas de résolution.
3. **Réparation de l'existant par re-scrape seul, sans purge.** Conséquence
   assumée et mesurée : les `Course` nées des URLs nue et positionnelles
   (`/V2/result/1060`, `/result/1082/4`, `/result/1082/7`) portent des
   `source_url` qui ne seront **plus jamais produites** par le fan-out — elles
   resteront en base avec leur contenu fourre-tout jusqu'à suppression manuelle.
   Les 26 lignes en forme `?race=` seront, elles, réécrites en place si la règle 3
   ci-dessus est respectée.

## Défaut adjacent, hors périmètre

`_build_split_map` mappe **plusieurs champs sur le même rôle** puis
`_parse_athlete` retient le premier non vide. Sur l'événement 979 :
`{T1: swim, T2: t1, T3: bike, T6: bike, T7: bike, T4: t2, T5: run, T8: run}` —
`T3`, `T6`, `T7` sont des points de passage vélo, `T5` et `T8` des points de
passage à pied. Le temps stocké en `bike_time` / `run_time` est donc celui du
**premier point de passage rencontré dans l'ordre de l'API**, pas le temps de la
section. Indépendant du fan-out (le défaut existe déjà par course) : ouvert
séparément en **#280**.
