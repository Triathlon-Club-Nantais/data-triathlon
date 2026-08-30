"""Logique métier des déclarations de bénévolat (#751)."""
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.user import User
from app.models.volunteer_declaration import VolunteerDeclaration
from app.repositories import (
    admin_action_log_repository,
    user_repository,
    volunteer_declaration_repository,
)


def create_self(db: Session, *, user_id: int, title: str, description: str) -> VolunteerDeclaration:
    """Auto-déclaration : bénéficiaire et auteur sont le membre connecté,
    toujours créée « en attente » (FR-001)."""
    return volunteer_declaration_repository.create(
        db,
        title=title,
        description=description,
        beneficiary_user_id=user_id,
        author_user_id=user_id,
        status="en_attente",
    )


def list_for_self(db: Session, *, user_id: int) -> list[VolunteerDeclaration]:
    return volunteer_declaration_repository.list_for_beneficiary(db, user_id)


def _beneficiaire_ou_404(db: Session, beneficiary_user_id: int) -> User:
    beneficiaire = user_repository.get(db, beneficiary_user_id)
    if beneficiaire is None:
        raise NotFoundError("Membre introuvable.")
    return beneficiaire


def create_for_other(
    db: Session, *, admin_user_id: int, beneficiary_user_id: int, title: str, description: str
) -> VolunteerDeclaration:
    """Un admin déclare pour n'importe quel membre — validée d'office (FR-004)."""
    _beneficiaire_ou_404(db, beneficiary_user_id)

    declaration = volunteer_declaration_repository.create(
        db,
        title=title,
        description=description,
        beneficiary_user_id=beneficiary_user_id,
        author_user_id=admin_user_id,
        status="validee",
    )
    admin_action_log_repository.create(
        db,
        user_id=admin_user_id,
        action="volunteer_declaration.create_for_other",
        entity_type="volunteer_declaration",
        entity_id=declaration.id,
        payload={"beneficiary_user_id": beneficiary_user_id},
    )
    return declaration


def _declaration_ou_404(db: Session, declaration_id: int) -> VolunteerDeclaration:
    declaration = volunteer_declaration_repository.get(db, declaration_id)
    if declaration is None:
        raise NotFoundError("Déclaration introuvable.")
    return declaration


def validate(db: Session, *, admin_user_id: int, declaration_id: int) -> VolunteerDeclaration:
    """Fait passer une déclaration « en attente » à « validée » (FR-005),
    idempotent si déjà validée."""
    declaration = _declaration_ou_404(db, declaration_id)
    if declaration.status == "validee":
        return declaration

    mise_a_jour = volunteer_declaration_repository.set_status(db, declaration_id, "validee")
    admin_action_log_repository.create(
        db,
        user_id=admin_user_id,
        action="volunteer_declaration.validate",
        entity_type="volunteer_declaration",
        entity_id=declaration_id,
    )
    return mise_a_jour


def delete_self(db: Session, *, user_id: int, declaration_id: int) -> None:
    """L'auteur supprime sa propre déclaration, quel que soit son statut
    (FR-006). Refuse silencieusement (404 côté router) si l'appelant n'en
    est pas l'auteur (FR-007) — pas de fuite d'existence."""
    declaration = volunteer_declaration_repository.get(db, declaration_id)
    if declaration is None or declaration.author_user_id != user_id:
        raise NotFoundError("Déclaration introuvable.")
    volunteer_declaration_repository.delete(db, declaration_id)


def delete_any(db: Session, *, admin_user_id: int, declaration_id: int) -> None:
    """Un admin supprime la déclaration de n'importe quel membre (FR-006)."""
    _declaration_ou_404(db, declaration_id)
    volunteer_declaration_repository.delete(db, declaration_id)
    admin_action_log_repository.create(
        db,
        user_id=admin_user_id,
        action="volunteer_declaration.delete",
        entity_type="volunteer_declaration",
        entity_id=declaration_id,
    )


def list_all(db: Session) -> list[VolunteerDeclaration]:
    """Vue d'ensemble admin — tous les membres, tous les statuts (FR-010)."""
    return volunteer_declaration_repository.list_all(db)
