# Phase 1 — Data Model : les 13 questions que l'app ne sait pas montrer

Aucune nouvelle entité : les 13 vues consomment et étendent des entités déjà
normalisées (`backend/app/models/AGENTS.md`). Une seule extension de modèle
DB (US13), deux extensions additives de schéma de sortie (US4, US5). Le
reste est de l'agrégation en lecture, sans changement de schéma DB.

## Extension de modèle — `Participation` (US13)

| Champ | Type | Nullable | Rempli par |
| --- | --- | --- | --- |
| `validated_at` | `DateTime` | oui (NULL tant que non résolu) | le service de validation, au moment où `is_pending_validation` passe à faux avec acceptation |
| `rejected_at` | `DateTime` | oui (NULL tant que non résolu) | le service de validation, au moment où `is_rejected` passe à vrai |

- **Invariant** : au plus un des deux est non-NULL à la fois ; les deux sont
  NULL tant que la participation est en attente.
- **Migration** : `uv run alembic revision --autogenerate -m "ajoute
  validated_at/rejected_at à participation"`, relecture manuelle obligatoire
  (constitution, Additional Constraints). Colonnes nullables, aucun backfill
  possible pour l'historique déjà résolu avant cette migration (donnée jamais
  capturée) — l'arriéré affiché ne couvre que les résolutions postérieures au
  déploiement, à documenter dans l'état vide du graphique (edge case déjà
  posé dans `spec.md`).
- **Couche** : la colonne est écrite par le service de validation existant
  (celui qui bascule `is_pending_validation`/`is_rejected`), pas par une
  nouvelle couche — respecte le sens unique `api → services →
  repositories → DB` (Principe II).

## Extensions additives de schéma — `backend/app/schemas/participation_stats.py`

### `RankingEvolutionStep` (US5)

| Champ | Type | Statut |
| --- | --- | --- |
| `cumulative_seconds` | `int \| None` | **nouveau**, additif |

Valeur déjà produite par `_cumulative_seconds`
(`participation_stats_service.py:107-119`), simplement non exposée
aujourd'hui. Champ additif : ne casse aucun consommateur existant de
`GET /participations/{id}/stats` (Principe IV).

### `ComparisonRow` (US4)

| Champ | Type | Statut |
| --- | --- | --- |
| `mine_seconds` | `int \| None` | **nouveau**, additif |
| `theirs_seconds` | `int \| None` | **nouveau**, additif |

Valeurs déjà produites par `_comparison`
(`participation_stats_service.py:94-96`) avant réduction en pourcentage pour
`ComparisonTable`. Additif, même route.

## Vues dérivées côté client (aucun changement DB/API)

Ces vues consomment des données déjà chargées par les routes existantes ;
elles vivent en `frontend/lib/utils/` à côté des agrégations déjà en place
(`ranking.ts`, `club-aggregate.ts`, `format.ts`).

| Vue | Source déjà chargée | Dérivation |
| --- | --- | --- |
| Série de progression (US1) | `data.participations` sur `/athletes/[id]` | `rankRatio(p)` par participation, ordonné par `course.event_date` |
| Répartition disciplines × saisons (US7) | `data.participations` | groupement par `event_type`/saison depuis `event_date` |
| Roster avec catégorie (US9) | `Participation.category`, déjà chargé pour `buildRoster` | ajout de `category` à `RosterEntry` |
| Podiums × discipline (US10) | `podiumsByScope` (déjà calculé) + `formatToken` | groupement croisé avant affichage |
| Couverture temporelle (US11) | liste d'épreuves (`page_size=all`) | groupement par mois/année sur `event_date` |
| Filtre carte à venir/distance (US12) | `lat`/`lon`/`event_date` déjà sur le type carte | comparaison de date + haversine vs. point de référence statique |

## Entités inchangées, réutilisées telles quelles

- **Participation** : `rank_overall`, `rank_category`, `course_finishers`,
  `splits` (JSON), `category`, `gender` — tous déjà présents, réutilisés en
  lecture par plusieurs US.
- **Course** : `event_date`, `event_type`, `distance_km`, `lat`/`lon` — déjà
  présents.
- **Athlète** : identité déjà normalisée, aucune extension requise.
- **CourseSummary** (`GET /courses/{id}/summary`) : `histogram`,
  `categories`/`categories_total` déjà servis, simplement pas fetchés
  aujourd'hui depuis l'écran de détail de participation (US2, US3).
