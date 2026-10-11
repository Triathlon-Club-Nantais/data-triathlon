"""MemberEmail : une adresse d'adhérent pour une saison (#1334).

Importée de l'export AssoConnect ou ajoutée à la main, elle reconnaît un
adhérent à la connexion. Distincte d'`allowed_emails` (porte du back-office).
Aucune autre donnée de l'export n'est gardée.
"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.time import utcnow

SOURCE_IMPORT = "import"
SOURCE_MANUAL = "manual"


class MemberEmail(Base):
    __tablename__ = "member_emails"
    __table_args__ = (UniqueConstraint("email", "season", name="uq_member_email_season"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320))
    season: Mapped[int] = mapped_column(Integer, index=True)
    source: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
