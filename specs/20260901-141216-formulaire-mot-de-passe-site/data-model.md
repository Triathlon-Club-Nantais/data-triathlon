# Data Model: Ouvrir le formulaire de crédit d'un athlète au mot de passe du site (#809)

## Changement de schéma

`VolunteerAction.declared_by_user_id` (`backend/app/models/
volunteer_action.py`) : `Mapped[int]` (FK `NOT NULL`) → `Mapped[int | None]`
(FK nullable, sans `ondelete`, sur le patron de `UserFeedback.user_id`).
Migration Alembic requise (`uv run alembic revision --autogenerate`, relecture
manuelle attendue).

## Code modifié

| Couche | Symbole | Fichier | Changement |
|---|---|---|---|
| Modèle | `VolunteerAction.declared_by_user_id` | `app/models/volunteer_action.py` | `int` → `int \| None` |
| Route | `creer_pour_un_athlete` | `app/api/v1/volunteer_actions.py` | `Depends(current_user)` → `Depends(optional_user)`, `user: User \| None` |
| Service | `create_pending` | `app/services/volunteer_action_service.py` | `declared_by_user_id: int` → `int \| None` |
| Repository | `create_pending` | `app/repositories/volunteer_action_repository.py` | `declared_by_user_id: int` → `int \| None` |
| Schéma | `VolunteerActionSelfOut.declared_by_user_id` | `app/schemas/volunteer_action.py` | `int` → `int \| None` |
| Schéma | `AdminVolunteerActionOut.declared_by_user_id` | `app/schemas/volunteer_action.py` | `int` → `int \| None` |
| Test d'ouverture | `ROUTES_VOLUNTEER_ACTIONS_FERMEES` | `tests/test_auth/test_public_routes_still_open.py` | retiré (ensemble vide), route sort de `ROUTES_FERMEES` |
| Frontend | section crédit d'athlète | `app/(public_restricted)/benevolat/page.tsx` | rendue hors du bloc `useSession()` |

## Ce qui reste inchangé

- `VolunteerAction.title`/`.description`/`.status`/`.athlete_id`/`.season`
  — aucun changement (research.md D2/D3 de #778/#780).
- `require_site_access` sur le routeur `volunteer_actions` (`v1/router.py`)
  — inchangé, reste la seule garde.
- Tout le domaine #779 (file d'attente admin, accept/reject,
  `athletes:volunteer_validate`) — inchangé, aucune route ni permission
  touchée.
- Tout le domaine #781 (`GET /admin/athletes/{id}/volunteer-actions/
  validated`, `VolunteerActionsList.tsx`) — inchangé, n'affiche pas
  `declared_by_user_id`.
- Le formulaire d'auto-déclaration #751 (`VolunteerDeclaration*`) — table et
  routes indépendantes, aucun changement.
- Tests existants qui appellent `create_pending(..., declared_by_user_id=
  auteur.id)` avec un entier réel — continuent de passer tels quels, une
  colonne nullable élargit ce qu'elle accepte sans invalider l'existant.
