"""AthleteClaim : la demande d'un compte de rattacher sa fiche athlète (#1325).

Une au plus par compte (`UNIQUE(user_id)`), en attente ou refusée. Validée,
elle disparaît et le rattachement vit sur `users.athlete_id` ; l'historique des
décisions est le journal d'administration. Possédée par le compte (cascade ORM
depuis `User.athlete_claim`), elle suit sa fiche : `ON DELETE CASCADE`, report
à la fusion (`athlete_merge`).
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow

STATUS_PENDING = "pending"
STATUS_REJECTED = "rejected"


class AthleteClaim(Base):
    __tablename__ = "athlete_claims"
    __table_args__ = (UniqueConstraint("user_id", name="uq_athlete_claim_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="athlete_claim")  # noqa: F821
    athlete: Mapped["Athlete"] = relationship()  # noqa: F821
