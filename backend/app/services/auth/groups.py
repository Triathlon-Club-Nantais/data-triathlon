"""Les groupes d'appartenance : composition et members (#197).

**Ce module est délibérément séparé d'`authorization.py`**, et ce n'est pas une
question de goût. AC6 exige qu'« aucune décision d'accès ne consulte les
groupes », et un test ne sait pas lire une intention. Deux modules distincts
rendent l'énoncé mécanique : ni `api/deps.py` ni `services/auth/authorization.py`
ne nomment `Group`, `UserGroup` ou `group_repository` —
`tests/test_auth/test_groups_grant_nothing.py` le vérifie par lecture d'AST.

Fondues dans `authorization.py`, les deux responsabilités ne seraient plus
séparables par aucun outil, et la borne de la v1 retomberait sur la vigilance du
relecteur — précisément ce que #115 a refusé pour la non-amplification.

**Trois règles de #115 sont absentes, et leur absence est le sujet** : pas de
non-amplification (il n'y a aucun pouvoir à amplifier), pas d'invariant du
dernier membre (vider un groupe ne verrouille personne dehors), pas de caractère
d'administration (un groupe n'accorde rien).
"""
import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError, NotFoundError
from app.models.group import Group
from app.models.user import User
from app.repositories import group_repository, role_repository, user_repository

logger = logging.getLogger(__name__)


class GroupSlugTakenError(DomainError):
    status_code = 409
    message = "Un groupe porte déjà cet identifiant dans ce club."


class GroupInUseError(DomainError):
    """La suppression d'un groupe encore peuplé (FR-011).

    409 et non 403 : l'appelant a bien le pouvoir, sa requête est bien formée,
    c'est le **résultat** qui est interdit. Aucun droit n'est pourtant perdu à
    supprimer un groupe — ce qu'on protège est la **composition**, qu'aucune
    migration ne reconstitue et qu'aucun autre système ne détient.
    """

    status_code = 409
    message = "Ce groupe compte encore des membres. Retirez-les d'abord."


class NoOrganisationError(DomainError):
    status_code = 422
    message = "Aucune organisation n'existe."


def get_group_or_404(db: Session, group_id: int) -> Group:
    group = group_repository.get(db, group_id)
    if group is None:
        raise NotFoundError("Ce groupe n'existe pas.")
    return group


def get_user_or_404(db: Session, user_id: int) -> User:
    user = user_repository.get(db, user_id)
    if user is None:
        raise NotFoundError("Cet utilisateur n'existe pas.")
    return user


def group_view(db: Session, group: Group) -> dict:
    """La forme rendue par la liste, `contracts/admin-groups-api.md`."""
    return {
        "id": group.id,
        "organisation_id": group.organisation_id,
        "slug": group.slug,
        "name": group.name,
        "description": group.description,
        "member_count": group_repository.count_members(db, group.id),
        "created_at": group.created_at,
    }


def group_detail_view(db: Session, group: Group) -> dict:
    """La forme rendue par le détail : le groupe **et sa composition** (FR-012)."""
    return group_view(db, group) | {
        "members": [
            {
                "user_id": membership.user.id,
                "email": membership.user.email,
                "display_name": membership.user.display_name,
                "is_active": membership.user.is_active,
                "joined_at": membership.joined_at,
            }
            for membership in group_repository.list_members(db, group.id)
        ]
    }


def list_groups(db: Session) -> list[Group]:
    """Tous les groupes, triés par slug. L'installation n'a qu'un club."""
    return group_repository.list_all(db)


def create_group(
    db: Session,
    actor: User,
    *,
    slug: str,
    name: str,
    description: str = "",
    organisation_id: int | None = None,
) -> Group:
    """Crée un groupe. Il naît **vide** — de membres comme de droits (FR-004).

    **Aucun appel à `assert_may_grant`** : la non-amplification de #115 garde la
    distribution de **pouvoirs**, et un groupe n'en porte aucun. L'y appeler
    laisserait croire qu'il y a quelque chose à amplifier.
    """
    club = _existing_organisation(db, organisation_id)
    if group_repository.find_in_scope(db, slug=slug, organisation_id=club) is not None:
        raise GroupSlugTakenError()

    try:
        # **Le point de reprise entoure l'écriture, pas un flush d'après-coup.**
        # `group_repository.create` flushe lui-même : c'est là que la violation de
        # `uq_group_org_slug` est levée, et un `try` posé après lui n'attraperait
        # rien — la lecture ci-dessus, elle, est franchie par deux exploitants
        # simultanés. Le `SAVEPOINT` rattrape sans perdre la transaction en cours.
        with db.begin_nested():
            group = group_repository.create(
                db, organisation_id=club, slug=slug, name=name, description=description
            )
    except IntegrityError as collision:
        raise GroupSlugTakenError() from collision

    logger.info(
        "Group created: actor=%s group=%s organisation=%s", actor.id, group.slug, club
    )
    return group


