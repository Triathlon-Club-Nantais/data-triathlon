"""Gestion admin du mot de passe partagé bénévoles (#271 → cette feature).

Remplace `BENEVOLE_SHARED_PASSWORD` par une configuration en base, gérée par
un administrateur habilité (`benevole_access:manage`). Couche mince : `GET`
délègue à la lecture du repository (simple consultation, patron
`admin_allowed_emails.py`), `PUT`/`POST .../generate` délèguent à
`services/benevole_access.replace_password` — jamais un appel direct au
repository pour ces deux gestes, qui combinent hachage et rotation du secret
de session (AGENTS.md, « routers fins : délégation au service »).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.permissions import P
from app.models.user import User
from app.repositories import admin_action_log_repository, benevole_config_repository
from app.schemas.benevole_access import (
    BenevoleAccessConfigOut,
    BenevoleAccessGeneratedOut,
    BenevoleAccessReplaceIn,
)
from app.services import benevole_access

router = APIRouter(tags=["admin"])

#: `entity_id` constant : une seule ligne existe à tout instant (data-model.md).
_ENTITY_TYPE = "benevole_access_config"
_ACTION = "benevole_access.password_replace"


def _vue(config) -> BenevoleAccessConfigOut:
    return BenevoleAccessConfigOut(
        configured=config is not None,
        updated_at=config.updated_at if config else None,
        updated_by=config.updated_by.display_name if config else None,
    )


@router.get("/admin/benevoles/access", response_model=BenevoleAccessConfigOut)
def get_access_config(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.BENEVOLE_ACCESS_MANAGE)),
):
    """État courant — 200 dans tous les cas, y compris jamais configuré."""
    return _vue(benevole_config_repository.get_config(db))


@router.put("/admin/benevoles/access", response_model=BenevoleAccessConfigOut)
def replace_access_password(
    body: BenevoleAccessReplaceIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.BENEVOLE_ACCESS_MANAGE)),
):
    """Remplace le mot de passe par une saisie (Story 1, FR-001).

    Invalide immédiatement toute session bénévole ouverte : `replace_password`
    régénère `session_secret` dans le même geste (FR-006).
    """
    config, _mot_de_passe = benevole_access.replace_password(
        db, password=body.password, admin_user_id=actor.id
    )
    admin_action_log_repository.create(
        db,
        user_id=actor.id,
        action=_ACTION,
        entity_type=_ENTITY_TYPE,
        entity_id=config.id,
    )
    db.commit()
    return _vue(config)


@router.post("/admin/benevoles/access/generate", response_model=BenevoleAccessGeneratedOut)
def generate_access_password(
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.BENEVOLE_ACCESS_MANAGE)),
):
    """Génère un mot de passe sécurisé (Story 2, FR-002/FR-003).

    Le mot de passe généré n'est renvoyé **qu'ici**, une seule fois — rien
    côté serveur ne le conserve après le hachage (research.md §D5).
    """
    config, mot_de_passe = benevole_access.replace_password(
        db, password=None, admin_user_id=actor.id
    )
    admin_action_log_repository.create(
        db,
        user_id=actor.id,
        action=_ACTION,
        entity_type=_ENTITY_TYPE,
        entity_id=config.id,
    )
    db.commit()
    return BenevoleAccessGeneratedOut(
        password=mot_de_passe,
        updated_at=config.updated_at,
        updated_by=config.updated_by.display_name,
    )
