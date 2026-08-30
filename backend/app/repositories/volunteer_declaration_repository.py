"""Accès données pour VolunteerDeclaration — seule couche qui touche la Session (Principe II)."""
from sqlalchemy.orm import Session

from app.models.volunteer_declaration import VolunteerDeclaration


def create(
    db: Session,
    *,
    title: str,
    description: str,
    beneficiary_user_id: int,
    author_user_id: int,
    status: str,
) -> VolunteerDeclaration:
    declaration = VolunteerDeclaration(
        title=title,
        description=description,
        beneficiary_user_id=beneficiary_user_id,
        author_user_id=author_user_id,
        status=status,
    )
    db.add(declaration)
    db.flush()
    return declaration


def get(db: Session, declaration_id: int) -> VolunteerDeclaration | None:
    return db.get(VolunteerDeclaration, declaration_id)


def list_for_beneficiary(db: Session, beneficiary_user_id: int) -> list[VolunteerDeclaration]:
    return (
        db.query(VolunteerDeclaration)
        .filter(VolunteerDeclaration.beneficiary_user_id == beneficiary_user_id)
        .order_by(VolunteerDeclaration.created_at.desc())
        .all()
    )


def list_all(db: Session) -> list[VolunteerDeclaration]:
    return db.query(VolunteerDeclaration).order_by(VolunteerDeclaration.created_at.desc()).all()


def delete(db: Session, declaration_id: int) -> None:
    declaration = db.get(VolunteerDeclaration, declaration_id)
    if declaration is not None:
        db.delete(declaration)
        db.flush()


def set_status(db: Session, declaration_id: int, status: str) -> VolunteerDeclaration | None:
    declaration = db.get(VolunteerDeclaration, declaration_id)
    if declaration is None:
        return None
    declaration.status = status
    db.flush()
    return declaration
