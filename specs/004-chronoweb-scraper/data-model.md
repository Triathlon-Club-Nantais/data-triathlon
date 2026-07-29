# Phase 1 — Modèle de données

**Aucun changement de schéma.** Ni modèle SQLAlchemy, ni migration Alembic : le
fournisseur produit des `ScrapedResult`, que la chaîne existante
(`mapping` → `repositories`) convertit en `Athlete` / `Course` / `Participation`.
Ce document décrit les structures **internes** au scraper et la correspondance
vers le contrat de sortie.

## Structures internes (module `chronoweb`)

```
EventMeta        name: str              « Triathlon d'Oléron 2024 » (h2.name)
                 event_date: date|None  06/10/2024 (h2.date)
                 city: str              catalogue, "" si indisponible

RaceMeta         race_id: str           1147 (option value / data-race)
                 label: str             « Triathlon M »
                 event_type: str        triathlon-m (classify, contexte = EventMeta.name)
                 is_relay: bool         libellé contenant relais/duo/team

Passage          point_id: int          data-point (ordre = ordre de passage)
                 point_name: str        Natation | Vélo | Course
                 cumulative: str        « 01:31:34 » temps depuis le départ
                 segment: str           « 01:00:09 » durée du segment
                 rank_overall: int|None display_rank_global
                 rank_category: int|None display_rank_cat
                 speed: str             « 39.9 km/h » (raw_data)
                 rank_gain: str         « -1 » (raw_data)

Runner           bib: str, name: str, category: str
                 passages: list[Passage]   trié par point_id croissant
```

### Invariants (mesurés, cf. sondage)

- `(race_id, bib, point_id)` est unique — 0 collision sur 31 642 lignes.
- `cumulative` croît avec `point_id` — 8 930 participants, 0 contre-exemple.
- au premier passage, `segment == cumulative` — 8 884 / 8 884.
- un `Runner` a au moins un `Passage` ; il peut lui manquer un point
  intermédiaire tout en ayant le point final.

## Correspondance `Runner` → `ScrapedResult`

| Champ de sortie | Source | Règle |
| --- | --- | --- |
| `source_url` | URL canonique de l'événement | R5 |
| `provider` | — | `"chronoweb"` |
| `athlete_name` / `athlete_firstname` | colonne Nom | découpage standard ; sur épreuve relais, libellé entier en nom, prénom vide |
| `bib_number` | `div.lineinfo_bib` | tel quel |
| `category` | `data-cat` | tel quel |
| `gender` | `category` | R7 |
| `club` | — | toujours `""` : la source ne le publie pas |
| `event_name` | `EventMeta.name` + `RaceMeta.label` | `qualify_event_name` |
| `event_date` | `EventMeta.event_date` | identique pour toutes les épreuves |
| `event_type` | `RaceMeta.label`, contexte `EventMeta.name` | `classify_event_type` |
| `is_relay` | `RaceMeta.is_relay` | R6 |
| `rank_overall` / `rank_category` | dernier `Passage` | jamais un rang intermédiaire |
| `total_time` | `cumulative` du dernier `Passage` | `normalize_time` |
| `swim/t1/bike/t2/run_time` | motif reconnu | R2 + transitions R3 |
| `segments` | motif non reconnu | `[(point_name, segment), …]`, transitions incluses sous « Changement » |
| `distance_km` | — | `None` : le site ne publie aucune distance exploitable |
| `status` | — | `""` : l'heuristique aval classe DNF l'absence de temps total |
| `raw_data` | voir ci-dessous | |

### `raw_data`

```
event_id, race_id, race_label     identifiants et libellé côté source
city                              commune du catalogue (R4), absente si indisponible
points[]                          {point_id, name, cumulative, segment,
                                   rank_overall, rank_category, speed, rank_gain}
```

Les rangs intermédiaires, vitesses moyennes et gains de place n'ont pas de
colonne dans le modèle : ils voyagent ici plutôt que d'être jetés.

## Ce qui reste vide, et pourquoi

| Champ | Raison |
| --- | --- |
| `club` | absent de toute la source (0 occurrence sur le panel) |
| date de naissance | absente ; seule la catégorie situe l'âge |
| `rank_gender` | le site ne publie que le rang général et le rang de catégorie |
| `distance_km` | aucune distance publiée dans le classement ; l'extraction depuis le nom d'épreuve reste faite en aval par `mapping` |
| `status` | aucun libellé DNF/DNS/DSQ dans la source ; DNS et DSQ sont indistinguables |
