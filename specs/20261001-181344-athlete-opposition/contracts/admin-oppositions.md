# Contract: `/api/v1/admin/oppositions` (pouvoir `oppositions:manage`)

Toutes les routes : 401 sans session, 403 sans le pouvoir. Ajouts **additifs** au contrat v1.

## `GET /admin/oppositions`

```json
[{ "id": 3, "requested_on": "2026-09-20", "applied_at": "2026-10-01T16:00:00Z",
   "delay_days": 11, "overdue": false, "applied_by_name": "Admin", "anonymised_count": 4 }]
```

Tri : `applied_at` décroissant. `overdue` = délai > 30 jours. Aucun nom de la personne.

## `POST /admin/oppositions/preview`

Corps : `{ "athlete_id": 12 }` **ou** `{ "nom": "Dupont", "prenom": "Jean" }` (l'un ou l'autre, 422 sinon).

```json
{ "athletes": 2, "results": 5, "already_opposed": false }
```

`athletes` > 1 signale des homonymes.

## `POST /admin/oppositions`

Corps : la même identité que `preview`, plus `"requested_on": "2026-09-20"` (date, non future ; 422 sinon). 404 si `athlete_id` inconnu.

Rend `201` et la ligne au format de `GET`. Idempotent sur l'identité (réapplique, rend la ligne existante, `200`).

## Effets annexes

- `POST /feedback` accepte `type: "retrait"`.
- `POST /participations` (saisie manuelle) rend `422` `{"detail": "Cette personne s'est opposée à la publication de ses résultats : ce résultat ne peut pas être enregistré."}` sur une identité opposée.
- `PUT …/teammates` (composition) rend la même erreur sur un équipier opposé.
