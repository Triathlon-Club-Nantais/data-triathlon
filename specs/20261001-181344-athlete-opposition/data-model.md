# Data Model: Droit d'opposition effectif

## Table `athlete_oppositions` (nouvelle)

| Colonne | Type | Règle |
| --- | --- | --- |
| `id` | int PK | |
| `identity_hash` | str(64), **UNIQUE**, index | SHA-256 de la clé normalisée (research R3) |
| `requested_on` | date, non nul | date de la demande, saisie par l'administrateur |
| `applied_at` | datetime, non nul | horodatage de l'application |
| `applied_by_user_id` | FK `users.id`, nullable | sans `ondelete`, patron `allowed_emails.created_by_user_id` |
| `anonymised_count` | int, non nul | résultats anonymisés à l'application |

Aucun nom, aucune référence vers `athletes` (la fiche disparaît).

Une seconde opposition sur la même identité ne crée pas de ligne : elle réapplique (de nouveaux résultats ont pu entrer par une saisie antérieure) et rend la ligne existante.

## Effets sur l'existant (application)

Pour chaque athlète dont la clé normalisée correspond :

- chaque participation dont il est porteur : rattachée à un athlète anonyme `Anonyme {course_id}-{dossard}` (ou `Anonyme {course_id}-p{participation_id}` sans dossard), `club`, `category` et `raw_data` vidés ; `tcn_count` de l'épreuve ajusté ;
- chaque liaison d'équipier (`participation_teammates`) où il figure : remplacée, à sa position, par un équipier anonyme (`Anonyme {course_id}-{dossard}-{position}`), une équipe gardant 2 à 8 membres ; la ligne brute du relais vidée ;
- `users.athlete_id` → `NULL` ; `volunteer_actions`, `season_validations` de l'athlète : supprimées ;
- la fiche `athletes` : supprimée ;
- une entrée `admin_action_log` (`action="opposition.apply"`, `entity_type="opposition"`, `entity_id` = id de l'opposition, payload : `requested_on`, `anonymised_count`, **sans nom**).

## `user_feedback.type`

Valeurs : `bug`, `feedback`, `retrait`.
