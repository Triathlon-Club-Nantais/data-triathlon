"""Modèle BenevoleAccessConfig — le mot de passe partagé bénévoles, géré depuis
le back-office plutôt que par la variable d'environnement `BENEVOLE_SHARED_PASSWORD`
(#271, cette feature).

Une seule ligne existe à tout instant : le remplacement du mot de passe est un
`UPDATE` de cette ligne si elle existe, son unique `INSERT` sinon. **Absence de
ligne = accès non configuré** (fail-closed, FR-007), même prédicat qu'aujourd'hui.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class BenevoleAccessConfig(Base):
    """État courant du mot de passe partagé bénévoles.

    `password_hash`/`password_salt` ne permettent que de **vérifier** une
    tentative de connexion, jamais de retrouver le mot de passe (FR-004).
    `session_secret` signe le cookie de session bénévole (research.md §D2 de
    cette feature) — distinct du mot de passe, pour que la vérification n'ait
    jamais besoin de le relire en clair. Les trois champs sont toujours
    réécrits **ensemble** par `services/benevole_access.replace_password` :
    jamais l'un sans les autres, sous peine de casser soit la vérification du
    mot de passe soit l'invalidation des sessions (FR-006).
    """

    __tablename__ = "benevole_access_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    password_salt: Mapped[str] = mapped_column(String, nullable=False)
    session_secret: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    updated_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    updated_by: Mapped["User"] = relationship()  # noqa: F821
