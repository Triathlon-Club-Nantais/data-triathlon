"""Groupes d'entraînement : constitution et appartenances (#1291, US1).

Générique (FR-015) ; la restriction aux jeunes vit dans la garde des routes."""
import logging

from sqlalchemy.orm import Session

from app.core.exceptions import DomainError, NotFoundError
from app.models.training_group import TrainingGroup
from app.models.user import User
from app.repositories import (
    profile_repository,
    training_group_repository,
    training_session_repository,
)
from app.services import profile_service, training_session_service

logger = logging.getLogger(__name__)


class InvalidGroupNameError(DomainError):
    status_code = 422
    message = "Le nom du groupe est obligatoire."


MAX_NAME_LENGTH = 80


class GroupNameTooLongError(DomainError):
    status_code = 422
    message = f"Le nom du groupe compte au plus {MAX_NAME_LENGTH} caractères."


class GroupNameTakenError(DomainError):
    status_code = 422
    message = "Un groupe porte déjà ce nom."


def get_group_or_404(db: Session, training_group_id: int) -> TrainingGroup:
    group = training_group_repository.get(db, training_group_id)
    if group is None:
        raise NotFoundError("Ce groupe n'existe pas.")
    return group


def list_group_views(db: Session) -> list[dict]:
    return [
        {"id": group.id, "name": group.name, "member_count": member_count}
        for group, member_count in training_group_repository.list_with_member_counts(db)
    ]


def group_detail_view(db: Session, group: TrainingGroup) -> dict:
    return {
        "id": group.id,
        "name": group.name,
        "members": [
            profile_service.profile_view(profile)
            for profile in training_group_repository.list_members(db, group.id)
        ],
    }


def _valid_name(db: Session, organisation_id: int, name: str, group: TrainingGroup | None = None) -> str:
    name = name.strip()
    if not name:
        raise InvalidGroupNameError()
    if len(name) > MAX_NAME_LENGTH:
        raise GroupNameTooLongError()
    existing = training_group_repository.find_by_name(db, organisation_id=organisation_id, name=name)
    if existing is not None and existing is not group:
        raise GroupNameTakenError()
    return name


def create_group(db: Session, actor: User, *, name: str) -> TrainingGroup:
    organisation_id = profile_service.default_organisation_id(db)
    group = training_group_repository.create(
        db, organisation_id=organisation_id, name=_valid_name(db, organisation_id, name)
    )
    logger.info("Training group created: actor=%s group=%s", actor.id, group.id)
    return group


def rename_group(db: Session, actor: User, group: TrainingGroup, *, name: str) -> TrainingGroup:
    training_group_repository.rename(db, group, _valid_name(db, group.organisation_id, name, group))
    logger.info("Training group renamed: actor=%s group=%s", actor.id, group.id)
    return group


def delete_group(db: Session, actor: User, group: TrainingGroup) -> None:
    group_id = group.id
    # Ses membres restent inscrits aux séances existantes (spec, Edge Cases).
    training_session_repository.make_group_enrolments_manual(db, group_id)
    training_group_repository.delete_group(db, group)
    logger.info("Training group deleted: actor=%s group=%s", actor.id, group_id)


def add_member(db: Session, actor: User, group: TrainingGroup, *, profile_id: int) -> None:
    if profile_repository.get(db, profile_id) is None:
        raise NotFoundError("Ce profil n'existe pas.")
    _, created = training_group_repository.add_member(db, training_group_id=group.id, profile_id=profile_id)
    training_session_service.sync_member_of_group(db, group, profile_id)
    logger.info("Group member added: actor=%s group=%s profile=%s new=%s", actor.id, group.id, profile_id, created)


def remove_member(db: Session, actor: User, group: TrainingGroup, *, profile_id: int) -> None:
    training_group_repository.remove_member(db, training_group_id=group.id, profile_id=profile_id)
    training_session_service.sync_member_of_group(db, group, profile_id)
    logger.info("Group member removed: actor=%s group=%s profile=%s", actor.id, group.id, profile_id)
