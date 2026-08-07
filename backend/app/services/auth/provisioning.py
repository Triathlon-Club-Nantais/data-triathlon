"""Politique de provisionnement — qui a le droit d'exister comme utilisateur.

Extraite du flux délibérément : c'est **elle** qui grossira avec les rôles,
l'invitation et la restriction de domaine. La laisser dans l'orchestration du
parcours ferait de `flow.py` un objet-dieu à la première évolution.

L'ordre des trois étapes est contractuel (FR-005) : certification de l'adresse,
**puis** liste des comptes autorisés, **puis** résolution de l'identité.
"""
import logging

from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories import (
    allowed_email_repository,
    identity_repository,
    role_repository,
    user_repository,
    user_role_repository,
)
from app.services.auth import authorization
from app.services.auth.errors import LoginError
from app.services.auth.idp.base import ExternalIdentity

logger = logging.getLogger(__name__)


def resolve_user(db: Session, identity: ExternalIdentity) -> User:
    """Utilisateur derrière cette identité externe, créé au besoin.

    Un refus ne laisse **jamais** d'utilisateur enregistré (FR-006) : les deux
    portes sont franchies avant la moindre écriture.
    """
    if not identity.email_verified or not identity.email:
        logger.info("Login refused: provider certifies no address (%s)", identity.provider)
        raise LoginError("email_unverified")

    if not _is_allowed(db, identity.email):
        # L'adresse **est** journalisée ici, et nulle part ailleurs dans le
        # parcours. Le code rendu au visiteur est muet sur la valeur soumise
        # (FR-030) ; sans cette trace, un refus n'est pas diagnosticable et
        # l'exploitant ne sait pas quelle adresse ajouter à la liste. Une
        # adresse n'est pas un secret au sens de FR-038, dont le filet
        # (`test_no_secret_logged`) porte sur les jetons, les clés et le code de
        # retour. Elle n'est pas journalisée sur le refus de certification, où
        # le fournisseur ne la prouve pas et où l'exploitant n'a rien à faire.
        logger.info(
            "Login refused: address not in the allow-list (%s, %s)",
            identity.provider,
            identity.email,
        )
        raise LoginError("account_not_allowed")

    known = identity_repository.get_by_subject(
        db, provider=identity.provider, subject=identity.subject
    )
    if known is not None:
        user = user_repository.get(db, known.user_id)
        if user is None:
            # Identité pendante : la ligne `users` a disparu sans la sienne. La
            # FK est inerte en SQLite (`database.py` n'émet aucun
            # `PRAGMA foreign_keys=ON`), donc l'état est atteignable. Refuser en
            # le nommant dans le journal vaut mieux qu'un `AttributeError` sur
            # `None` que le `except Exception` du router imputerait au
            # fournisseur.
            logger.error(
                "Dangling identity %s/%s points at missing user %s",
                identity.provider,
                identity.subject,
                known.user_id,
            )
            raise LoginError("provider_error")

        if not user.is_active:
            # FR-015 : la désactivation ferme l'accès, **y compris** pour une
            # nouvelle connexion. `session.resolve` le refusait déjà en lecture,
            # mais laisser le parcours aboutir ici posait un cookie et
            # redirigeait comme si la connexion avait réussi — une boucle de
            # connexion qui paraît marcher, une session orpheline par tentative,
            # et le profil du compte révoqué réécrit à chaque passage.
            logger.info("Login refused: account is deactivated (%s)", identity.provider)
            raise LoginError("account_not_allowed")

        user_repository.refresh_profile(
            db, user, email=identity.email, display_name=identity.display_name
        )
        identity_repository.refresh_email(db, known, email=identity.email)
        return user

    # Identité inconnue → **nouvel** utilisateur, même si l'adresse est déjà en
    # base (FR-003). Apparier sur l'adresse ouvrirait la prise de contrôle par
    # pré-inscription : un attaquant créant chez un fournisseur laxiste un compte
    # portant l'adresse d'un contributeur.
    user = user_repository.create(
        db, email=identity.email, display_name=identity.display_name
    )
    identity_repository.create(
        db,
        user_id=user.id,
        provider=identity.provider,
        subject=identity.subject,
        email=identity.email,
    )
    _grant_initial_role(db, user, identity.email)
    return user


