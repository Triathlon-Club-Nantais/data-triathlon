"""Modèle UserSession — la preuve qu'un navigateur agit pour un utilisateur (#114)."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class UserSession(Base):
    """Empreinte d'une session ouverte.

    Nommée `user_sessions` et non `sessions` : `Session` désignerait deux choses
    dans des modules qui importent aussi SQLAlchemy.

    Le jeton brut n'existe qu'en mémoire et dans le cookie ; la base n'en garde
    que le SHA-256 (FR-012). Trois colonnes sont **délibérément absentes**,
    toutes ajoutables plus tard par migration purement additive :
    `last_seen_at` (une écriture par requête authentifiée pour zéro lecteur),
    `user_agent` (donnée quasi personnelle sans durée de conservation) et
    `revoked_at` — la déconnexion **supprime** la ligne.
    """

    __tablename__ = "user_sessions"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_user_session_token"),)

    # Ne franchit **jamais** l'API : séquentiel, donc énumérable.
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    user: Mapped["User"] = relationship(back_populates="sessions")  # noqa: F821
