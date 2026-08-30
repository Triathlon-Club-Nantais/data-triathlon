# Quickstart: Déclaration de bénévolat

## Prérequis

```bash
cd backend
uv sync
uv run alembic upgrade head   # après la migration de cette feature
uv run python scripts/dev_server.py
```

Deux comptes de test : un membre standard connecté, un compte admin avec
`benevolat:manage` (composer un rôle via `/admin/droits` ou seed de test).

## Scénario 1 — Auto-déclaration, en attente (US1, SC-001, SC-004)

1. Connecté en membre standard, `POST /api/v1/volunteer-declarations`
   `{"title": "Ravitaillement", "description": "Poste eau, 10km du Lac"}`.
2. Vérifier la réponse `201`, `status: "en_attente"`,
   `beneficiary_user_id == author_user_id`.
3. `GET /api/v1/volunteer-declarations` → la déclaration apparaît, statut
   `"en_attente"`.
4. Titre ou description vide → `422`, rien de créé (FR-002).

## Scénario 2 — Admin déclare pour un tiers, validée d'office (US2)

1. Connecté en admin (`benevolat:manage`),
   `POST /admin/volunteer-declarations`
   `{"title": "...", "description": "...", "beneficiary_user_id": <id>}`.
2. Vérifier `201`, `status: "validee"` directement.
3. Vérifier une ligne `AdminActionLog` avec
   `action: "volunteer_declaration.create_for_other"`.

## Scénario 3 — Validation d'une déclaration en attente (US3)

1. Reprendre la déclaration du Scénario 1 (`id`).
2. Connecté en admin, `POST /admin/volunteer-declarations/{id}/validate`.
3. Vérifier `status: "validee"` en réponse et en base.
4. Rejouer le même appel → `200` sans changement (idempotent, edge case).

## Scénario 4 — Suppression (US4)

1. Le membre standard supprime sa propre déclaration (validée ou non) :
   `DELETE /api/v1/volunteer-declarations/{id}` → `204`.
2. `GET /api/v1/volunteer-declarations` ne la liste plus (SC-002).
3. Un autre membre standard tente `DELETE` sur une déclaration qui n'est pas
   la sienne → `404`.
4. Un admin supprime la déclaration d'un tiers via
   `DELETE /admin/volunteer-declarations/{id}` → `204`, ligne
   `AdminActionLog` `action: "volunteer_declaration.delete"`.

## Scénario 5 — Consultation (US5)

1. Membre standard : `GET /api/v1/volunteer-declarations` ne retourne que
   ses propres déclarations, triées récent → ancien.
2. Admin : `GET /admin/volunteer-declarations` retourne celles de tous les
   membres, avec l'identité du bénéficiaire.

## Vérification automatisée

```bash
uv run pytest -m "not integration" backend/tests/test_api/test_volunteer_declarations_api.py backend/tests/test_admin_actions_volunteer_declarations.py
cd frontend && npm test -- VolunteerDeclaration
```
