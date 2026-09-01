# Contract: Liste des actions de bénévolat validées d'un athlète (#781)

Une seule route neuve, dans `app/api/v1/admin_volunteer_actions.py` (#779)
— même router, même garde que `pending`/`accept`/`reject`.

## `GET /api/v1/admin/athletes/{athlete_id}/volunteer-actions/validated`

Liste les déclarations `VolunteerAction` de cet athlète à l'état
`"validee"`, toutes saisons confondues, triées de la plus récente à la
plus ancienne (FR-001, FR-002, FR-004). Gardée par
`require_permission(P.ATHLETES_VOLUNTEER_VALIDATE)`.

**Response** `200`: `list[AdminVolunteerActionOut]`
```json
[
  {
    "id": 1,
    "athlete_id": 42,
    "season": 2026,
    "title": "Ravitaillement",
    "description": "Poste eau km 15.",
    "status": "validee",
    "declared_by_user_id": 17,
    "created_at": "2026-08-31T14:00:00Z"
  }
]
```

**Errors**: `403` — sans `athletes:volunteer_validate`. Pas de `404` sur
un `athlete_id` inconnu — liste vide (cohérent avec l'edge case de
spec.md, « aucune action » et « athlète inconnu » ne se distinguent pas
ici, aucun FR ne l'exige).
