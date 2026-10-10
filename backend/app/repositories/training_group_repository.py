"""Accès données pour TrainingGroup et TrainingGroupMember (#1291). On `flush()`,
jamais de `commit()` : la transaction reste au service, patron `group_repository`."""
from datetime import date

from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.personal_profile import PersonalProfile
from app.models.training_group import TrainingGroup, TrainingGroupMember


def get(db: Session, training_group_id: int) -> TrainingGroup | None:
    return db.get(TrainingGroup, training_group_id)


def list_by_ids(db: Session, training_group_ids: list[int]) -> list[TrainingGroup]:
    if not training_group_ids:
        return []
    return list(db.scalars(select(TrainingGroup).where(TrainingGroup.id.in_(training_group_ids))))


def find_by_name(db: Session, *, organisation_id: int, name: str) -> TrainingGroup | None:
    return db.scalar(
        select(TrainingGroup).where(TrainingGroup.organisation_id == organisation_id, TrainingGroup.name == name)
    )


def list_with_member_counts(db: Session) -> list[tuple[TrainingGroup, int]]:
    """Les groupes triés par nom, avec leur nombre de membres, en une requête."""
    count = func.count(TrainingGroupMember.id)
    return [
        (group, member_count)
        for group, member_count in db.execute(
            select(TrainingGroup, count)
            .outerjoin(TrainingGroupMember, TrainingGroupMember.training_group_id == TrainingGroup.id)
            .group_by(TrainingGroup.id)
            .order_by(TrainingGroup.name)
        ).all()
    ]


def create(db: Session, *, organisation_id: int, name: str) -> TrainingGroup:
    group = TrainingGroup(organisation_id=organisation_id, name=name)
    db.add(group)
    db.flush()
    return group


def rename(db: Session, group: TrainingGroup, name: str) -> TrainingGroup:
    group.name = name
    db.flush()
    return group


def delete_group(db: Session, group: TrainingGroup) -> None:
    """Les appartenances partent par la cascade ORM, les liens séance et
    récurrence par `secondary` ; les inscriptions restent."""
    db.delete(group)
    db.flush()


def list_members(db: Session, training_group_id: int) -> list[PersonalProfile]:
    return list(
        db.scalars(
            select(PersonalProfile)
            .join(TrainingGroupMember, TrainingGroupMember.profile_id == PersonalProfile.id)
            .where(TrainingGroupMember.training_group_id == training_group_id)
            .order_by(PersonalProfile.last_name, PersonalProfile.first_name)
        )
    )


def list_groups_of_profile(db: Session, profile_id: int) -> list[TrainingGroup]:
    return list(
        db.scalars(
            select(TrainingGroup)
            .join(TrainingGroupMember, TrainingGroupMember.training_group_id == TrainingGroup.id)
            .where(TrainingGroupMember.profile_id == profile_id)
            .order_by(TrainingGroup.name)
        )
    )


def _find_member(db: Session, training_group_id: int, profile_id: int) -> TrainingGroupMember | None:
    return db.scalar(
        select(TrainingGroupMember).where(
            TrainingGroupMember.training_group_id == training_group_id,
            TrainingGroupMember.profile_id == profile_id,
        )
    )


def add_member(db: Session, *, training_group_id: int, profile_id: int) -> tuple[TrainingGroupMember, bool]:
    """Rend `(appartenance, créée)`. Idempotent sous concurrence par la contrainte
    d'unicité, sous point de reprise, comme `training_session_repository.add_participant`."""
    member = TrainingGroupMember(training_group_id=training_group_id, profile_id=profile_id)
    try:
        with db.begin_nested():
            db.add(member)
            db.flush()
    except IntegrityError:
        existing = _find_member(db, training_group_id, profile_id)
        if existing is None:  # pragma: no cover — une autre contrainte a cédé
            raise
        return existing, False
    return member, True


def remove_member(db: Session, *, training_group_id: int, profile_id: int) -> bool:
    member = _find_member(db, training_group_id, profile_id)
    if member is None:
        return False
    db.delete(member)
    db.flush()
    return True


def active_member_ids(db: Session, training_group_ids: list[int], *, on: date) -> set[int]:
    """Les profils membres d'au moins un de ces groupes et adhérents à `on` (FR-017)."""
    if not training_group_ids:
        return set()
    return set(
        db.scalars(
            select(TrainingGroupMember.profile_id)
            .join(PersonalProfile, PersonalProfile.id == TrainingGroupMember.profile_id)
            .where(
                TrainingGroupMember.training_group_id.in_(training_group_ids),
                or_(PersonalProfile.membership_ended_on.is_(None), PersonalProfile.membership_ended_on >= on),
            )
        )
    )


def delete_memberships_of_profile(db: Session, profile_id: int) -> int:
    """Retire les appartenances d'un profil purgé (#1158), avant le profil."""
    return db.execute(delete(TrainingGroupMember).where(TrainingGroupMember.profile_id == profile_id)).rowcount
