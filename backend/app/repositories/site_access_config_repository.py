"""Accès données pour SiteAccessConfig — seule couche qui touche la Session.

Patron identique à `benevole_config_repository.py` : une seule ligne existe
à tout instant, `save_config` écrit la ligne existante ou la crée. Ne
commite jamais — la transaction reste portée par le service appelant.
"""
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.site_access_config import SiteAccessConfig

#: La clé primaire de l'unique ligne de `site_access_config`, **figée à 1**.
#:
#: C'est bien l'`id` en base (question posée en revue de #513) : la table est un
#: singleton — un seul mot de passe de site existe à tout instant — et fixer la
#: clé plutôt que de laisser l'autoincrément la donner est ce qui rend le
#: singleton vrai. `save_config` fait `db.get(SiteAccessConfig, SINGLETON_ID)`
#: puis écrit cette ligne ou la crée avec cet `id` : deux appels concurrents
#: entrent en collision de clé primaire (`IntegrityError`, rattrapée par le
#: savepoint) au lieu de créer une seconde configuration que personne ne lirait.
#:
#: Même nom et même valeur que `benevole_config_repository.SINGLETON_ID` (#271),
#: dont ce module est le jumeau — les renommer n'aurait de sens qu'ensemble.
SINGLETON_ID = 1


def get_config(db: Session, *, with_updated_by: bool = True) -> SiteAccessConfig | None:
    """`with_updated_by=False` pour la garde (`api/deps.require_site_access`) :
    posée sur pratiquement chaque requête (revue finale, Fix #7), elle ne lit
    jamais que `session_secret` et n'a donc aucune raison de payer la jointure
    sur `updated_by`, utile à la seule vue d'administration
    (`admin_site_access.get_access_config`), qui garde `with_updated_by=True`."""
    query = select(SiteAccessConfig)
    if with_updated_by:
        query = query.options(joinedload(SiteAccessConfig.updated_by))
    return db.scalar(query)


def save_config(
    db: Session,
    *,
    password_hash: str,
    password_salt: str,
    session_secret: str,
    updated_by_user_id: int,
) -> SiteAccessConfig:
    config = db.get(SiteAccessConfig, SINGLETON_ID)
    if config is not None:
        config.password_hash = password_hash
        config.password_salt = password_salt
        config.session_secret = session_secret
        config.updated_by_user_id = updated_by_user_id
        db.flush()
        db.refresh(config)
        return config

    config = SiteAccessConfig(
        id=SINGLETON_ID,
        password_hash=password_hash,
        password_salt=password_salt,
        session_secret=session_secret,
        updated_by_user_id=updated_by_user_id,
    )
    try:
        with db.begin_nested():
            db.add(config)
            db.flush()
    except IntegrityError:
        config = db.get(SiteAccessConfig, SINGLETON_ID)
        if config is None:  # pragma: no cover
            raise
        config.password_hash = password_hash
        config.password_salt = password_salt
        config.session_secret = session_secret
        config.updated_by_user_id = updated_by_user_id
        db.flush()
    db.refresh(config)
    return config
