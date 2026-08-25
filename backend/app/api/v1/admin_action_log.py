"""Lecture du journal d'administration (#501) — une ressource, une garde.

Couche mince : délégation à `repositories/admin_action_log_repository.py`,
traduction en HTTP. Aucune écriture ici — le journal ne s'écrit que depuis les
gestes qu'il trace (`services/admin_actions.py`, `course_merge.py`,
`course_review.py`).

La garde est posée **sur la route**, jamais sur le préfixe (#115, FR-018) :
`admin.py` monte sous le même `/admin/` le signalement anonyme du site public.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.permissions import P
from app.models.user import User
from app.repositories import admin_action_log_repository
from app.schemas.admin import AdminActionLogEntry, AdminActionLogPage

router = APIRouter(tags=["admin"])


@router.get("/admin/action-log", response_model=AdminActionLogPage)
def list_action_log(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.ADMIN_LOG_READ)),
):
    """Les dernières entrées du journal, la plus récente d'abord.

    Pouvoir dédié plutôt que réutilisation de `courses:delete` ou
    `participations:wipe_all` : le journal couvre des entités que ces pouvoirs
    ne gardent pas (corrections de coureurs, réattributions de résultats), et
    « qui peut détruire peut lire son propre geste » n'est vrai que par
    accident.
    """
    entries, total = admin_action_log_repository.list_recent(
        db, page=page, page_size=page_size
    )
    return AdminActionLogPage(
        entries=[
            AdminActionLogEntry(
                id=entry.id,
                created_at=entry.created_at,
                user_name=entry.user.display_name or entry.user.email,
                action=entry.action,
                entity_type=entry.entity_type,
                entity_id=entry.entity_id,
                payload=entry.payload,
            )
            for entry in entries
        ],
        total=total,
    )
