# Contrat : routes utilisateur du rattachement

Toutes exigent une session (401 sinon) et passent `core/origin_guard` pour les écritures. Routeur `auth`, exempté de la garde du site.

## `GET /api/v1/auth/me` (champs additifs)

```json
{
  "athlete": {"id": 42, "prenom": "Léa", "nom": "Martin"},
  "athlete_claim": {"athlete": {"id": 42, "prenom": "Léa", "nom": "Martin"}, "status": "pending", "created_at": "2026-10-17T12:00:00Z"}
}
```

`athlete` : `null` sans rattachement. `athlete_claim` : `null` sans demande ; `status` ∈ `pending`, `rejected`.

## `POST /api/v1/auth/me/athlete-claim`

Corps `{"athlete_id": 42}` (`DbId`). **201** avec `athlete_claim` ci-dessus (`status: "pending"`). Remplace une demande en attente ou refusée.

- **404** fiche inexistante (« Fiche athlète introuvable. »).
- **409** compte déjà rattaché (« Votre compte est déjà rattaché à une fiche : détachez-vous d'abord. »).

## `DELETE /api/v1/auth/me/athlete-claim`

Annule la demande en attente ou efface la demande refusée. **204**, idempotent.

## `DELETE /api/v1/auth/me/athlete`

Détache le compte de sa fiche. **204**, idempotent.
