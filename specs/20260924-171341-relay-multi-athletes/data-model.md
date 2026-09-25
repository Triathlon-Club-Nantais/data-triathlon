# Data Model: Rattacher un résultat de relais à plusieurs athlètes

## Nouvelle table `participation_teammates`

| Colonne | Type | Contrainte |
| --- | --- | --- |
| `participation_id` | int | FK `participations.id`, `ON DELETE CASCADE`, partie de la PK |
| `athlete_id` | int | FK `athletes.id`, `ON DELETE RESTRICT`, partie de la PK |

- PK composite `(participation_id, athlete_id)` : un athlète n'apparaît
  qu'une fois par résultat.
- Index `ix_participation_teammates_athlete_id` : lectures par athlète.
- Migration Alembic autogénérée puis relue (contraintes de la constitution).
  Aucune donnée existante n'est migrée (reprise hors périmètre).

## `Participation` (existante)

- `athlete_id` : inchangé, toujours renseigné. Sur un résultat attribué, c'est
  l'équipier porteur, le premier de la liste soumise.
- `team_name` : à l'attribution, reçoit le nom de la fiche d'origine s'il est
  vide. Sert d'affichage (FR-009) et de clé d'appariement au rescrape sans
  dossard (research R3).
- Relation ORM `teammates` (lecture), ordonnée par ordre d'insertion.

## Invariants

1. Liaison vide : résultat classique, un seul athlète (`athlete_id`).
2. Liaison non vide : de 2 à 8 lignes, et `athlete_id` en fait partie.
3. Seul un résultat de relais (`Participation.is_relay` ou `Course.is_relay`)
   peut avoir une liaison non vide.
4. Aucun équipier ne porte un autre résultat sur la même épreuve (en direct ou
   par une liaison).

## Transitions

| Depuis | Geste | Vers |
| --- | --- | --- |
| Liaison vide, athlète fictif F | Attribuer [A, B, …] | Liaison [A, B, …], `athlete_id = A`, `team_name` = nom de F si vide, F purgé s'il est orphelin |
| Liaison [A, B] | Attribuer [A, C] | Liaison [A, C], `athlete_id = A`, B purgé s'il est orphelin |
| Liaison [A, B] | Réattribution simple vers X (existante) | Liaison vidée, `athlete_id = X`, A et B purgés s'ils sont orphelins |
| Liaison [A, B] | Rescrape de l'épreuve | Inchangée (research R3) |

Chaque transition écrit une ligne de journal d'administration.

## Journal

`action = "participation.set_teammates"`, `entity_type = "participation"`,
`payload = {course_id, from_athlete_id, teammate_ids, athletes_created,
athletes_purged}`.
