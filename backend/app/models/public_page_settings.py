"""PublicPageSettings : ce que l'athlète rattaché montre sur sa fiche publique (#1692).

Possédé par le compte (cascade ORM depuis `User.public_page_settings`, table de
`user_repository._OWNED_TABLES`) : il part avec lui. Une ligne par compte, créée
au premier enregistrement ; sans ligne, rien n'est masqué.
"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, false
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.time import utcnow


class PublicPageSettings(Base):
    __tablename__ = "public_page_settings"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    hide_best_times: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    hide_progression: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    hide_comparison: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    links: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    #: Résultat épinglé ; `SET NULL` est inerte en SQLite, donc la lecture revérifie l'appartenance.
    pinned_participation_id: Mapped[int | None] = mapped_column(
        ForeignKey("participations.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
