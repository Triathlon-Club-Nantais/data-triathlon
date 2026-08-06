"""La décision d'accès : qui porte quoi, et l'organisation garde-t-elle un admin.

**Elle relit la base à chaque appel, et ne met rien en cache** (FR-016). C'est
ce qui rend l'édition d'un rôle effective à la **requête suivante** de tous ses
porteurs, sans reconnexion — et ce qu'un cache, si petit soit-il, rendrait faux :
« c'est effectif tout de suite » deviendrait « au bout d'un moment ».
"""
import logging
from contextlib import contextmanager

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import permissions
from app.core.exceptions import DomainError, NotFoundError
from app.core.permissions import Permission
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.user import User
from app.repositories import role_repository, user_repository, user_role_repository

logger = logging.getLogger(__name__)


class UnknownPermissionError(DomainError):
    """Un code **soumis** n'est pas de l'inventaire."""

    status_code = 422
    message = "Ce pouvoir n'existe pas."


class SlugTakenError(DomainError):
    status_code = 409
    message = "Un rôle porte déjà cet identifiant dans cette portée."


class SystemRoleError(DomainError):
    status_code = 409
    message = "Ce rôle est livré avec l'application et ne peut pas être supprimé."


class RoleInUseError(DomainError):
    status_code = 409
    message = "Ce rôle est encore porté. Retirez-le d'abord."


class RoleOutOfScopeError(DomainError):
    status_code = 422
    message = "Ce rôle est propre à une autre organisation."


class PrivilegeEscalationError(DomainError):
    """Nul n'accorde un pouvoir qu'il ne porte pas (FR-011).

    Le message ne nomme **pas** le pouvoir en cause, au même titre que le 403 de
    la garde (FR-019).
    """

    status_code = 403
    message = "Vous ne pouvez pas accorder un pouvoir que vous ne portez pas."


class LastAdministratorError(DomainError):
    """L'état d'arrivée laisserait l'organisation sans administrateur (FR-032).

    409 et non 403 : l'appelant *est* administrateur, sa requête est bien
    formée, c'est le **résultat** qui est interdit.
    """

    status_code = 409
    message = "Cette opération laisserait l'installation sans aucun administrateur."


def _is_superuser(db: Session, user: User, organisation_id: int | None) -> bool:
    return any(
        attribution.role.is_superuser
        for attribution in user_role_repository.list_for_user(
            db, user.id, organisation_id=organisation_id
        )
    )


def effective_permissions(
    db: Session, user: User, *, organisation_id: int | None = None
) -> frozenset[str]:
    """Les codes que cet utilisateur porte réellement — **union** de ses rôles.

    Deux bornes, et chacune est une décision :

    - **Un superutilisateur porte le catalogue**, ni plus ni moins. C'est cette
      égalité qui rend un code périmé retirable par tout le monde : s'il portait
      « tout », y compris l'inconnu, la non-amplification ne pourrait jamais
      autoriser sa purge (FR-011).
    - **Un code absent de l'inventaire n'accorde rien** (FR-042). Un pouvoir
      retiré par une livraison laisse des lignes inertes ; elles ne cassent rien
      et ne donnent rien.

    Un compte désactivé ne porte rien : la décision est aussi appelée hors HTTP
    (CLI), où aucune session ne l'a filtré en amont.
    """
    if not user.is_active:
        return frozenset()
    if _is_superuser(db, user, organisation_id):
        return permissions.CODES
    return frozenset(
        lien.permission_code
        for attribution in user_role_repository.list_for_user(
            db, user.id, organisation_id=organisation_id
        )
        for lien in attribution.role.permissions
        if permissions.is_known(lien.permission_code)
    )


