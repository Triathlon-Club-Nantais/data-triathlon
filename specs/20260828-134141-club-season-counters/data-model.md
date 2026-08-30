# Data Model: Compteurs de saison distincts + validation humaine du quota club

**Feature**: `specs/20260828-134141-club-season-counters/spec.md`
**Décisions source** : `research.md` D4, D5, D6.

## Nouvelles entités

### `VolunteerAction`

Une action de bénévolat déclarée pour un athlète et une saison. Journal
append-only — plusieurs lignes possibles pour le même `(athlete_id, season)`
(D4).

| Colonne | Type | Contraintes | Notes |
|---|---|---|---|
| `id` | `int` | PK | |
| `athlete_id` | `int` | FK `athletes.id`, `NOT NULL`, indexé | Pas d'`ondelete` (convention du dépôt, cf. `AdminActionLog.user_id`) |
| `season` | `int` | `NOT NULL`, indexé | Année de début, même convention que `core/season.py::season_of` |
| `declared_by_user_id` | `int` | FK `users.id`, `NOT NULL` | L'auteur ne disparaît jamais (même choix que `AdminActionLog.user_id`) |
| `created_at` | `datetime` | `NOT NULL`, `default=utcnow` | |

Pas de colonne `course_id` (D4 — hors périmètre, aucune exigence de la spec
ne la requiert). Pas d'`UPDATE`/`DELETE` exposés — cohérent avec les Edge
Cases de la spec.

**Requête dérivée** : « le barème bénévolat est-il atteint pour
`(athlete_id, season)` ? » ⇔ `EXISTS(SELECT 1 FROM volunteer_actions WHERE
athlete_id = :id AND season = :season)`.

### `SeasonValidation`

Le statut de validation de la saison d'un athlète (D5). **L'existence de la
ligne porte le statut** — pas de colonne booléenne.

| Colonne | Type | Contraintes | Notes |
|---|---|---|---|
| `id` | `int` | PK | |
| `athlete_id` | `int` | FK `athletes.id`, `NOT NULL`, indexé | |
| `season` | `int` | `NOT NULL` | |
| `validated_by_user_id` | `int` | FK `users.id`, `NOT NULL` | |
| `validated_at` | `datetime` | `NOT NULL`, `default=utcnow` | |

**Contrainte d'unicité** : `UniqueConstraint("athlete_id", "season", name="uq_season_validation_athlete_season")`
— une saison ne peut être validée qu'une fois à la fois pour un athlète
(revalider une saison déjà validée est un no-op contrôlé par le service, pas
une double ligne).

**Cycle de vie** :
- **Valider** : `INSERT` la ligne (échoue proprement sur la contrainte
  d'unicité si déjà validée — le service vérifie l'existence avant, comme
  `update_identity` documente le faire ailleurs dans ce repository).
- **Dévalider** : `DELETE` la ligne.
- Chaque opération écrit, dans la **même transaction**, une entrée
  `AdminActionLog` (`action="athlete.season_validation.create"` /
  `"athlete.season_validation.delete"`, `entity_type="athlete"`,
  `entity_id=athlete_id`, `payload={"season": ...}`) — c'est cette table qui
  porte l'historique complet, pas `SeasonValidation` elle-même (D6).

## Entités existantes, non modifiées en schéma

- **`Athlete`** (`app/models/athlete.py`) : source de `Athlete.club` pour la
  sélection du roster (D1). Aucune colonne ajoutée — le statut de validation
  vit dans `SeasonValidation`, pas sur `Athlete` (une ligne par athlète **et**
  saison, cf. FR-010).
- **`Participation`** : `club` et `is_pending_validation` restent les deux
  colonnes sources des trois compteurs (D2). Aucun changement de schéma.
- **`AdminActionLog`** : réutilisé tel quel (D6) — aucune colonne ajoutée,
  aucune migration sur cette table.

## Relations

```text
Athlete 1──* VolunteerAction        (athlete_id)
Athlete 1──* SeasonValidation       (athlete_id, unique par season)
User    1──* VolunteerAction        (declared_by_user_id)
User    1──* SeasonValidation       (validated_by_user_id)
```

Aucune relation ORM bidirectionnelle requise sur `Athlete`/`User` — même
sens unique que le patron `AdminActionLog.user` (Principe II : les
repositories dédiés, `volunteer_action_repository.py` et
`season_validation_repository.py`, sont la seule couche qui interroge ces
tables).

## Migration

Une migration Alembic (`uv run alembic revision --autogenerate`) crée les
deux tables `volunteer_actions` et `season_validations`, avec leurs index
(`athlete_id`, et `(athlete_id, season)` unique pour la seconde). Aucune
colonne existante modifiée — migration additive pure, revue manuelle de la
révision générée (Additional Constraints de la constitution).
