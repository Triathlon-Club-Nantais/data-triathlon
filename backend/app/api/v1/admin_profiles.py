"""Router d'administration des profils individuels (#867, epic #863).

Cinq ressources, chacune gardée individuellement par `jeunes:read` ou
`jeunes:write` (FR-007 de spec.md) — jamais par préfixe, patron
`admin_groups.py`. Le schéma est générique (research.md D1), la restriction
« jeunes uniquement » pour cette itération vit **entièrement** ici, dans la
garde, et nulle part dans `profile_service`/`profile_repository`.

Le club vise le seul de l'installation (`role_repository.default_organisation`),
comme l'attribution d'un rôle et la création d'un groupe : `ProfileCreate` ne
porte pas de champ `organisation_id`, une seule organisation existant à ce
jour (research.md, assumptions de spec.md).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.permissions import P
from app.models.user import User
from app.schemas.profile import (
    ProfileCreate,
    ProfileDetailRead,
    ProfileLogEntryCreate,
    ProfileRead,
    ProfileUpdate,
)
from app.services import profile_service

router = APIRouter(tags=["admin"])


@router.get("/admin/profiles", response_model=list[ProfileRead])
def list_profiles(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.JEUNES_READ)),
):
    return [profile_service.profile_view(p) for p in profile_service.list_profiles(db)]


@router.get("/admin/profiles/{profile_id}", response_model=ProfileDetailRead)
def get_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.JEUNES_READ)),
):
    profile = profile_service.get_profile_or_404(db, profile_id)
    return profile_service.profile_detail_view(db, profile)


@router.post("/admin/profiles", response_model=ProfileDetailRead, status_code=201)
def create_profile(
    body: ProfileCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.JEUNES_WRITE)),
):
    profile = profile_service.create_profile(
        db,
        actor,
        first_name=body.first_name,
        last_name=body.last_name,
        birth_date=body.birth_date,
        emergency_contact=body.emergency_contact,
        notes=body.notes,
    )
    view = profile_service.profile_detail_view(db, profile)
    db.commit()
    return view


@router.patch("/admin/profiles/{profile_id}", response_model=ProfileDetailRead)
def update_profile(
    profile_id: int,
    body: ProfileUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.JEUNES_WRITE)),
):
    profile = profile_service.get_profile_or_404(db, profile_id)
    profile_service.update_profile(
        db,
        actor,
        profile,
        first_name=body.first_name,
        last_name=body.last_name,
        birth_date=body.birth_date,
        emergency_contact=body.emergency_contact,
        notes=body.notes,
    )
    view = profile_service.profile_detail_view(db, profile)
    db.commit()
    return view


@router.post(
    "/admin/profiles/{profile_id}/log-entries",
    response_model=ProfileDetailRead,
    status_code=201,
)
def add_log_entry(
    profile_id: int,
    body: ProfileLogEntryCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.JEUNES_WRITE)),
):
    """Rend le détail complet, pas seulement l'entrée créée (patron
    `add_member` de `admin_groups.py`) : le front n'a besoin que d'un seul
    appel après l'ajout."""
    profile = profile_service.get_profile_or_404(db, profile_id)
    profile_service.add_log_entry(
        db, actor, profile, text=body.text, entry_date=body.entry_date
    )
    view = profile_service.profile_detail_view(db, profile)
    db.commit()
    return view