def has_permission(
    db: Session,
    user: User,
    code: Permission | str,
    *,
    organisation_id: int | None = None,
) -> bool:
    """Cet utilisateur porte-t-il ce pouvoir **précis** ?

    La question est posée dans ce sens et jamais « quels codes porte-t-il ? » :
    c'est ce qui rend les lignes périmées inertes par construction.

    Le court-circuit superutilisateur est **antérieur** à l'inventaire, et c'est
    la promesse de FR-014 : un pouvoir livré demain est franchi demain, sans
    migration ni recochage — même si le catalogue de ce processus l'ignore
    encore.
    """
    if not user.is_active:
        return False
    if _is_superuser(db, user, organisation_id):
        return True
    return str(code) in effective_permissions(
        db, user, organisation_id=organisation_id
    )


def count_active_superusers(db: Session, organisation_id: int) -> int:
    """Combien de comptes actifs franchissent tout dans cette organisation."""
    return user_role_repository.count_active_superusers(db, organisation_id)


def is_superuser(db: Session, user: User, *, organisation_id: int | None = None) -> bool:
    """Ce compte franchit-il tout ? `is_superuser` ne se compose pas (FR-010)."""
    return user.is_active and _is_superuser(db, user, organisation_id)


# --- Composition des rôles (US3) --------------------------------------------


def _codes(role: Role) -> tuple[list[str], list[str]]:
    """Les codes du rôle, séparés en `(de l'inventaire, périmés)`."""
    portes = sorted(lien.permission_code for lien in role.permissions)
    connus = [code for code in portes if permissions.is_known(code)]
    perimes = [code for code in portes if not permissions.is_known(code)]
    return connus, perimes


def role_view(db: Session, role: Role) -> dict:
    """La forme rendue par l'API, `contracts/admin-api.md`."""
    connus, perimes = _codes(role)
    return {
        "id": role.id,
        "organisation_id": role.organisation_id,
        "slug": role.slug,
        "name": role.name,
        "description": role.description,
        "is_system": role.is_system,
        "is_superuser": role.is_superuser,
        "permissions": connus,
        "stale_permissions": perimes,
        "holders": role_repository.count_holders(db, role.id),
    }


def _valider_les_codes_soumis(codes: list[str]) -> None:
    """Tout code **soumis** doit être de l'inventaire — 422 sinon.

    C'est le seul écrivain, et c'est pourquoi une clé étrangère ne protégerait
    rien : il valide déjà contre le catalogue.
    """
    inconnus = sorted({code for code in codes if not permissions.is_known(code)})
    if inconnus:
        raise UnknownPermissionError(
            f"Pouvoir inconnu : {', '.join(inconnus)}."
        )


def assert_may_grant(
    db: Session, actor: User, codes: set[str], *, organisation_id: int | None = None
) -> None:
    """FR-011 — nul n'accorde ni ne retire un pouvoir qu'il ne porte pas lui-même.

    **L'intersection avec l'inventaire n'est pas une précaution, c'est la
    condition de réversibilité.** Sans elle, un code périmé — que personne ne
    porte, pas même un superutilisateur dont les pouvoirs effectifs *sont*
    l'inventaire — ne serait retirable par personne : le rôle qui en traîne un
    deviendrait immodifiable, et `is_system` ou attribué, indélébile. Un
    nettoyage de code ordinaire suffirait à geler un rôle définitivement.
    """
    vises = codes & permissions.CODES
    manquants = vises - effective_permissions(
        db, actor, organisation_id=organisation_id
    )
    if manquants:
        logger.warning(
            "Privilege escalation refused: user %s lacks %s",
            actor.id,
            ",".join(sorted(manquants)),
        )
        raise PrivilegeEscalationError()


def assert_may_set_superuser(db: Session, actor: User, *, organisation_id=None) -> None:
    """FR-010 — `is_superuser` n'est posable **ni retirable** que par qui le porte."""
    if not is_superuser(db, actor, organisation_id=organisation_id):
        raise PrivilegeEscalationError(
            "Seul un administrateur peut poser ou retirer ce caractère."
        )


