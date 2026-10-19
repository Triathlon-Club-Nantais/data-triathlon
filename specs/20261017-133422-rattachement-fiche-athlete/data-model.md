# Data Model: Revendiquer sa fiche athlète

## athlete_claims (nouvelle)

| Colonne | Type | Contrainte |
| --- | --- | --- |
| `id` | integer | PK |
| `user_id` | integer | FK `users.id`, **UNIQUE**, NOT NULL, sans `ondelete` (cascade ORM `User.athlete_claim`) |
| `athlete_id` | integer | FK `athletes.id` `ON DELETE CASCADE`, NOT NULL, index |
| `status` | varchar(16) | `pending` ou `rejected`, NOT NULL, index |
| `created_at` | datetime (UTC naïf) | NOT NULL, date de la demande |
| `decided_at` | datetime | NULL tant qu'en attente |

Transitions : (aucune) → `pending` (demande) ; `pending` → `rejected` (refus) ; `pending` → supprimée + `users.athlete_id` posé (validation) ; `pending` → supprimée (annulation) ; `pending`/`rejected` → remplacée par une nouvelle `pending` (nouvelle demande).

## users (existante)

`athlete_id` : désormais écrit à la validation, vidé au détachement. Aucune colonne nouvelle.

## Statut adhérent (dérivé)

`is_member(user) = actif ∧ non système ∧ (adresse dans member_emails de la saison ∨ athlete_id non nul)`.
