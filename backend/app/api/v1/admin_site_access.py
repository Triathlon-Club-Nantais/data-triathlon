"""Gestion admin du mot de passe partagé du site (#509).

Ferme l'accès public au site entier, distinct du mot de passe bénévoles
(#271) : secret propre, table propre, gardé par le pouvoir dédié
`site_access:manage`. Patron exact de `admin_benevole_access.py` : `GET`
délègue à la lecture du repository (simple consultation), `PUT`/
`POST .../generate` délèguent à `services/site_access.replace_password` —
jamais un appel direct au repository pour ces deux gestes, qui combinent
hachage et rotation du secret de session (AGENTS.md, « routers fins :
délégation au service »).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.permissions import P
from app.models.user import User
from app.repositories import admin_action_log_repository, site_access_config_repository
from app.schemas.site_access_config import (
    SiteAccessConfigOut,
    SiteAccessGeneratedOut,
    SiteAccessReplaceIn,
)
from app.services import site_access

router = APIRouter(tags=["admin"])

#: `entity_id` constant : une seule ligne existe à tout instant (data-model.md).
_ENTITY_TYPE = "site_access_config"
_ACTION = "site_access.password_replace"


def _vue(config) -> SiteAccessConfigOut:
    return SiteAccessConfigOut(
        configured=config is not None,
        updated_at=config.updated_at if config else None,
        updated_by=config.updated_by.display_name if config else None,
    )


@router.get("/admin/site-access", response_model=SiteAccessConfigOut)
def get_access_config(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.SITE_ACCESS_MANAGE)),
):
    """État courant — 200 dans tous les cas, y compris jamais configuré."""
    return _vue(site_access_config_repository.get_config(db))


@router.put("/admin/site-access", response_model=SiteAccessConfigOut)
def replace_access_password(
    body: SiteAccessReplaceIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.SITE_ACCESS_MANAGE)),
):
    """Remplace le mot de passe par une saisie.

    Invalide immédiatement toute session site ouverte : `replace_password`
    régénère `session_secret` dans le même geste.
    """
    config, _mot_de_passe = site_access.replace_password(
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


@router.post("/admin/site-access/generate", response_model=SiteAccessGeneratedOut)
def generate_access_password(
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.SITE_ACCESS_MANAGE)),
):
    """Génère un mot de passe sécurisé.

    Le mot de passe généré n'est renvoyé **qu'ici**, une seule fois — rien
    côté serveur ne le conserve après le hachage.
    """
    config, mot_de_passe = site_access.replace_password(
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
    return SiteAccessGeneratedOut(
        password=mot_de_passe,
        updated_at=config.updated_at,
        updated_by=config.updated_by.display_name,
    )
