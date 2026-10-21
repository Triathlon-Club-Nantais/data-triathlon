"""MemberRequest : la demande d'adhésion d'un compte connecté qui n'est pas adhérent (#1785).

Une au plus par compte et par organisation, en attente ou refusée. Acceptée,
elle disparaît (le compte reçoit un rôle) ; l'historique est le journal
d'administration. Possédée par le compte (cascade ORM depuis `User.member_requests`).
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow

STATUS_PENDING = "pending"
STATUS_REJECTED = "rejected"


class MemberRequest(Base):
    __tablename__ = "member_requests"
    __table_args__ = (
        UniqueConstraint("user_id", "organisation_id", name="uq_member_request_user_organisation"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id"))
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="member_requests")  # noqa: F821
