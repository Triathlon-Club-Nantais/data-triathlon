"""Router public authentifié : self-service des déclarations de bénévolat (#751).

Le chemin dit qui peut appeler : cette ressource ne vit jamais sous `/admin`
— toutes ses routes exigent une session (`current_user`, 401 sinon), aucune
n'exige de pouvoir RBAC particulier. La consultation d'ensemble et
l'instruction admin vivent dans `admin_volunteer_declarations.py`.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.volunteer_declaration import VolunteerDeclarationCreate, VolunteerDeclarationOut
from app.services import volunteer_declaration_service

router = APIRouter(tags=["volunteer-declarations"])


@router.post("/volunteer-declarations", status_code=201, response_model=VolunteerDeclarationOut)
def creer_pour_soi_meme(
    body: VolunteerDeclarationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    declaration = volunteer_declaration_service.create_self(
        db, user_id=user.id, title=body.title, description=body.description
    )
    db.commit()
    db.refresh(declaration)
    return declaration


@router.get("/volunteer-declarations", response_model=list[VolunteerDeclarationOut])
def lister_les_siennes(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    return volunteer_declaration_service.list_for_self(db, user_id=user.id)


@router.delete("/volunteer-declarations/{declaration_id}", status_code=204)
def supprimer_la_sienne(
    declaration_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    volunteer_declaration_service.delete_self(db, user_id=user.id, declaration_id=declaration_id)
    db.commit()
