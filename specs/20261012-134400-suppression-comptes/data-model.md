# Data Model: Suppression des comptes

## `users` (modifiée)

| Colonne | Type | Contrainte | Note |
|---|---|---|---|
| `last_seen_at` | `DateTime` (UTC naïf) | `NOT NULL`, défaut `utcnow` | posée à l'ouverture de session, repoussée au plus une fois par jour ; rattrapée depuis `created_at` par la migration |

Aucune autre table modifiée.

## Suppression d'un compte

1. Refus si `email == SYSTEM_USER_EMAIL` (`SystemAccountDeletionError`, 409).
2. Refus si une colonne obligatoire de l'inventaire (research D1) cite le compte (`AccountStillReferencedError`, 409, « Votre compte est encore cité par des actions du club et ne peut pas être supprimé ici. Contactez le club pour le faire supprimer. »).
3. Dans `administrateurs_preserves` : mise à `NULL` des colonnes facultatives, `db.delete(user)` (cascade ORM : identités, sessions, rôles, groupes) ; `LastAdministratorError` (409) si l'état d'arrivée perd le dernier administrateur.
4. `audit.record(system_user_id, action="account.delete", entity_type="user", entity_id=<id>, payload={"origin": ...})`.

Pas de commit dans le service : la route commite, `purge_expired` commite.

## Éligibilité à l'expiration

`last_seen_at < now - 5 × 365 jours` ET aucune ligne `user_roles` ET `email != SYSTEM_USER_EMAIL`. Parmi les éligibles, un compte cité par une référence obligatoire est sauté.

## `RetentionOutcome` (étendu)

| Champ | Type | Sens |
|---|---|---|
| `accounts_deleted` | `int` | comptes supprimés (ou à supprimer en passe à blanc) |
| `accounts_skipped` | `int` | comptes éligibles conservés pour référence obligatoire |
