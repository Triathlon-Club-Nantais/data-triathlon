"""Modèle PersonalProfile — profil individuel générique (#867, epic #863).

**Aucune mention « jeune » dans ce schéma**, et c'est délibéré : l'epic #863
anticipe une future extension aux adultes, non implémentée par cette feature.
La restriction « jeunes uniquement » pour cette itération vit entièrement dans
la garde d'accès (`jeunes:read`/`jeunes:write`, `app/core/permissions.py`),
jamais dans la table. Rationale complète :
`specs/20260915-111701-profil-jeune/research.md` (D1).

Patron `app/models/group.py` pour `organisation_id` (non nul — un profil est
celui d'une organisation précise, jamais global).
"""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class PersonalProfile(Base):
    __tablename__ = "personal_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    organisation_id: Mapped[int] = mapped_column(
        ForeignKey("organisations.id"), index=True, nullable=False
    )
    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str] = mapped_column(String, nullable=False)
    #: Optionnelle : un profil peut être créé avant que la date de naissance
    #: soit connue. L'âge se calcule à l'affichage, jamais stocké.
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    emergency_contact: Mapped[str] = mapped_column(String, default="", nullable=False)
    #: Fin d'adhésion saisie par un encadrant (#1158). Nulle tant que le jeune est
    #: adhérent ; le profil est purgé à la fin de la saison qui suit celle-ci.
    membership_ended_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )
    #: Pas d'`ondelete` : supprimer l'utilisateur qui a créé un profil ne doit
    #: ni effacer ni casser le profil (patron `allowed_emails.created_by_user_id`).
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    #: Sans cascade DB (pas d'`ondelete`) : la seule suppression d'un profil est
    #: la purge de rétention (#1158), et la cascade ORM `delete-orphan` y emporte
    #: le journal.
    log_entries: Mapped[list["ProfileLogEntry"]] = relationship(  # noqa: F821
        back_populates="profile", cascade="all, delete-orphan"
    )
