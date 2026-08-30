"""Router admin des déclarations de bénévolat (#751) — création pour un tiers,
validation, suppression et vue d'ensemble. Le self-service vit dans
`volunteer_declarations.py`, un router distinct (« le chemin dit qui peut
appeler »).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.permissions import P
from app.models.user import User
from app.models.volunteer_declaration import VolunteerDeclaration
from app.schemas.volunteer_declaration import (
    AdminVolunteerDeclarationCreate,
    AdminVolunteerDeclarationOut,
)
from app.services import volunteer_declaration_service

router = APIRouter(tags=["admin-volunteer-declarations"])


def _to_admin_out(declaration: VolunteerDeclaration) -> AdminVolunteerDeclarationOut:
    return AdminVolunteerDeclarationOut(
        id=declaration.id,
        title=declaration.title,
        description=declaration.description,
        status=declaration.status,
        beneficiary_user_id=declaration.beneficiary_user_id,
        author_user_id=declaration.author_user_id,
        created_at=declaration.created_at,
        beneficiary_display_name=declaration.beneficiary.display_name,
        beneficiary_email=declaration.beneficiary.email,
    )


@router.post(
    "/admin/volunteer-declarations", status_code=201, response_model=AdminVolunteerDeclarationOut
)
def creer_pour_un_tiers(
    body: AdminVolunteerDeclarationCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(P.BENEVOLAT_MANAGE)),
):
    declaration = volunteer_declaration_service.create_for_other(
        db,
        admin_user_id=admin.id,
        beneficiary_user_id=body.beneficiary_user_id,
        title=body.title,
        description=body.description,
    )
    db.commit()
    db.refresh(declaration)
    return _to_admin_out(declaration)


@router.get("/admin/volunteer-declarations", response_model=list[AdminVolunteerDeclarationOut])
def lister_toutes_les_declarations(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.BENEVOLAT_READ)),
):
    return [_to_admin_out(d) for d in volunteer_declaration_service.list_all(db)]


@router.post(
    "/admin/volunteer-declarations/{declaration_id}/validate",
    response_model=AdminVolunteerDeclarationOut,
)
def valider(
    declaration_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(P.BENEVOLAT_MANAGE)),
):
    declaration = volunteer_declaration_service.validate(
        db, admin_user_id=admin.id, declaration_id=declaration_id
    )
    db.commit()
    db.refresh(declaration)
    return _to_admin_out(declaration)


@router.delete("/admin/volunteer-declarations/{declaration_id}", status_code=204)
def supprimer(
    declaration_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(P.BENEVOLAT_MANAGE)),
):
    volunteer_declaration_service.delete_any(
        db, admin_user_id=admin.id, declaration_id=declaration_id
    )
    db.commit()
