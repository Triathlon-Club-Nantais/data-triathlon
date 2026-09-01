# Contract: Workflow de validation admin des actions de bénévolat (#779)

Un router neuf, `app/api/v1/admin_volunteer_actions.py`, patron
`admin_volunteer_declarations.py` (#751). Toutes les routes gardées par
`require_permission(P.ATHLETES_VOLUNTEER_VALIDATE)` (research.md D2).
L'endpoint de création admin existant
(`POST /admin/athletes/{athlete_id}/volunteer-actions`, `admin_data.py`)
n'est pas modifié — non répété ici.

## `GET /api/v1/admin/volunteer-actions/pending`

Liste les déclarations `VolunteerAction` à l'état `"en_attente"`,
tous athlètes confondus (FR-001).

**Response** `200`: `list[AdminVolunteerActionOut]`
```json
[
  {
    "id": 1,
    "athlete_id": 42,
    "season": 2026,
    "title": "Ravitaillement",
    "description": "Poste eau km 15.",
    "status": "en_attente",
    "declared_by_user_id": 17,
    "created_at": "2026-08-31T14:00:00Z"
  }
]
```

`title`/`description` peuvent être `null` (ligne créée par le chemin admin
existant, #709, edge case de spec.md).

## `POST /api/v1/admin/volunteer-actions/{action_id}/accept`

`"en_attente"` → `"validee"` (FR-003) ; idempotent si déjà `"validee"`
(FR-004). Journalise dans `AdminActionLog` sauf no-op (research.md D7).

**Response** `200`: `AdminVolunteerActionOut` (statut `"validee"`).

**Errors**: `404` — `action_id` introuvable.

## `POST /api/v1/admin/volunteer-actions/{action_id}/reject`

`"en_attente"` **ou** `"validee"` → `"refusee"` (FR-005, research.md D6) ;
idempotent si déjà `"refusee"` (FR-006).

**Response** `200`: `AdminVolunteerActionOut` (statut `"refusee"`).

**Errors**: `404` — `action_id` introuvable.

## Effet de bord : quota de saison

`GET /admin/athletes/{athlete_id}/season-quota` (existant, inchangé dans sa
forme) — son champ `has_volunteer_action` ne compte désormais que les
lignes `"validee"` (FR-008, research.md D3), plus aucune ligne
`"en_attente"` ou `"refusee"`.