def update_group(
    db: Session,
    actor: User,
    group: Group,
    *,
    name: str | None = None,
    description: str | None = None,
) -> Group:
    """Renomme et redécrit. **Le slug ne bouge pas** — il est l'identité du groupe,
    et le changer serait un changement d'identité déguisé en modification de
    libellé. Aucune appartenance n'est touchée (FR-006)."""
    if name is not None:
        group.name = name
    if description is not None:
        group.description = description
    db.flush()

    logger.info("Group updated: actor=%s group=%s", actor.id, group.slug)
    return group


def delete_group(db: Session, actor: User, group: Group) -> None:
    """Supprime un groupe **vide** ; refuse s'il compte encore des members (FR-011).

    Le nombre est **dans le message** : « conflit » ne se corrige pas. Il n'y a
    aucune cascade — la refuser ici et la laisser à l'ORM reviendrait à ne tenir
    la règle que par le chemin.
    """
    members = group_repository.count_members(db, group.id)
    if members:
        raise GroupInUseError(
            f"Ce groupe compte {members} membre{'s' if members > 1 else ''}. "
            f"Retirez-{'les' if members > 1 else 'le'} d'abord."
        )

    logger.info("Group deleted: actor=%s group=%s", actor.id, group.slug)
    group_repository.delete(db, group)


def add_member(db: Session, actor: User, *, group: Group, user: User) -> None:
    """Ajoute un membre. **Idempotent** (FR-008).

    Un compte **désactivé** est un membre parfaitement légitime : rien de ce que
    porte un groupe ne dépend de son activité. Refuser serait le traiter comme un
    porteur de droits.
    """
    _, created = group_repository.add_member(db, group_id=group.id, user_id=user.id)
    logger.info(
        "Member added: actor=%s target_user=%s group=%s new=%s",
        actor.id,
        user.id,
        group.slug,
        created,
    )


def remove_member(db: Session, actor: User, *, group: Group, user: User) -> None:
    """Retire un membre. Idempotent, et **ne retire rien d'autre** (FR-009).

    Aucun invariant ne s'y oppose, contrairement au retrait d'un rôle : vider un
    groupe entièrement ne verrouille personne dehors.
    """
    group_repository.remove_member(db, group_id=group.id, user_id=user.id)
    logger.info(
        "Member removed: actor=%s target_user=%s group=%s",
        actor.id,
        user.id,
        group.slug,
    )


def _existing_organisation(db: Session, organisation_id: int | None) -> int:
    """Le club visé — celui demandé s'il existe, le seul en base sinon.

    **L'existence est vérifiée**, et ce n'est pas une précaution de style :
    `core/database.py` n'émet aucun `PRAGMA foreign_keys=ON`, donc un
    `organisation_id` fantaisiste passerait en SQLite (développement et toute la
    suite de tests) et lèverait une violation de clé étrangère non attrapée en
    PostgreSQL. Un chemin d'écriture exposé qui diverge entre les deux moteurs
    est le pire des trois états possibles.

    Passe par `role_repository`, où vivent les accesseurs d'`Organisation`
    depuis #115. Les redéclarer ici en ferait une seconde définition de « quel
    club » — exactement le genre de divergence que le dépôt paie ailleurs
    (`is_tcn`, #76).
    """
    if organisation_id is not None:
        if role_repository.get_organisation(db, organisation_id) is None:
            raise NoOrganisationError("Ce club n'existe pas.")
        return organisation_id

    organisation = role_repository.default_organisation(db)
    if organisation is None:
        raise NoOrganisationError()
    return organisation.id