def assert_role_assignable_in(db: Session, role: Role, organisation_id: int) -> None:
    """FR-008 — un rôle propre à A n'est pas attribuable dans B.

    Contrôle de **service** : la règle croise deux tables, aucun SQL portable ne
    l'exprime. Dit ici plutôt que de laisser croire à une contrainte.
    """
    if role.organisation_id is not None and role.organisation_id != organisation_id:
        raise RoleOutOfScopeError()


def assert_organisation_keeps_an_admin(db: Session, organisation_id: int) -> None:
    """L'invariant, jugé sur l'**état d'arrivée** — après `flush`, avant `commit`.

    On ne garde pas les *chemins* : retirer une attribution, supprimer un rôle,
    décocher `is_superuser`, désactiver un compte — et chaque nouvelle façon
    d'éditer les droits en ouvrira une cinquième. Une seule définition, et le
    cinquième chemin ajouté demain est couvert sans qu'on y pense (FR-032).

    À n'appeler **que** sur une organisation qui en avait un avant l'opération :
    voir `administrateurs_preserves`.
    """
    if count_active_superusers(db, organisation_id) == 0:
        raise LastAdministratorError()


@contextmanager
def administrateurs_preserves(db: Session, organisation_id: int | None = None):
    """Encadre une opération et refuse qu'elle **fasse perdre** le dernier admin.

    La nuance « faire perdre » n'est pas cosmétique : sur une installation neuve,
    personne n'est encore administrateur. Un invariant qui jugerait le seul état
    d'arrivée y refuserait *toute* opération — y compris celles qui n'ont aucun
    rapport avec les superutilisateurs — et l'installation serait figée avant
    même d'avoir servi. On compare donc avant et après.

    `organisation_id` à `None` couvre **toutes** les organisations : un rôle
    global est superutilisateur partout, le décocher ou le supprimer peut
    verrouiller un club autre que celui d'où l'on agit.
    """
    cibles = (
        [organisation_id]
        if organisation_id is not None
        else [ligne.id for ligne in role_repository.list_organisations(db)]
    )
    avant = {cible: count_active_superusers(db, cible) for cible in cibles}
    yield
    db.flush()
    for cible, compte in avant.items():
        if compte > 0:
            assert_organisation_keeps_an_admin(db, cible)


def create_role(
    db: Session,
    actor: User,
    *,
    slug: str,
    name: str,
    description: str = "",
    organisation_id: int | None = None,
    codes: list[str],
    superuser: bool = False,
) -> Role:
    _valider_les_codes_soumis(codes)
    assert_may_grant(db, actor, set(codes))
    if superuser:
        assert_may_set_superuser(db, actor)
    if role_repository.find_in_scope(
        db, slug=slug, organisation_id=organisation_id
    ) is not None:
        raise SlugTakenError()

    try:
        # **Le point de reprise entoure l'écriture**, et non un `flush`
        # d'après-coup : `role_repository.create` flushe lui-même, donc
        # l'`IntegrityError` était levée *avant* d'entrer dans ce `try` et
        # remontait nue — 500 au lieu du 409 promis. C'est l'index partiel
        # `WHERE organisation_id IS NULL` qui tranche ce que la lecture préalable
        # laisse passer sous concurrence, et il faut donc l'attraper là où il
        # parle. Le `SAVEPOINT` rattrape sans perdre la transaction, là où le
        # `db.rollback()` d'avant aurait emporté tout ce qui précédait.
        with db.begin_nested():
            role = role_repository.create(
                db,
                slug=slug,
                name=name,
                description=description,
                organisation_id=organisation_id,
                is_superuser=superuser,
            )
    except IntegrityError as collision:
        raise SlugTakenError() from collision

    for code in dict.fromkeys(codes):
        role.permissions.append(RolePermission(permission_code=code))
    db.flush()

    logger.info(
        "Role created: actor=%s role=%s codes=%s superuser=%s",
        actor.id,
        role.slug,
        ",".join(sorted(codes)) or "-",
        superuser,
    )
    return role


