# Contrat API : extensions additives de `/api/v1`

Lecture publique, aucune garde nouvelle (FR-009). Aucun champ retiré, aucun sens
inversé (Principe IV).

## `GET /api/v1/courses/{id}`

Paramètres inchangés (`page`, `page_size`, `q`, `scope`, `club`, `category`).

Réponse : un champ ajouté.

```json
{
  "course": { "...": "CourseBrief, inchangé" },
  "participations": ["... tranche du classement validé, inchangée"],
  "total": 0,
  "page": 1,
  "page_size": 20,
  "pending_participations": [
    { "id": 246845, "is_pending_validation": true, "is_rejected": false, "...": "ParticipationOut" }
  ]
}
```

- `pending_participations` : résultats en attente **non refusés** de l'épreuve,
  filtrés par `q`, `scope`, `club`, `category` comme le classement, triés par nom
  puis prénom puis id ; indépendants de `page` et `page_size` (rendus en entier à
  chaque page). Vide par défaut.
- `total` et `participations` : inchangés, ne contiennent jamais de ligne en attente.

## `GET /api/v1/courses/events`

Paramètres inchangés. Chaque `EventOut` gagne :

```json
{ "id": 1195, "total": 0, "tcn_count": 0, "pending_count": 1, "...": "inchangé" }
```

- `pending_count` : résultats en attente non refusés de l'épreuve qui satisfont les
  filtres de la requête. Défaut `0`.
- La page liste désormais aussi une épreuve dont `total = 0` et `pending_count > 0`.
- `total`, `tcn_count`, `total_participations` : comptes de résultats validés,
  inchangés.
- `total_events` : nombre d'épreuves listées, y compris celles qui n'ont que des
  résultats en attente (clarification Q5).

## Inchangés

`GET /courses/{id}/summary`, `GET /courses`, `GET /courses/count`, `/stats/*`,
`/club/*`, `/athletes/*`, `/admin/quality/count` : aucun champ ni valeur ne change.
