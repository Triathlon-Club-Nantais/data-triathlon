# Phase 1 — Data model

**Aucune entité nouvelle, aucun champ nouveau, aucune migration Alembic.** Le
provider alimente le modèle normalisé existant via `ScrapedResult`, que
`services/mapping.py` convertit en `Athlete` / `Course` / `Participation`.

Ce document est la table de correspondance qui sert de contrat aux tests.

## Colonnes du site → champs de `ScrapedResult`

| # | En-tête du site | Contenu observé | Champ | Traitement |
| --- | --- | --- | --- | --- |
| 0 | Nom et Prénom | `MACQ Guillaume`, `LE ROUX Pierre`, `?DOSSARD #9998` | `athlete_name`, `athlete_firstname` | `utils.split_athlete_name` (gère « LE ROUX »), **sauf** libellé anonyme → nom intégral, prénom vide |
| 1 | Perf | `01:01:43` | `total_time` | string normalisée |
| 2 | 1ère épreuve | `00:13:37` + `P:4` + `1.12%` + `3.30 km/h` | `swim_time` | seul le temps ; le reste en `raw_data` |
| 3 | Vélo | idem, **vide en aquathlon** | `bike_time` | vide → pas de segment |
| 4 | Place avant CàP | `1` + `↗ 3` | — | `raw_data` seulement (c'est un rang, pas un temps) |
| 5 | CàP | idem colonne 2 | `run_time` | |
| 6 | Classement | `1`/`356` + `=` + `0.28%` | `rank_overall` | le total et le percentile en `raw_data` |
| 7 | Catégorie | `1`/`S3M` | `rank_category`, `category`, `gender` | rang + libellé ; genre = suffixe `M`/`F` |

Champs déduits du `<title>` (identiques pour toutes les lignes d'une épreuve) :

| Champ | Source | Exemple |
| --- | --- | --- |
| `event_name` | titre, parenthèses de distances retirées | `Triathlon de Plouescat S` |
| `event_date` | titre, `JJ/MM/AAAA` | `2026-07-19` |
| `event_type` | `classify.classify_event_type(event_name)` | `triathlon-s` |
| `distance_km` | titre, `25.75KM` | `25.75` |
| `provider` | constante du module | `runnerbreizh` |
| `source_url` | URL canonique | `…?CourseFichierGpsNom=2026-07-1925plouescat` |

Champs volontairement **non renseignés**, avec la conséquence assumée :

| Champ | Valeur | Conséquence |
| --- | --- | --- |
| `bib_number` | `""` | déduplication de repli par athlète (existante) |
| `club` | `""` | `Participation.club = NULL` → hors périmètre `scope=club` |
| `status` | `""` | `mapping.derive_status` applique son heuristique (finisher si temps) |
| `rank_gender` | `None` | le site ne publie pas de classement par sexe sur la page de résultats |
| `t1_time`, `t2_time` | `""` | transitions non publiées |
| `segments` | `None` | chemin positionnel retenu (cf. research D5) |

`is_relay` : vrai si le nom d'épreuve désigne une équipe (« duo », « relais ») ou
si la catégorie a la forme `X+Y` (`M+M`, `M+F`).

## Contenu de `raw_data`

Tout ce que le modèle n'a pas de place pour accueillir, et rien de plus :

```json
{
  "page": 1,
  "coureur_id": "717557",
  "total_classes": 356,
  "evolution_rang": "+4",
  "place_avant_cap": 6,
  "evolution_place_avant_cap": "+5",
  "percentile": "0.56%",
  "segments_detail": [
    {"position": 1, "temps": "00:14:21", "rang": 11, "ecart": "3.09%", "vitesse": "3.14 km/h"},
    {"position": 2, "temps": "00:30:58", "rang": 8,  "ecart": "2.25%", "vitesse": "38.75 km/h"},
    {"position": 3, "temps": "00:17:57", "rang": 5,  "ecart": "1.40%", "vitesse": "16.71 km/h"}
  ],
  "chronometreur": "BREIZHCHRONO"
}
```

`position` et non un libellé : les segments sont positionnels, leur sens dépend de
la discipline (cf. research D5). `chronometreur` n'est présent que si la page
porte la mention.

## Effets sur les entités persistées

- **`Course`** — une URL canonique = **une** `Course`. Identité
  `(name, event_date, event_type, is_relay)` inchangée. `source_url` = URL
  canonique, donc clé de cache TTL unique pour les deux formes du Sheet.
- **`Participation`** — une ligne du classement. `bib_number` `NULL`, `club`
  `NULL`, `splits` en JSON ré-étiqueté par discipline.
- **`Athlete`** — dédoublonné par `(nom, prénom, birth_date=NULL)`. Aucun club
  écrit, donc aucun club écrasé.
