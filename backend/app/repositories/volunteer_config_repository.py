"""Accès données pour VolunteerAccessConfig — seule couche qui touche la Session.

Une seule ligne existe à tout instant (data-model.md) : `save_config` écrit
la ligne existante si elle existe, la crée sinon. **Ne commite jamais** — la
transaction reste portée par le service appelant, comme partout ailleurs.
"""
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.volunteer_access_config import VolunteerAccessConfig

#: Id fixe de la ligne unique — nommée `SINGLETON_ID` jusqu'à la revue de #513,
#: qui a jugé le mot illisible : il dit la forme de la table, pas ce que la
#: constante porte. Renommée ici comme dans le jumeau `site_access_config_repository`
#: (#509), pour que les deux modules continuent de se lire l'un par l'autre.
#:
#: Deux administrateurs (ou un double-clic)
#: remplaçant le mot de passe au tout premier réglage peuvent tous deux
#: constater l'absence de ligne avant que l'un des deux n'écrive — une
#: lecture préalable serait franchie par les deux. La contrainte de clé
#: primaire, elle, ne l'est jamais : le second `INSERT` échoue et se
#: rattrape en `UPDATE` (patron `allowed_email_repository.add`).
CONFIG_ROW_ID = 1


def get_config(db: Session) -> VolunteerAccessConfig | None:
    """La configuration courante, ou `None` si aucun mot de passe n'a jamais
    été défini (fail-closed, FR-007). `updated_by` est chargé dans la même
    requête — l'écran l'affiche à chaque consultation."""
    return db.scalar(
        select(VolunteerAccessConfig).options(
            joinedload(VolunteerAccessConfig.updated_by)
        )
    )


def save_config(
    db: Session,
    *,
    password_hash: str,
    password_salt: str,
    session_secret: str,
    updated_by_user_id: int,
) -> VolunteerAccessConfig:
    """Écrit les trois champs secrets **ensemble** — jamais l'un sans les
    autres (data-model.md, invariant d'atomicité).

    Le cas ordinaire (la ligne existe déjà) se lit puis se met à jour, sans
    détour. **Seule** l'absence de ligne tente une création, sous point de
    reprise : un autre exploitant a pu insérer entre cette lecture et cette
    écriture (remplacement concurrent au tout premier réglage), et c'est
    alors la contrainte de clé primaire — jamais une seconde lecture, que
    les deux franchiraient pareillement — qui tranche.
    """
    config = db.get(VolunteerAccessConfig, CONFIG_ROW_ID)
    if config is not None:
        config.password_hash = password_hash
        config.password_salt = password_salt
        config.session_secret = session_secret
        config.updated_by_user_id = updated_by_user_id
        db.flush()
        db.refresh(config)
        return config

    config = VolunteerAccessConfig(
        id=CONFIG_ROW_ID,
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
        config = db.get(VolunteerAccessConfig, CONFIG_ROW_ID)
        if config is None:  # pragma: no cover — une autre contrainte a cédé
            raise
        config.password_hash = password_hash
        config.password_salt = password_salt
        config.session_secret = session_secret
        config.updated_by_user_id = updated_by_user_id
        db.flush()
    db.refresh(config)
    return config
