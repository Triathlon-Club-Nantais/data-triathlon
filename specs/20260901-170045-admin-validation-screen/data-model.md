# Data Model: Écran de validation admin des déclarations de crédit d'athlète (#817)

## Aucun changement de schéma

`VolunteerAction` gagne une relation ORM (`athlete`) et une propriété de
lecture (`athlete_nom`/`athlete_prenom`) — aucune colonne, aucune migration
(research.md D1/D2).

## Code ajouté

| Couche | Symbole | Fichier |
|---|---|---|
| Modèle | `VolunteerAction.athlete` (relation), `.athlete_nom`/`.athlete_prenom` (propriétés) | `backend/app/models/volunteer_action.py` |
| Schéma | `AdminVolunteerActionOut.athlete_nom`/`.athlete_prenom` | `backend/app/schemas/volunteer_action.py` |
| Repository | `selectinload(VolunteerAction.athlete)` dans `list_pending()` | `backend/app/repositories/volunteer_action_repository.py` |
| Frontend | `AdminVolunteerActionsTable` | `frontend/components/benevolat/AdminVolunteerActionsTable.tsx` (+ `.test.tsx`) |
| Frontend | `usePendingVolunteerActions`, `useAcceptVolunteerAction`, `useRejectVolunteerAction` | `frontend/lib/queries/admin.ts` |
| Frontend | `pendingVolunteerActions` | `frontend/lib/queries/keys.ts` |
| Frontend | `listPendingVolunteerActions`, `acceptVolunteerAction`, `rejectVolunteerAction` | `frontend/lib/api/client.ts` |
| Frontend | `AdminVolunteerActionOut.athlete_nom`/`.athlete_prenom` | `frontend/lib/types.ts` |
| Frontend | entrée nav `id: "a-benevolat-validation"` | `frontend/components/layout/nav.config.ts` |
| Frontend | contenu définitif de la page | `frontend/app/admin/benevolat/page.tsx` (état minimal posé par #816) |

## Ce qui reste, sans changement

- `GET /admin/volunteer-actions/pending`, `POST .../{id}/accept`,
  `POST .../{id}/reject` (#779) — routes inchangées, seule leur réponse
  s'enrichit de deux champs.
- `athletes:volunteer_validate` — pouvoir inchangé, seule garde de l'écran.
- `GET /admin/athletes/{id}/volunteer-actions/validated` (#781),
  `VolunteerActionsList.tsx` — inchangés.
- Le flux de crédit lui-même (#778/#809) — inchangé.
