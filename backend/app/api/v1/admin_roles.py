"""Router d'administration des rôles (#115) — sept ressources, sept gardes.

**Chacune porte sa garde individuellement, et nomme un pouvoir, jamais un rôle**
(FR-017, FR-018). Aucune n'est protégée par son préfixe : `admin.py` monte, sous
le même `/admin/`, le signalement anonyme du site public.

Couche mince : validation, délégation à `services/auth/authorization.py`,
traduction en HTTP. **Aucune écriture directe** dans `roles`, `role_permissions`
ou `user_roles` — un méta-test AST le vérifie (FR-031), parce que c'est
l'invariant qui se perd à la route suivante et ne se rattrape pas après coup.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core import permissions
from app.core.database import get_db
from app.core.permissions import P
from app.models.user import User
from app.repositories import role_repository
from app.schemas.admin import (
    AdminUserRead,
    PermissionGroupRead,
    PermissionRead,
    RoleAssign,
    RoleCreate,
    RoleRead,
    RoleUpdate,
)
from app.schemas.ids import DbId
from app.services import not_found
from app.services.auth import authorization

router = APIRouter(tags=["admin"])


@router.get("/admin/permissions", response_model=list[PermissionGroupRead])
def list_permissions(_: User = Depends(require_permission(P.ROLES_READ))):
    """L'inventaire de ce que l'application sait vérifier. **Servi depuis le code.**

    C'est ce qui garantit qu'un pouvoir livré aujourd'hui est proposé
    aujourd'hui, sans migration (FR-002, FR-014).

    Exige `roles:read`, et ce n'est pas une question de secret — les codes vivent
    dans un dépôt public. C'est qu'il n'a **pas d'autre lecteur** : son seul
    usage est de composer un rôle. Qui veut connaître *ses* pouvoirs lit
    `GET /auth/me`, qui n'exige rien.
    """
    return [
        PermissionGroupRead(
            feature=group.feature,
            permissions=[
                PermissionRead(
                    code=permission.code,
                    label=permission.label,
                    description=permission.description,
                )
                for permission in group.permissions
            ],
        )
        for group in permissions.grouped_by_feature()
    ]


@router.get("/admin/roles", response_model=list[RoleRead])
def list_roles(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.ROLES_READ)),
):
    roles = role_repository.list_all(db)
    holders = role_repository.count_holders_by_role(db, [role.id for role in roles])
    return [
        authorization.role_view(db, role, holders=holders.get(role.id, 0))
        for role in roles
    ]


@router.get("/admin/roles/{role_id}", response_model=RoleRead)
def get_role(
    role_id: DbId,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.ROLES_READ)),
):
    return authorization.role_view(db, authorization.get_role_or_404(db, role_id))


@router.post("/admin/roles", response_model=RoleRead, status_code=201)
def create_role(
    body: RoleCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.ROLES_WRITE)),
):
    """Compose un rôle. C'est ici que la **non-amplification** mord (FR-011).

    Sans elle, `roles:write` équivaudrait à `root` : quiconque édite les rôles se
    fabriquerait en trois clics celui qui peut tout.
    """
    role = authorization.create_role(
        db,
        actor,
        slug=body.slug,
        name=body.name,
        description=body.description,
        organisation_id=body.organisation_id,
        codes=body.permissions,
        superuser=body.is_superuser,
    )
    view = authorization.role_view(db, role)
    db.commit()
    return view


@router.patch("/admin/roles/{role_id}", response_model=RoleRead)
def update_role(
    role_id: DbId,
    body: RoleUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.ROLES_WRITE)),
):
    """Recompose un rôle. `permissions` **remplace** l'ensemble.

    Le changement s'applique à la **requête suivante** de tous les porteurs, sans
    reconnexion (FR-016) — leurs sessions restent valides : retirer un pouvoir
    n'est pas déconnecter quelqu'un.
    """
    role = authorization.get_role_or_404(db, role_id)
    authorization.update_role(
        db,
        actor,
        role,
        name=body.name,
        description=body.description,
        codes=body.permissions,
        superuser=body.is_superuser,
    )
    view = authorization.role_view(db, role)
    db.commit()
    return view


@router.delete("/admin/roles/{role_id}", status_code=204)
def delete_role(
    role_id: DbId,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.ROLES_WRITE)),
):
    """Supprime un rôle. **Pas de cascade** : dépouiller silencieusement trois
    personnes est exactement ce qu'on rend explicite par un 409 (FR-007)."""
    authorization.delete_role(db, actor, authorization.get_role_or_404(db, role_id))
    db.commit()


@router.get("/admin/users", response_model=list[AdminUserRead])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.USERS_READ)),
):
    return authorization.users_view(db)


@router.post("/admin/users/{user_id}/roles", response_model=AdminUserRead, status_code=201)
def grant_role(
    user_id: DbId,
    body: RoleAssign,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.ROLES_ASSIGN)),
):
    """Attribue un rôle. **Idempotent** — réattribuer est un succès (FR-012)."""
    target = not_found.user_or_404(db, user_id)
    role = authorization.get_role_or_404(db, body.role_id)
    organisation_id = body.organisation_id or _default_organisation_id(db)
    authorization.grant_role(
        db, actor, user=target, role=role, organisation_id=organisation_id
    )
    view = authorization.user_view(db, target)
    db.commit()
    return view


@router.delete("/admin/users/{user_id}/roles/{role_id}", status_code=204)
def revoke_role(
    user_id: DbId,
    role_id: DbId,
    organisation_id: DbId | None = None,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.ROLES_ASSIGN)),
):
    """Retire un rôle. Idempotent, et refusé si l'organisation y perdrait son
    dernier administrateur actif — **409**, l'appelant étant bien administrateur
    et sa requête bien formée : c'est le résultat qui est interdit."""
    target = not_found.user_or_404(db, user_id)
    role = authorization.get_role_or_404(db, role_id)
    authorization.revoke_role(
        db,
        actor,
        user=target,
        role=role,
        organisation_id=organisation_id or _default_organisation_id(db),
    )
    db.commit()


def _default_organisation_id(db: Session) -> int:
    """Le seul club en base. L'option existe parce que le modèle porte
    l'organisation ; elle n'a qu'une valeur possible tant qu'un second club
    n'est pas créé."""
    return authorization.existing_organisation(db, None)
