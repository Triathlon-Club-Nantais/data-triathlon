# Data Model: accès bénévoles par pouvoir SSO (#1272)

Aucune table, colonne ni migration.

## Acteur d'un geste bénévole (dérivé, non stocké)

| Mode d'admission | Acteur inscrit dans `admin_action_log.user_id` |
|---|---|
| Session SSO valide + pouvoir `benevole_access:manage` (cookie bénévoles indifférent) | `users.id` de l'administrateur |
| Cookie bénévoles valide seul | `users.id` du compte système `benevoles@systeme.interne` |
| Aucun des deux | refus 401, aucune écriture |

Entités existantes réutilisées : `User`, `UserSession` (résolution SSO), `BenevoleAccessConfig` (cookie), `AdminActionLog` (journal).
