# Phase 1 — Modèle de données

**Feature** : pagination et recherche du classement d'une épreuve (issue #163)

## Ce que cette feature ne change pas

**Aucune table n'est créée, modifiée ni supprimée.** `Athlete`, `Course`,
`Participation` sont lus tels quels. La feature ne porte que sur la lecture.

Une **seule** migration Alembic est produite, et elle ne touche à aucune table :
`CREATE EXTENSION IF NOT EXISTS unaccent`, nécessaire à la recherche
insensible aux accents sur PostgreSQL (cf. `research.md`, R2). Sur SQLite elle
est sans objet — le développement passe par une fonction Python enregistrée à
la connexion.

## Champs lus

### Tranche de classement

Lus depuis `Participation`, avec `Athlete` joint : les champs de
`ParticipationOut`, inchangés. La jointure sur l'athlète est nécessaire au
tri (nom, prénom), à la recherche et à l'affichage.

### Synthèse d'épreuve

Lus depuis `Participation`, avec `Athlete` joint, **colonnes seules** — aucun
objet ORM n'est hydraté :

| Champ | Origine | Sert à |
|---|---|---|
| `status` | `Participation` | décompte ventilé |
| `club` | `Participation` | top clubs, appartenance au club, compteur TCN |
| `category` | `Participation` | répartition par catégorie |
| `total_time` | `Participation` | histogramme |
| `splits` | `Participation` | clés de colonnes de temps intermédiaires |
| `gender` | `Athlete` | répartition par genre |

## Formes de sortie

Deux schémas Pydantic nouveaux. `CourseSummary` et ses sous-modèles vivent dans
`app/schemas/course.py`, aux côtés de `EventPage` dont ils reprennent la logique
d'enveloppe. `CourseParticipationPage` vit dans `app/schemas/participation.py` :
`course.py` ne peut pas importer `ParticipationOut` sans créer un cycle, ce
dernier module important déjà `CourseBrief`.

### `CourseParticipationPage`

Enveloppe de la réponse de `GET /courses/{id}`, dans son intégralité — elle
porte donc aussi la course. Les lignes sont des `ParticipationOut` existants.

| Champ | Type | Sens |
|---|---|---|
| `course` | `CourseBrief` | l'épreuve, inchangé |
| `participations` | `list[ParticipationOut]` | la tranche, dans l'ordre d'affichage |
| `total` | `int` | nombre de participations **de la sélection** (recherche et filtre club appliqués) |
| `page` | `int` | numéro de la tranche rendue, à partir de 1 |
| `page_size` | `int \| None` | taille demandée ; `None` quand `all` a été demandé |

**Le champ s'appelle `participations`, pas `items`.** C'est la clé que la route
rend déjà, et la seule chose que la feature n'a aucune raison de casser : le
contrat change sur la *quantité* de lignes (FR-005), pas sur leur *nom*.
`EventPage` emploie `items` de son côté, mais c'est une route de liste, sans
antériorité à préserver.

`total` porte sur la sélection et non sur l'épreuve : c'est lui qui donne le
nombre de pages. Les décomptes d'épreuve entière vivent dans la synthèse, et
nulle part ailleurs — deux totaux dans une même réponse s'inverseraient un jour.

### `CourseSummary`

Synthèse d'épreuve entière. Aucun de ses champs ne dépend de la recherche ni du
filtre club (FR-018).

| Champ | Type | Sens |
|---|---|---|
| `total` | `int` | partants |
| `finishers` | `int` | statut `finisher` |
| `non_finishers` | `int` | `DNF`, `DSQ`, `DNS` |
| `unknown` | `int` | statut vide ou non reconnu |
| `tcn_count` | `int` | participations du club |
| `male` / `female` | `int` | répartition par genre, sur les seules lignes genrées |
| `categories` | `list[CategoryCount]` | `{name, count}`, décroissant, 8 au plus |
| `clubs` | `list[ClubCount]` | `{name, count, is_tcn}`, décroissant, 9 au plus |
| `histogram` | `Histogram \| None` | `null` si aucun temps exploitable |
| `split_keys` | `list[str]` | clés de temps intermédiaires renseignées sur au moins une participation, dans l'ordre d'apparition |

`total = finishers + non_finishers + unknown` est un invariant, éprouvé par un
test : c'est ce que garantit déjà `countOutcomes` côté navigateur, et c'est ce
qui distingue « partants » de « finishers » (#23).

`Histogram` porte `bars: list[int]`, `start_sec: int`, `bucket_sec: int` —
mêmes champs que la fonction `buildHistogram` qu'elle remplace, pour que l'axe
des abscisses continue de s'ancrer sur des heures rondes (#129).

## Règles de validation

| Entrée | Règle | Sinon |
|---|---|---|
| `page` | entier ≥ 1 | 422 |
| `page_size` | entier entre 1 et 200, ou le mot `all` | 422 (FR-007) |
| `q` | chaîne libre ; vide ou blancs = pas de recherche | — |
| `scope` | `club` ou absent | absent = pas de filtre (Principe V) |
| `page` au-delà du dernier | tranche vide, `total` exact | jamais d'erreur (FR-004) |
| épreuve inexistante | `NotFoundError` | 404, comportement actuel inchangé |

## Ce qu'aucune sortie n'enregistre

- **Aucun rang recalculé.** Le rang affiché reste `rank_overall` tel qu'importé.
  La position d'une ligne dans une page n'est pas un rang, et ne doit jamais en
  tenir lieu — plusieurs sources publient des rangs en doublon (relais
  runnerbreizh) ou absents.
- **Aucun décompte par page.** Le pied de tableau annonce le décompte de
  l'épreuve entière (FR-030), qui vient de la synthèse. Un décompte de page n'a
  pas de sens métier.
