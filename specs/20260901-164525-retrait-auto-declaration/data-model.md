# Data Model: Retrait de l'auto-déclaration de bénévolat (#816)

## Suppression de table

`VolunteerDeclaration` (`backend/app/models/volunteer_declaration.py`) —
table `volunteer_declarations` retirée par migration Alembic
(`op.drop_table`), aucune donnée conservée (research.md D2).

## Code retiré

| Couche | Symbole | Fichier |
|---|---|---|
| API | `POST/GET /volunteer-declarations`, `DELETE /volunteer-declarations/{id}` | `backend/app/api/v1/volunteer_declarations.py` |
| API | `GET/POST /admin/volunteer-declarations`, `POST .../{id}/validate`, `DELETE .../{id}` | `backend/app/api/v1/admin_volunteer_declarations.py` |
| Service | tout le module | `backend/app/services/volunteer_declaration_service.py` |
| Repository | tout le module | `backend/app/repositories/volunteer_declaration_repository.py` |
| Schéma | tout le module | `backend/app/schemas/volunteer_declaration.py` |
| Modèle | `VolunteerDeclaration` | `backend/app/models/volunteer_declaration.py` + retrait de l'import/export dans `backend/app/models/__init__.py` |
| Permission | `BENEVOLAT_READ`, `BENEVOLAT_MANAGE`, `FEATURE_VOLUNTEERING` | `backend/app/core/permissions.py` — retirés de `P` et `ALL` |
| Router | enregistrement des deux routers | `backend/app/api/v1/router.py` |
| Frontend | `VolunteerDeclarationForm`, `VolunteerDeclarationList` | `frontend/components/benevolat/` |
| Frontend | `AdminVolunteerDeclarationCreateForm`, `AdminVolunteerDeclarationTable` | `frontend/components/benevolat/` |
| Frontend | `useMyVolunteerDeclarations`, `useCreateVolunteerDeclaration`, `useDeleteMyVolunteerDeclaration` | `frontend/lib/queries/volunteer-declarations.ts` (fichier entier) |
| Frontend | `useAllVolunteerDeclarations`, `useAdminCreateVolunteerDeclaration`, `useValidateVolunteerDeclaration`, `useAdminDeleteVolunteerDeclaration` | `frontend/lib/queries/admin.ts` |
| Frontend | `myVolunteerDeclarations`, `adminVolunteerDeclarations` | `frontend/lib/queries/keys.ts` |
| Frontend | 7 méthodes client (`createVolunteerDeclaration` etc.) | `frontend/lib/api/client.ts` |
| Frontend | `VolunteerDeclaration`, `VolunteerDeclarationCreate`, `AdminVolunteerDeclaration`, `AdminVolunteerDeclarationCreate` | `frontend/lib/types.ts` |
| Frontend | entrée nav `id: "a-benevolat"` (215-221) et doublon orphelin (265) | `frontend/components/layout/nav.config.ts` |

## Ce qui reste, sans changement de comportement

- `VolunteerAction` (modèle, schémas, service, repository) — #778/#779/#809,
  inchangé.
- `POST /volunteer-actions`, `GET /admin/volunteer-actions/pending`,
  `POST .../{id}/accept`, `POST .../{id}/reject`,
  `GET /admin/athletes/{id}/volunteer-actions/validated` — inchangés.
- `athletes:volunteer_validate` — inchangé, aucun lien avec les pouvoirs
  retirés.
- `frontend/components/benevolat/VolunteerActionForm.tsx` — reste, son
  commentaire de désambiguïsation avec `VolunteerDeclarationForm` (ligne 14)
  est mis à jour (research.md D5).
