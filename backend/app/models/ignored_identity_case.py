"""IgnoredIdentityCase — un cas de revue d'identité à une seule fiche, écarté (#1252).

Les cas à deux fiches s'écartent par paire (`IgnoredAthletePair`). Un cas à une
fiche (`same_course_bibs`) n'a pas de seconde fiche à nommer : la décision porte
sur la fiche, son motif, et l'empreinte des données jugées (`fingerprint`, les
épreuves en conflit). Une empreinte qui change fait revenir le cas.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.time import utcnow


class IgnoredIdentityCase(Base):
    __tablename__ = "ignored_identity_cases"
    __table_args__ = (
        UniqueConstraint("athlete_id", "reason", name="uq_ignored_identity_case"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Même raison que `IgnoredAthletePair` : une fiche disparaît par plusieurs chemins.
    # Pas d'index propre : `uq_ignored_identity_case` commence par elle.
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id", ondelete="CASCADE"))
    reason: Mapped[str] = mapped_column(String(32))
    fingerprint: Mapped[str] = mapped_column(Text)
    ignored_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    ignored_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
