# Contract: API déclaration de bénévolat

Deux routers, patron `feedback.py` / `admin_feedback.py` : le chemin dit qui
peut appeler.

## Router public (authentifié) — `app/api/v1/volunteer_declarations.py`

Toutes les routes exigent `current_user` (401 si absent — contrairement à
`feedback.py` qui accepte l'anonyme via `optional_user`, cette feature n'a
pas de cas d'usage non-authentifié).

### `POST /api/v1/volunteer-declarations`

Crée une auto-déclaration (FR-001). Toujours `beneficiary_user_id ==
author_user_id == current_user.id`, statut `"en_attente"` forcé côté service
— le corps ne porte pas de champ bénéficiaire ni de statut.

**Request**:
```json
{ "title": "string, non vide", "description": "string, non vide" }
```

**Response** `201`:
```json
{
  "id": 1,
  "title": "...",
  "description": "...",
  "status": "en_attente",
  "beneficiary_user_id": 42,
  "author_user_id": 42,
  "created_at": "2026-08-30T16:02:00Z"
}
```

**Errors**: `422` (titre/description vide — validation Pydantic, FR-002).

### `GET /api/v1/volunteer-declarations`

Liste les déclarations du membre connecté (FR-009), triées par
`created_at desc`. Pas de pagination — volume par membre attendu faible
(cohérent avec l'absence d'index composite, data-model.md).

**Response** `200`: `list[VolunteerDeclarationOut]` (schéma ci-dessus).

### `DELETE /api/v1/volunteer-declarations/{id}`

Supprime une déclaration dont `author_user_id == current_user.id`
(FR-006/FR-007), quel que soit son statut.

**Response**: `204`.

**Errors**: `404` uniquement (introuvable, ou appartient à un autre membre —
même réponse dans les deux cas, pas de fuite d'existence). Cette route ne
vérifie jamais `benevolat:manage` — la suppression de la déclaration d'un
tiers par un admin passe exclusivement par
`DELETE /admin/volunteer-declarations/{id}` ci-dessous, un router distinct.
*(Corrigé après `/speckit-analyze`, finding I3 : une mention `403` trompeuse
laissait croire que cette route self-service portait elle-même une garde
`benevolat:manage`.)*

## Router admin — `app/api/v1/admin_volunteer_declarations.py`

### `POST /admin/volunteer-declarations`

Réservé à `benevolat:manage`. Crée une déclaration validée d'office pour
n'importe quel membre (FR-004).

**Request**:
```json
{
  "title": "string, non vide",
  "description": "string, non vide",
  "beneficiary_user_id": 17
}
```

**Response** `201`: `VolunteerDeclarationOut` (statut `"validee"`).

**Side effect**: `AdminActionLog` — `action:
"volunteer_declaration.create_for_other"`.

**Errors**: `404` (`beneficiary_user_id` inconnu) ; `422` (champs vides).

### `GET /admin/volunteer-declarations`

Réservé à `benevolat:read` (ou `benevolat:manage`, qui l'inclut — voir plan.md
§ Constitution Check pour la règle d'inclusion des pouvoirs admin). Vue
d'ensemble, tous membres, tous statuts (FR-010).

**Response** `200`: `list[VolunteerDeclarationOut]`, avec en plus l'identité
du bénéficiaire pour l'affichage admin (voir schéma étendu
`AdminVolunteerDeclarationOut` — `beneficiary_display_name`/`beneficiary_email`,
patron `AdminAthleteRead` vs `AthleteRead`).

### `POST /admin/volunteer-declarations/{id}/validate`

Réservé à `benevolat:manage`. Fait passer `status` de `"en_attente"` à
`"validee"` (FR-005). Idempotent : si déjà `"validee"`, `200` sans effet
(edge case du spec).

**Response** `200`: `VolunteerDeclarationOut`.

**Side effect**: `AdminActionLog` — `action: "volunteer_declaration.validate"`.

**Errors**: `404` (id inconnu).

### `DELETE /admin/volunteer-declarations/{id}`

Réservé à `benevolat:manage`. Supprime la déclaration de n'importe quel
membre (FR-006), quel que soit son statut.

**Response**: `204`.

**Side effect**: `AdminActionLog` — `action: "volunteer_declaration.delete"`.

**Errors**: `404`.
