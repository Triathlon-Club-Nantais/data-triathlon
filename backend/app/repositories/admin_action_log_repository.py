"""Accès données pour AdminActionLog — seule couche qui touche la Session (Principe II).

**Deux fonctions, et pas de troisième.** Ni `update`, ni `delete` : un journal
d'audit modifiable ne prouve rien. `list_for_entity` n'a aujourd'hui qu'un
lecteur, les tests — la consultation du journal depuis une interface est un
besoin distinct, hors du périmètre de #117.
"""
from sqlalchemy.orm import Session

from app.models.admin_action_log import AdminActionLog


def create(
    db: Session,
    *,
    user_id: int,
    action: str,
    entity_type: str,
    entity_id: int,
    payload: dict | None = None,
) -> AdminActionLog:
    """Consigne un geste. **Ne commite pas** : la trace et l'action partagent la
    transaction du router, c'est ce qui les rend indissociables (FR-015)."""
    entree = AdminActionLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload,
    )
    db.add(entree)
    db.flush()
    return entree


def list_for_entity(db: Session, *, entity_type: str, entity_id: int) -> list[AdminActionLog]:
    """L'historique d'une entité, la plus récente d'abord.

    Tri sur `id` et non sur `created_at` : deux gestes de la même transaction
    portent le même horodatage à la microseconde près, et l'ordre deviendrait
    celui que la base voudra bien rendre.
    """
    return (
        db.query(AdminActionLog)
        .filter(
            AdminActionLog.entity_type == entity_type,
            AdminActionLog.entity_id == entity_id,
        )
        .order_by(AdminActionLog.id.desc())
        .all()
    )
