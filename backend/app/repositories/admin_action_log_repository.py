"""Accès données pour AdminActionLog — seule couche qui touche la Session (Principe II).

**Ni `update`, ni suppression ciblée** : un journal d'audit modifiable ne prouve
rien. La seule suppression est la purge de rétention (#1158), par ancienneté
seule, jamais par entrée. `list_recent` (#501) est la lecture paginée qui
alimente l'écran d'administration ; `list_for_entity` reste utilisée par les
tests et n'a pas d'autre lecteur.
"""
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, joinedload

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


def entity_ids_with_action(db: Session, *, action: str, entity_ids: list[int]) -> set[int]:
    """Celles de ces entités qu'un geste `action` a touchées."""
    if not entity_ids:
        return set()
    return set(
        db.scalars(
            select(AdminActionLog.entity_id).where(
                AdminActionLog.action == action, AdminActionLog.entity_id.in_(entity_ids)
            )
        )
    )


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


def list_recent(
    db: Session, *, page: int = 1, page_size: int = 20
) -> tuple[list[AdminActionLog], int]:
    """Les dernières entrées du journal, la plus récente d'abord (#501).

    Tri sur `id` et non sur `created_at`, même raison que `list_for_entity` :
    deux gestes de la même transaction partagent l'horodatage à la microseconde
    près. `user` est chargé dans la même requête (`joinedload`) — l'écran
    affiche l'auteur sur chaque ligne, et une requête par ligne serait un N+1.
    """
    total = db.query(func.count(AdminActionLog.id)).scalar() or 0
    offset = (page - 1) * page_size
    entries = (
        db.query(AdminActionLog)
        .options(joinedload(AdminActionLog.user))
        .order_by(AdminActionLog.id.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    return entries, total


def count_created_before(db: Session, cutoff: datetime) -> int:
    return db.scalar(select(func.count()).select_from(AdminActionLog).where(AdminActionLog.created_at < cutoff))


def delete_created_before(db: Session, cutoff: datetime) -> int:
    """Purge de rétention (#1158). Rend le nombre d'entrées supprimées."""
    return db.execute(delete(AdminActionLog).where(AdminActionLog.created_at < cutoff)).rowcount


def list_with_payload(db: Session) -> list[AdminActionLog]:
    """Entrées portant une charge, pour en masquer un nom (#334). Bornées par la rétention de 12 mois."""
    return list(db.scalars(select(AdminActionLog).where(AdminActionLog.payload.is_not(None))))