def update_role(
    db: Session,
    actor: User,
    role: Role,
    *,
    name: str | None = None,
    description: str | None = None,
    codes: list[str] | None = None,
    superuser: bool | None = None,
) -> Role:
    """Modifie un rôle. `codes` **remplace** l'ensemble des pouvoirs.

    Un rôle `is_system` est parfaitement modifiable : livré ne veut pas dire figé
    (FR-006). Seule sa suppression est refusée.
    """
    if codes is not None:
        _valider_les_codes_soumis(codes)
        avant = {lien.permission_code for lien in role.permissions}
        # La différence **symétrique** : ajouter et retirer relèvent de la même
        # règle. Un éditeur qui pourrait désarmer un rôle sans en porter les
        # pouvoirs contournerait la non-amplification par la sortie.
        assert_may_grant(db, actor, avant ^ set(codes))

    with administrateurs_preserves(db, role.organisation_id):
        if superuser is not None and superuser != role.is_superuser:
            assert_may_set_superuser(db, actor)
            role.is_superuser = superuser

        if name is not None:
            role.name = name
        if description is not None:
            role.description = description
        if codes is not None:
            role.permissions.clear()
            db.flush()
            for code in dict.fromkeys(codes):
                role.permissions.append(RolePermission(permission_code=code))

    logger.info(
        "Role updated: actor=%s role=%s codes=%s superuser=%s",
        actor.id,
        role.slug,
        ",".join(sorted(codes)) if codes is not None else "unchanged",
        role.is_superuser,
    )
    return role


def delete_role(db: Session, actor: User, role: Role) -> None:
    if role.is_system:
        raise SystemRoleError()
    porteurs = role_repository.count_holders(db, role.id)
    if porteurs:
        # Le nombre est **dans le message** : « conflit » ne se corrige pas.
        raise RoleInUseError(
            f"Ce rôle est porté par {porteurs} utilisateur"
            f"{'s' if porteurs > 1 else ''}. Retirez-le d'abord."
        )
    with administrateurs_preserves(db, role.organisation_id):
        logger.info("Role deleted: actor=%s role=%s", actor.id, role.slug)
        role_repository.delete(db, role)


def grant_role(
    db: Session, actor: User, *, user: User, role: Role, organisation_id: int
) -> None:
    """Attribue un rôle. Idempotent (FR-012)."""
    assert_role_assignable_in(db, role, organisation_id)
    connus, _ = _codes(role)
    assert_may_grant(db, actor, set(connus))

    _, cree = user_role_repository.grant(
        db, user_id=user.id, role_id=role.id, organisation_id=organisation_id
    )
    db.flush()
    logger.info(
        "Role granted: actor=%s target_user=%s role=%s new=%s",
        actor.id,
        user.id,
        role.slug,
        cree,
    )


def revoke_role(
    db: Session, actor: User, *, user: User, role: Role, organisation_id: int
) -> None:
    """Retire un rôle. Idempotent, et **soumis à l'invariant** (FR-032)."""
    connus, _ = _codes(role)
    assert_may_grant(db, actor, set(connus))

    with administrateurs_preserves(db, organisation_id):
        user_role_repository.revoke(
            db, user_id=user.id, role_id=role.id, organisation_id=organisation_id
        )
    logger.info(
        "Role revoked: actor=%s target_user=%s role=%s", actor.id, user.id, role.slug
    )


def user_view(db: Session, user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "is_active": user.is_active,
        "roles": [
            {
                "id": attribution.role.id,
                "slug": attribution.role.slug,
                "name": attribution.role.name,
                "organisation_id": attribution.organisation_id,
            }
            for attribution in user_role_repository.list_for_user(db, user.id)
        ],
        "created_at": user.created_at,
    }


def get_role_or_404(db: Session, role_id: int) -> Role:
    role = role_repository.get(db, role_id)
    if role is None:
        raise NotFoundError("Ce rôle n'existe pas.")
    return role


def get_user_or_404(db: Session, user_id: int) -> User:
    user = user_repository.get(db, user_id)
    if user is None:
        raise NotFoundError("Cet utilisateur n'existe pas.")
    return user
