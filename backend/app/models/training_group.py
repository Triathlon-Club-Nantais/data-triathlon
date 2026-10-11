"""Modèles TrainingGroup et TrainingGroupMember : un ensemble nommé de profils
(#1291). Générique (FR-015) : rien n'y nomme le public jeune, la restriction vit
dans la garde `jeunes:read`/`jeunes:write`. Préfixe `training_` parce que
`groups` est déjà la table des groupes d'appartenance RBAC (#197)."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class TrainingGroup(Base):
    """Supprimer un groupe emporte ses appartenances et ses liens vers les séances
    et récurrences (cascade ORM et `secondary`), jamais les inscriptions déjà
    produites : elles sont une donnée de la séance."""

    __tablename__ = "training_groups"
    __table_args__ = (UniqueConstraint("organisation_id", "name", name="uq_training_group_org_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    members: Mapped[list["TrainingGroupMember"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )
    sessions: Mapped[list["TrainingSession"]] = relationship(  # noqa: F821
        secondary="training_session_groups", back_populates="groups"
    )
    recurrences: Mapped[list["TrainingRecurrence"]] = relationship(  # noqa: F821
        secondary="training_recurrence_groups", back_populates="groups"
    )


class TrainingGroupMember(Base):
    """`UNIQUE(training_group_id, profile_id)` rend l'ajout idempotent sous
    concurrence, patron `uq_training_participant`. La purge de rétention retire
    les appartenances d'un profil avant lui (pas d'`ondelete` dans ce dépôt)."""

    __tablename__ = "training_group_members"
    __table_args__ = (UniqueConstraint("training_group_id", "profile_id", name="uq_training_group_member"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    training_group_id: Mapped[int] = mapped_column(ForeignKey("training_groups.id"), index=True, nullable=False)
    profile_id: Mapped[int] = mapped_column(ForeignKey("personal_profiles.id"), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    group: Mapped[TrainingGroup] = relationship(back_populates="members")
    profile: Mapped["PersonalProfile"] = relationship()  # noqa: F821
