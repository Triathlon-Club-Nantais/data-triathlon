"""Modèle Identity — un moyen de se connecter à un utilisateur (#114)."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class Identity(Base):
    """Un moyen de connexion, révocable unitairement.

    Le couple `(provider, subject)` est la **seule** clé de résolution (FR-002) :
    l'adresse n'apparie jamais. Plusieurs identités peuvent pointer un même
    utilisateur, mais aucune n'est créée automatiquement à partir d'une autre —
    cette feature n'en crée qu'une, à la première connexion.

    C'est aussi la raison pour laquelle le futur mot de passe vivra **ici** et
    non sur `users` : « supprimer ma connexion par mot de passe » doit être la
    suppression d'une ligne, pas la mise à nul d'une colonne sur l'utilisateur.
    """

    __tablename__ = "identities"
    __table_args__ = (
        UniqueConstraint("provider", "subject", name="uq_identity_provider_subject"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    # `str` et non `int` : un entier déborderait sur certains dialectes, et tous
    # les fournisseurs n'émettent pas des identifiants numériques.
    subject: Mapped[str] = mapped_column(String, nullable=False)
    # Adresse constatée **chez ce fournisseur**, distincte de `users.email`.
    email: Mapped[str] = mapped_column(String, nullable=False)
    # Vide pour une identité déléguée ; accueille le futur mot de passe.
    secret_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    user: Mapped["User"] = relationship(back_populates="identities")  # noqa: F821
