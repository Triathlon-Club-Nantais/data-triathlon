"""Modèle EntrainementParticipant — ce jeune est inscrit à cet entraînement
(#868, epic #863)."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class EntrainementParticipant(Base):
    """`(entrainement, jeune)` — et rien d'autre, sur le patron de `UserGroup`.

    **`jeune_id` n'est volontairement pas une clé étrangère dans ce lot** : la
    table de profils jeunes vit dans la sous-issue parallèle #867, pas encore
    mergée au moment de l'implémentation de #868. La colonne référence par
    convention le futur `jeunes.id` ; une migration de suivi ajoutera la
    contrainte une fois #867 en base. Détail et alternatives écartées :
    `research.md` §Dépendance sur le profil jeune (#867).

    `UNIQUE(entrainement_id, jeune_id)` rend l'inscription **idempotente sous
    concurrence** : c'est la contrainte qui le fait, pas une lecture
    préalable, que deux exploitants simultanés franchiraient tous deux —
    même raisonnement que `UserGroup.uq_user_group`.

    Pas d'`ondelete` sur la FK `entrainement_id` : `core/database.py` n'émet
    aucun `PRAGMA foreign_keys=ON`, la cascade ORM (`Entrainement.participants`,
    `delete-orphan`) fait le travail des deux côtés.
    """

    __tablename__ = "entrainement_participants"
    __table_args__ = (
        UniqueConstraint(
            "entrainement_id", "jeune_id", name="uq_entrainement_participant"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    entrainement_id: Mapped[int] = mapped_column(
        ForeignKey("entrainements_jeunes.id"), index=True, nullable=False
    )
    jeune_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    entrainement: Mapped["Entrainement"] = relationship(  # noqa: F821
        back_populates="participants"
    )
