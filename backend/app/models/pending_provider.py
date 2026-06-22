"""Modèle PendingProvider — URLs dont le scraping a échoué, signalées pour implémentation."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.time import utcnow


class PendingProvider(Base):
    __tablename__ = "pending_providers"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String)
    provider_hint: Mapped[str] = mapped_column(String, default="")  # domaine extrait de l'URL
    reported_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    handled: Mapped[bool] = mapped_column(Boolean, default=False)
