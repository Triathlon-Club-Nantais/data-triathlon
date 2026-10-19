"""ResultClaim : un compte rattaché réclame un résultat rangé sur une autre fiche (#1637).

En attente ou refusée ; validée, elle disparaît et le résultat a changé de fiche
(`admin_actions.reassign_participation`, journal). Une par compte et résultat.
Possédée par le compte (cascade ORM depuis `User.result_claims`), elle suit son
résultat (`ON DELETE CASCADE`).
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow

STATUS_PENDING = "pending"
STATUS_REJECTED = "rejected"


class ResultClaim(Base):
    __tablename__ = "result_claims"
    __table_args__ = (UniqueConstraint("user_id", "participation_id", name="uq_result_claim_user_participation"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    participation_id: Mapped[int] = mapped_column(ForeignKey("participations.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="result_claims")  # noqa: F821
    participation: Mapped["Participation"] = relationship()  # noqa: F821
