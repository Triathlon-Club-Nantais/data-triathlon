"""SiteAccessConfig — mot de passe partagé fermant l'accès public au site
(#509). Même schéma que `BenevoleAccessConfig` (#271), table distincte :
les deux secrets tournent indépendamment, deux populations différentes.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class SiteAccessConfig(Base):
    """État courant du mot de passe partagé du site. Une seule ligne existe
    à tout instant ; absence de ligne = accès non configuré (fail-closed).
    """

    __tablename__ = "site_access_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    password_salt: Mapped[str] = mapped_column(String, nullable=False)
    session_secret: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    #: NULL quand le code a été posé hors ligne par `set-site-code` (#929) :
    #: une installation neuve n'a encore aucun utilisateur à qui l'attribuer.
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    updated_by: Mapped["User | None"] = relationship()  # noqa: F821
