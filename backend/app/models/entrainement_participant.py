"""Modèle EntrainementParticipant — ce jeune est inscrit à cet entraînement
(#868, epic #863)."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class EntrainementParticipant(Base):
    """`(entrainement, jeune)` — et rien d'autre, sur le patron de `UserGroup`.

    **`jeune_id` référence `personal_profiles.id`** (#867). Posée sans FK à
    l'écriture initiale de #868, faute de table cible — #867 n'avait pas encore
    mergé sa table de profils. La contrainte a été resserrée après le merge de
    l'epic (#863), directement dans la migration d'origine (`e3649cbee16c`,
    rebasée sur celle de #867), plutôt que par une migration de suivi : cette
    révision n'était pas encore partagée ailleurs. Détail et alternatives
    écartées : `research.md` §Dépendance sur le profil jeune (#867).

    `UNIQUE(entrainement_id, jeune_id)` rend l'inscription **idempotente sous
    concurrence** : c'est la contrainte qui le fait, pas une lecture
    préalable, que deux exploitants simultanés franchiraient tous deux —
    même raisonnement que `UserGroup.uq_user_group`.

    Pas d'`ondelete` sur les deux FK, comme partout dans le dépôt
    (`core/database.py` n'émet aucun `PRAGMA foreign_keys=ON`) : côté
    `entrainement_id`, la cascade ORM (`Entrainement.participants`,
    `delete-orphan`) fait le travail des deux côtés ; côté `jeune_id`, aucune
    suppression de `PersonalProfile` n'est une ressource de cette feature —
    c'est le jour où #867 en posera une qu'il faudra décider quoi faire des
    inscriptions du profil supprimé.
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
    jeune_id: Mapped[int] = mapped_column(
        ForeignKey("personal_profiles.id"), index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    entrainement: Mapped["Entrainement"] = relationship(  # noqa: F821
        back_populates="participants"
    )
