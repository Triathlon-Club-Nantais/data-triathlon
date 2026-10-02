"""Opposition d'un athlète à la publication de ses résultats (#334).

Ne porte **aucun nom** : la seule identité est l'empreinte de
`core/identity.identity_hash`, et aucune référence vers `athletes`, dont la
fiche disparaît à l'application. Le filtre d'import (`import_service`) relit les
empreintes pour anonymiser tout résultat entrant.
"""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class AthleteOpposition(Base):
    __tablename__ = "athlete_oppositions"

    id: Mapped[int] = mapped_column(primary_key=True)
    identity_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    #: Date de la demande, saisie par l'administrateur : elle fait courir le délai d'un mois.
    requested_on: Mapped[date] = mapped_column(Date, nullable=False)
    applied_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    #: Pas d'`ondelete`, patron `allowed_emails.created_by_user_id`.
    applied_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    anonymised_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    applied_by: Mapped["User | None"] = relationship()  # noqa: F821
