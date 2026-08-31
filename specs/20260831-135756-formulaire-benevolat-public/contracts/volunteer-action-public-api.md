# Contract: Formulaire public de déclaration de bénévolat (#778)

Un seul router neuf, patron `volunteer_declarations.py` (#751) : le chemin
dit qui peut appeler. L'endpoint admin existant
(`app/api/v1/admin_data.py`, `POST /admin/athletes/{athlete_id}/
volunteer-actions`) n'est pas modifié — non répété ici.

## Router public (authentifié) — `app/api/v1/volunteer_actions.py`

Exige `current_user` (401 si absent), aucun pouvoir RBAC. Inclus dans
`v1/router.py` **hors** de `_EXEMPTES_DE_LA_GARDE_SITE` — hérite donc aussi
de `require_site_access` à l'inclusion, comme `volunteer_declarations`.

### `POST /api/v1/volunteer-actions`

Crée une déclaration de bénévolat pour l'athlète choisi, à l'état
`"en_attente"` (FR-001 à FR-004, FR-009). `season` dérivé côté serveur
(`current_season()`, research.md D5) — absent du corps de requête. Schéma
`VolunteerActionSelfCreate` (nommé ainsi pour ne pas collisionner avec
`VolunteerActionCreate` de `schemas/admin.py`, distinct et inchangé).

**Request**:
```json
{
  "athlete_id": 42,
  "title": "string, 1-200 caractères",
  "description": "string, 1-10 000 caractères"
}
```

**Response** `201`:
```json
{
  "id": 1,
  "athlete_id": 42,
  "season": 2026,
  "title": "...",
  "description": "...",
  "status": "en_attente",
  "declared_by_user_id": 17,
  "created_at": "2026-08-31T14:00:00Z"
}
```

**Errors**:
- `422` — `title`/`description` vide ou hors bornes (validation Pydantic, FR-004).
- `404` — `athlete_id` introuvable.
- `401` — pas de session.

## Recherche d'athlète : aucune route neuve

Le formulaire interroge la route publique existante
`GET /api/v1/athletes?name=` (`app/api/v1/athletes.py`, déjà en place,
FR-006/FR-007) — voir research.md D2. Comportement inchangé :

**Response** `200`: `list[AthleteBrief]` — `{ id, nom, prenom, gender, club }`,
jamais `birth_date`.
