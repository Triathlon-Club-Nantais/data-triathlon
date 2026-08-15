"""Accès données pour BenevoleAccessConfig — seule couche qui touche la Session.

Une seule ligne existe à tout instant (data-model.md) : `save_config` écrit
la ligne existante si elle existe, la crée sinon. **Ne commite jamais** — la
transaction reste portée par le service appelant, comme partout ailleurs.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.benevole_access_config import BenevoleAccessConfig


def get_config(db: Session) -> BenevoleAccessConfig | None:
    """La configuration courante, ou `None` si aucun mot de passe n'a jamais
    été défini (fail-closed, FR-007). `updated_by` est chargé dans la même
    requête — l'écran l'affiche à chaque consultation."""
    return db.scalar(
        select(BenevoleAccessConfig).options(
            joinedload(BenevoleAccessConfig.updated_by)
        )
    )


def save_config(
    db: Session,
    *,
    password_hash: str,
    password_salt: str,
    session_secret: str,
    updated_by_user_id: int,
) -> BenevoleAccessConfig:
    """Écrit les trois champs secrets **ensemble** — jamais l'un sans les
    autres (data-model.md, invariant d'atomicité)."""
    config = db.scalar(select(BenevoleAccessConfig))
    if config is None:
        config = BenevoleAccessConfig()
        db.add(config)
    config.password_hash = password_hash
    config.password_salt = password_salt
    config.session_secret = session_secret
    config.updated_by_user_id = updated_by_user_id
    db.flush()
    db.refresh(config)
    return config
