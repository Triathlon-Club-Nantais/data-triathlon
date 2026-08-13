# Data Model: Page de résultats détaillée d'une participation

Aucune migration Alembic — cette feature ne persiste rien de nouveau. Tout ce
qui suit est calculé à la demande à partir des tables existantes
(`athletes`, `courses`, `participations`) et exposé en DTO Pydantic /
TypeScript, jamais stocké.

## Entités existantes réutilisées (rappel, non modifiées)

- **`Course`** (`backend/app/models/course.py`) — apporte `provider` (déjà
  existant), consulté pour l'éligibilité. Aucun champ ajouté.
- **`Participation`** (`backend/app/models/participation.py`) — apporte
  `splits`, `total_time`, `rank_overall`, `is_relay`, `athlete`, `course`.
  Aucun champ ajouté.

## Règle métier nouvelle (code, pas donnée)

- **Éligibilité aux splits complets** — `app/core/splits_reliability.py`
  (nouveau module, même esprit que `app/core/club.py`) :
  - `UNRELIABLE_SPLIT_PROVIDERS: frozenset[str]` = `{"t2area", "breizhchrono"}`
    (cf. research.md §1).
  - `has_reliable_splits(provider: str | None) -> bool` — faux si `provider`
    est `None`, `"manuel"`, ou dans `UNRELIABLE_SPLIT_PROVIDERS` ; vrai sinon.
  - `is_stats_eligible(course: Course) -> bool` — `has_reliable_splits(course.provider)`.
    Point d'entrée unique consommé par le service de calcul ; aucune autre
    couche ne réimplémente ce prédicat (miroir de la règle déjà en place pour
    `is_tcn`, Principe II).

## Value objects calculés (non persistés)

Portés par un nouveau module `app/services/participation_stats_service.py`,
sérialisés par `app/schemas/participation_stats.py`. Aucun n'est une table :
tous sont recalculés à chaque lecture à partir du classement complet de la
course (`participation_repository.list_for_course`).

### `RankingEvolutionStep`

Une étape du graphique d'évolution du classement (US2 / FR-009, FR-010).

| Champ | Type | Description |
|---|---|---|
| `segment` | `str` | Clé du segment (`swim`, `t1`, `bike`, `t2`, `run`, ou l'équivalent du schéma du sport). |
| `scratch_position` | `int` | Rang scratch cumulé de l'athlète à la sortie de ce segment. |
| `segment_position` | `int` | Rang de l'athlète sur ce segment pris isolément. |

Une liste de `RankingEvolutionStep`, une par segment publié par l'épreuve
(FR-013 — pas de segment forcé si l'épreuve ne le publie pas).

### `ComparisonRow`

Une ligne du tableau de comparaison avec d'autres positions (US1 / FR-008).

| Champ | Type | Description |
|---|---|---|
| `position_label` | `str` | Libellé de la position de référence (`"1er"`, `"10e"`, `"25e"`, `"50e"`, `"100e"`). |
| `rank` | `int` | Rang scratch numérique correspondant (1, 10, 25, 50, 100). |
| `percentages` | `dict[str, float]` | Par clé de segment + `"total"` : temps de l'athlète consulté en pourcentage du temps du coureur à cette position, sur ce segment. |

Liste filtrée aux positions qui existent réellement dans le classement de la
course (FR-014 — ligne omise si l'effectif est insuffisant, jamais rendue
vide).

### `ImprovementRow`

Une ligne du tableau de simulation de gains par amélioration (US3 / FR-011).

| Champ | Type | Description |
|---|---|---|
| `segment` | `str` | Clé du segment concerné par la simulation. |
| `gains` | `dict[str, int]` | Par pourcentage d'amélioration (`"0.5"`, `"1"`, `"2"`, `"5"`, `"10"`, `"25"`) : nombre de places scratch gagnées si ce segment avait été amélioré de ce pourcentage, toutes choses égales par ailleurs. |

### `ParticipationStatsOut`

Enveloppe des trois agrégats ci-dessus, `null` quand la course n'est pas
éligible (FR-005) ou que la participation est un relais (FR-012) — c'est ce
`null` qui pilote côté front le rendu de l'état "statistiques indisponibles"
plutôt qu'un champ booléen séparé.

| Champ | Type |
|---|---|
| `segments` | `list[str]` |
| `ranking_evolution` | `list[RankingEvolutionStep]` |
| `comparison` | `list[ComparisonRow]` |
| `improvement` | `list[ImprovementRow]` |

`segments` porte les segments effectivement publiés par l'épreuve (FR-013),
dans leur ordre d'affichage. Il est porté par l'enveloppe plutôt que déduit des
trois blocs : ceux-ci omettent les valeurs manquantes (FR-007, FR-014), et une
colonne s'y déduirait alors de son absence — un split non publié par un athlète
et un segment non publié par l'épreuve deviendraient indiscernables.

## Extension de contrat existant

`ParticipationOut` (`backend/app/schemas/participation.py`) gagne un champ
optionnel :

```
stats: ParticipationStatsOut | None = None
```

Additif et rétrocompatible (Principe IV) — tout consommateur actuel de
`GET /participations/{id}` ou de `GET /courses/{id}` ignore simplement ce
champ s'il ne le lit pas ; sa présence ne change aucun champ existant.

`AthleteParticipationOut` héritant de `ParticipationOut`, et
`CourseParticipationPage.participations` étant une `list[ParticipationOut]`, le
champ apparaît aussi (à `null`, sans calcul) sur `GET /courses/{id}`,
`GET /athletes/{id}` et `GET /participations`.

## Diagramme (vue calcul, pas schéma SQL)

```
Course (provider) ──▶ is_stats_eligible() ──▶ bool
                                                 │
Participation (splits, total_time, is_relay) ───┼──▶ participation_stats_service.build(...)
        + classement complet (list_for_course)  │            │
                                                 │            ▼
                                          (si non éligible    ParticipationStatsOut
                                           ou is_relay)        ├─ ranking_evolution[]
                                                 │             ├─ comparison[]
                                                 ▼             └─ improvement[]
                                                null
```
