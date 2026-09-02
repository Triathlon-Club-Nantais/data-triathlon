# Data Model: Suppression d'une déclaration de crédit de bénévolat

Aucune migration Alembic — cette feature ne touche aucune colonne, elle
ajoute un chemin de suppression sur un modèle déjà en place.

## VolunteerAction (existant, `backend/app/models/volunteer_action.py`)

| Champ | Type | Rôle dans cette feature |
|---|---|---|
| `id` | `int` (PK) | Clé de la route `DELETE /admin/volunteer-actions/{id}` |
| `athlete_id` | `int` (FK `athletes.id`) | Entité journalisée (`entity_id` du log) et clé d'invalidation du cache front |
| `season` | `int` | Porté par le payload du journal et par l'invalidation du cache `season-quota` |
| `status` | `str` (`en_attente` / `validee` / `refusee`) | Aucune contrainte de statut sur la suppression (FR-001 : les trois statuts sont supprimables) |

Pas de nouvelle colonne, pas de nouvel état de `status` (cf. research.md D3 —
suppression définitive, pas de statut « supprimée »).

## Repository — nouvelle fonction

```text
delete(db: Session, action: VolunteerAction) -> None
```

Sur le patron de `course_source_repository.remove` : `db.delete(action)` +
`db.flush()`, aucune requête de validation dans le repository (la validation
d'existence reste côté service, via `_action_ou_404`).

## Service — nouvelle fonction

```text
delete(db: Session, *, admin_user_id: int, action_id: int) -> None
```

1. `action = _action_ou_404(db, action_id)` (lève `NotFoundError` sinon).
2. Capture `payload = {"season": action.season, "action_id": action_id, "status": action.status}` avant suppression (research.md D4).
3. `volunteer_action_repository.delete(db, action)`.
4. `admin_action_log_repository.create(db, user_id=admin_user_id, action="athlete.volunteer_action.delete", entity_type="athlete", entity_id=action.athlete_id, payload=payload)`.

Pas de valeur de retour utile côté route (204 No Content, comme la
suppression de source #739) — contrairement à `accept`/`reject`, qui
renvoient l'entité mise à jour, il n'y a plus d'entité à renvoyer après
suppression.

## État — pas de nouvelle transition

`VolunteerAction.status` ne gagne aucune valeur : la suppression retire la
ligne, elle ne la fait pas transiter vers un état terminal supplémentaire.
Le diagramme de statut existant (`en_attente` → `validee`/`refusee`, chacun
idempotent sur lui-même) reste inchangé ; la suppression s'applique aux
trois états sans distinction.
