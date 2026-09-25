"""Modèle TrainingParticipant — ce profil est inscrit à cette séance
(#868, epic #863)."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class TrainingParticipant(Base):
    """`(training_session, profile)` — et rien d'autre, sur le patron de `UserGroup`.

    **`profile_id` référence `personal_profiles.id`** (#867). Posée sans FK à
    l'écriture initiale de #868, faute de table cible — #867 n'avait pas encore
    mergé sa table de profils. La contrainte a été resserrée après le merge de
    l'epic (#863), directement dans la migration d'origine (`e3649cbee16c`,
    rebasée sur celle de #867), plutôt que par une migration de suivi : cette
    révision n'était pas encore partagée ailleurs. Détail et alternatives
    écartées : `research.md` §Dépendance sur le profil jeune (#867).

    `UNIQUE(training_session_id, profile_id)` rend l'inscription **idempotente sous
    concurrence** : c'est la contrainte qui le fait, pas une lecture
    préalable, que deux exploitants simultanés franchiraient tous deux —
    même raisonnement que `UserGroup.uq_user_group`.

    Pas d'`ondelete` sur les deux FK, comme partout dans le dépôt
    (`core/database.py` n'émet aucun `PRAGMA foreign_keys=ON`) : côté
    `training_session_id`, la cascade ORM (`TrainingSession.participants`,
    `delete-orphan`) fait le travail des deux côtés ; côté `profile_id`, aucune
    suppression de `PersonalProfile` n'est une ressource de cette feature —
    c'est le jour où #867 en posera une qu'il faudra décider quoi faire des
    inscriptions du profil supprimé.
    """

    __tablename__ = "training_participants"
    __table_args__ = (
        UniqueConstraint(
            "training_session_id", "profile_id", name="uq_training_participant"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    training_session_id: Mapped[int] = mapped_column(
        ForeignKey("training_sessions.id"), index=True, nullable=False
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("personal_profiles.id"), index=True, nullable=False
    )
    #: Statut de l'appel de **début** (#869) pour ce profil, à cette séance.
    #: `NULL` = pas encore pointé, `True`/`False` = le dernier statut
    #: enregistré fait foi (aucun historique des changements). Même
    #: granularité que la ligne elle-même : une colonne sur la relation
    #: plutôt qu'une table de présence séparée (cf. research.md D1 de
    #: `specs/20260915-141516-appel-jeunes/`).
    present: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    training_session: Mapped["TrainingSession"] = relationship(  # noqa: F821
        back_populates="participants"
    )