def _grant_initial_role(db: Session, user: User, email: str) -> None:
    """Le rôle que l'autorisation portait, donné **une fois**, à la naissance (#239).

    **Une fois, et le rôle est consommé** — c'est ce qui rend la promesse vraie.
    Laissé posé, il n'était « une fois » que *par compte* : toute identité
    externe inconnue en crée un nouveau, « même si l'adresse est déjà en base »
    (voir `resolve_user` ci-dessus), et l'entrée aurait donc armé chaque identité
    suivante portant l'adresse — y compris après une révocation, et longtemps
    après que celui qui a choisi le rôle a perdu le droit de le donner. C'est
    l'appariement par adresse que #114 refuse, sur le chemin qui accorde du
    pouvoir. Ni une reconnexion ni une réactivation ne repassent ici.

    **Aucune garde de non-amplification** : il n'y a pas d'acteur à cet instant,
    l'administrateur ayant choisi le rôle bien avant, sous les gardes de
    `allowed_emails.add`. Même asymétrie que `grant-role` — le contrôle porte sur
    le choix, jamais sur l'application.

    Rien de ce qui échoue ici ne doit refuser la connexion : un rôle disparu
    (la clé étrangère est inerte en SQLite), une base sans organisation ou un
    rôle devenu hors portée laisseraient un visiteur légitime dehors, avec un
    code d'erreur qui n'expliquerait rien.
    """
    entree = allowed_email_repository.get_by_email(db, email)
    if entree is None or entree.role_id is None:
        return

    organisation = role_repository.default_organisation(db)
    role = role_repository.get(db, entree.role_id)
    #: Les trois sorties ci-dessous **précèdent** la réclamation : rien ne doit
    #: lever le choix d'un administrateur sans que le compte l'ait reçu.
    # `role_assignable_in` et non une relecture de la règle : c'est le
    # **troisième** écrivain de `user_roles`, et un chemin qui écrit sans porter
    # les gardes du premier est exactement la façon dont ces règles se perdent.
    if (
        organisation is None
        or role is None
        or not authorization.role_assignable_in(role, organisation.id)
    ):
        logger.warning(
            "Initial role skipped: role=%s organisation=%s (user %s)",
            entree.role_id,
            organisation.id if organisation else None,
            user.id,
        )
        return

    # Réclamer **avant** de donner : le perdant d'une course ne donne rien, et
    # celui qui donne est celui qui a levé.
    if allowed_email_repository.claim_initial_role(db, entree) is None:
        return

    user_role_repository.grant(
        db, user_id=user.id, role_id=role.id, organisation_id=organisation.id
    )
    logger.info(
        "Initial role granted: user=%s role=%s organisation=%s",
        user.id,
        role.slug,
        organisation.slug,
    )


def _is_allowed(db: Session, email: str) -> bool:
    """Liste d'autorisation, **fail-closed** et réévaluée à chaque connexion.

    Vide = aucune connexion (FR-004 de #170) : une base neuve est un état
    ordinaire, et « liste vide = tout le monde » la transformerait en ouverture
    de l'administration à n'importe quel compte GitHub. C'est **ici**, et nulle
    part ailleurs, que le fail-closed se joue : depuis #170 le garde de
    configuration ne pèse plus la liste, et `/auth/methods` n'interroge aucune
    table.

    **En base, et sans cache.** La liste vivait dans un réglage lu par un
    `Settings` en `lru_cache` — c'est ce cache qui faisait de l'ajout d'un
    contributeur un redéploiement. Un ajout est désormais effectif à la
    tentative suivante, un retrait aussi.

    La comparaison ignore la casse et les espaces ; la normalisation est portée
    par le repository, seul point de passage de cette table.
    """
    return allowed_email_repository.exists(db, email)
