# Data Model: Retrait du bouton admin de déclaration de bénévolat (#780)

## Aucun changement de schéma

`VolunteerAction` (existant) : `title`/`description` restent `nullable`
(research.md D2) — aucune migration Alembic dans cette sous-issue.

## Code retiré (pas de remplacement)

| Couche | Symbole | Fichier |
|---|---|---|
| API | `POST /admin/athletes/{athlete_id}/volunteer-actions` | `backend/app/api/v1/admin_data.py` |
| Service | `declare_volunteer_action()` | `backend/app/services/admin_actions.py` |
| Repository | `create()` | `backend/app/repositories/volunteer_action_repository.py` |
| Schéma | `VolunteerActionCreate`, `VolunteerActionOut` | `backend/app/schemas/admin.py` |
| Permission | `ATHLETES_VOLUNTEER_MANAGE` (`athletes:volunteer_manage`) | `backend/app/core/permissions.py` — retiré de la classe `P` **et** du tuple `ALL` |
| Frontend | `DeclarerBenevolat`, `peutDeclarerBenevolat` | `frontend/components/athletes/SeasonValidationPanel.tsx` |
| Frontend | `useDeclareVolunteerAction` | `frontend/lib/queries/admin.ts` |
| Frontend | `declareVolunteerAction` | `frontend/lib/api/client.ts` |
| Frontend | `VolunteerAction` (interface) | `frontend/lib/types.ts` — si orpheline (à vérifier par grep en fin de tâche) |

## Ce qui reste inchangé

- `VolunteerAction.title`/`.description`/`.status` (nullable, #778/#779).
- `create_pending()` (#778) — seul point de création restant.
- `list_for_athlete_season()`, `exists_for_athlete_season()`,
  `list_pending()`, `get()`, `set_status()`, `list_validated_for_athlete()`
  — toutes encore appelées (self-service, workflow de validation #779,
  fiche athlète #781).
- `admin_actions.season_quota()` — lit `exists_for_athlete_season()`,
  aucune dépendance au chemin retiré.
- `ValiderSaison`, `athletes:season_validate` (research.md D6).
