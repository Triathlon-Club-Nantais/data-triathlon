# Contrats API : relais multi-athlètes

Toutes les modifications de réponses existantes sont **additives** (Principe IV).

## Nouveau : `PUT /api/v1/admin/participations/{participation_id}/teammates`

Remplace la composition d'un résultat de relais. `PUT` : l'état soumis est
l'état voulu, rejouer la même requête ne change rien et n'écrit pas de journal
(même règle que `reassign_participation`, `services/admin_actions.py`).

Garde : `require_permission(P.PARTICIPATIONS_REASSIGN)`.

Requête :

```json
{
  "teammates": [
    { "athlete_id": 123 },
    { "athlete_name": "MARTIN", "athlete_firstname": "Paul" }
  ]
}
```

- 2 à 8 entrées. Chaque entrée porte soit `athlete_id`, soit `athlete_name` et
  `athlete_firstname` non vides.
- Champs d'entrée en anglais (Principe I), sur le précédent de
  `ParticipationCreate` (`backend/app/schemas/participation.py:122-123`). La
  sortie `AthleteBrief` garde `nom`/`prenom`, gelés par le contrat existant.
- Le premier équipier devient le porteur (`athlete.id` de la réponse).

Réponse `200` : `ParticipationOut` (avec `teammates` renseigné).

Erreurs (messages en français, `DomainError`) :

| Statut | Cas |
| --- | --- |
| 404 | Participation ou athlète inconnu |
| 409 | Un équipier a déjà un résultat sur cette épreuve (le message le nomme) |
| 422 | Corps invalide : moins de 2 ou plus de 8 équipiers, doublon, entrée incomplète |
| 400 | Résultat qui n'est pas un relais (`DomainError`, patron des refus métier du dépôt) |
| 401 / 403 | Sans session / sans le pouvoir |

## Modifié (additif) : `ParticipationOut`

```json
{
  "athlete": { "id": 123, "nom": "DUPONT", "prenom": "Jean" },
  "teammates": [
    { "id": 123, "nom": "DUPONT", "prenom": "Jean" },
    { "id": 456, "nom": "MARTIN", "prenom": "Paul" }
  ]
}
```

- `teammates: AthleteBrief[]`, liste vide par défaut. Vide pour tout résultat
  non attribué : les consommateurs actuels ne voient aucun changement.
- `frontend/lib/types.ts` suit.

## Modifié (additif) : `ClubPodiumEntry`

`teammate_names: string[]`, vide par défaut. `athlete_id` et `athlete_name`
restent ceux du porteur.

## Comportement modifié, sans changement de forme

- `GET /api/v1/athletes/{id}` : liste aussi les résultats où l'athlète figure
  comme équipier. Les compteurs individuels excluent les relais (spec FR-011).
- `POST /api/v1/admin/participations/{id}/reassign` sur un résultat attribué :
  vide la liaison (voir data-model, transitions).
