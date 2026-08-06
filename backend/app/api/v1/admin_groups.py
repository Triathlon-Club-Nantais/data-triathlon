"""Router d'administration des groupes (#197) — sept ressources, sept gardes.

Même patron qu'`admin_roles.py`, et délibérément **un fichier séparé** : le
module de #115 s'annonce comme « router d'administration des rôles », et y fondre
sept ressources de plus brouillerait un docstring qui vaut contrat.

Chaque route porte sa garde individuellement et nomme un **pouvoir** (FR-015).
Aucune n'est protégée par son préfixe : `admin.py` monte, sous le même
`/admin/`, le signalement anonyme du site public.

**Ce router n'intervient dans aucune décision d'accès.** Les groupes qu'il gère
n'accordent rien — c'est la borne de la v1, vérifiée par
`tests/test_auth/test_groups_grant_nothing.py`.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.permissions import P
from app.models.user import User
from app.schemas.admin import (
    GroupCreate,
    GroupDetailRead,
    GroupMemberAdd,
    GroupRead,
    GroupUpdate,
)
from app.services.auth import groups as group_service

router = APIRouter(tags=["admin"])


@router.get("/admin/groups", response_model=list[GroupRead])
def list_groups(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.GROUPS_READ)),
):
    """Les groupes du club, triés par slug, avec leur nombre de membres.

    Sans pagination, pour la raison exacte qui l'écarte sur `GET /admin/users` :
    les groupes d'un club se comptent sur les doigts.
    """
    return [group_service.group_view(db, group) for group in group_service.list_groups(db)]


@router.get("/admin/groups/{group_id}", response_model=GroupDetailRead)
def get_group(
    group_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.GROUPS_READ)),
):
    """Un groupe **et sa composition** — la ressource qui justifie l'objet entier.

    « Liste-moi les membres du Codir » n'est rendu proprement par aucune
    agrégation de rôles (FR-012).
    """
    return group_service.group_detail_view(
        db, group_service.get_group_or_404(db, group_id)
    )


@router.post("/admin/groups", response_model=GroupDetailRead, status_code=201)
def create_group(
    body: GroupCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.GROUPS_WRITE)),
):
    """Crée un groupe. Il naît **vide** — un groupe existe avant d'avoir des
    membres, et c'est ce qui le distingue d'un rôle.

    Rend le **détail**, comme `PATCH` et l'ajout d'un membre : les trois gestes
    qui portent sur un groupe précis rendent la même forme. Seule la liste en
    diffère, et c'est elle l'exception.
    """
    group = group_service.create_group(
        db,
        actor,
        slug=body.slug,
        name=body.name,
        description=body.description,
        organisation_id=body.organisation_id,
    )
    view = group_service.group_detail_view(db, group)
    db.commit()
    return view


@router.patch("/admin/groups/{group_id}", response_model=GroupDetailRead)
def update_group(
    group_id: int,
    body: GroupUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.GROUPS_WRITE)),
):
    """Renomme et redécrit. Le slug n'est pas dans le DTO : le soumettre rend
    **422**, jamais un renommage silencieux."""
    group = group_service.get_group_or_404(db, group_id)
    group_service.update_group(
        db, actor, group, name=body.name, description=body.description
    )
    view = group_service.group_detail_view(db, group)
    db.commit()
    return view


@router.delete("/admin/groups/{group_id}", status_code=204)
def delete_group(
    group_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.GROUPS_WRITE)),
):
    """Supprime un groupe **vide**. Peuplé, c'est un 409 qui nomme le nombre.

    Aucun droit n'est perdu à supprimer un groupe : ce qu'on protège est la
    **composition**, qu'aucune migration ne reconstitue.
    """
    group_service.delete_group(db, actor, group_service.get_group_or_404(db, group_id))
    db.commit()


@router.post(
    "/admin/groups/{group_id}/members", response_model=GroupDetailRead, status_code=201
)
def add_member(
    group_id: int,
    body: GroupMemberAdd,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.GROUPS_ASSIGN)),
):
    """Ajoute un membre. **Idempotent** — réajouter est un succès (FR-008)."""
    group = group_service.get_group_or_404(db, group_id)
    target = group_service.get_user_or_404(db, body.user_id)
    group_service.add_member(db, actor, group=group, user=target)
    view = group_service.group_detail_view(db, group)
    db.commit()
    return view


@router.delete("/admin/groups/{group_id}/members/{user_id}", status_code=204)
def remove_member(
    group_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.GROUPS_ASSIGN)),
):
    """Retire un membre. Idempotent, et **ne retire rien d'autre** (FR-009).

    Aucun invariant du dernier membre : un groupe peut être vidé entièrement.
    """
    group = group_service.get_group_or_404(db, group_id)
    target = group_service.get_user_or_404(db, user_id)
    group_service.remove_member(db, actor, group=group, user=target)
    db.commit()
