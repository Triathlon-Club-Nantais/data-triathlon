"""Politique de provisionnement — qui a le droit d'exister comme utilisateur.

Extraite du flux délibérément : c'est **elle** qui grossira avec les rôles,
l'invitation et la restriction de domaine. La laisser dans l'orchestration du
parcours ferait de `flow.py` un objet-dieu à la première évolution.

L'ordre est contractuel (FR-005) : certification de l'adresse, **puis** choix de
l'adresse retenue, **puis** résolution de l'identité. Depuis #1322 la liste
d'autorisation ne refuse plus personne : une adresse certifiée hors liste ouvre
un compte **sans rôle**, que les gardes (pouvoir, code du site) laissent dehors
tant qu'il n'est pas adhérent ou qu'on ne lui donne pas de rôle.
"""
import logging
from dataclasses import replace

from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.models.user import User
from app.repositories import (
    allowed_email_repository,
    identity_repository,
    role_repository,
    user_repository,
    user_role_repository,
)
from app.services import membership
from app.services.auth import authorization
from app.services.auth.errors import LoginError
from app.services.auth.idp.base import ExternalIdentity

logger = logging.getLogger(__name__)


def resolve_user(db: Session, identity: ExternalIdentity) -> User:
    """Utilisateur derrière cette identité externe, créé au besoin.

    Un refus ne laisse **jamais** d'utilisateur enregistré (FR-006) : la
    certification est éprouvée avant la moindre écriture.
    """
    if not identity.email_verified or not identity.email:
        logger.info("Login refused: provider certifies no address (%s)", identity.provider)
        raise LoginError("email_unverified")

    # L'adresse retenue alimente `users.email` et `identities.email` (#1059,
    # FR-016 de #1322) : c'est sur elle que le statut adhérent se dérive.
    identity = replace(identity, email=membership.retained_email(db, identity, utcnow().date()))

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

        if allowed_email_repository.exists(db, user.email) and not allowed_email_repository.exists(
            db, identity.email
        ):
            # Une adresse inscrite n'est jamais remplacée par une adresse hors
            # liste : retirer l'adresse inscrite doit encore désactiver ce
            # compte, et `allowed_emails.remove` le retrouve par son adresse.
            identity = replace(identity, email=user.email)
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
    if not _grant_initial_role(db, user, identity.email):
        # Sans l'adresse : l'identifiant suffit à retrouver le compte, et rien
        # n'est à corriger côté exploitant, un compte sans rôle est légitime.
        logger.info("Account created without role: user=%s provider=%s", user.id, identity.provider)
    return user


def _grant_initial_role(db: Session, user: User, email: str) -> bool:
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
    entry = allowed_email_repository.get_by_email(db, email)
    if entry is None or entry.role_id is None:
        return False

    organisation = role_repository.default_organisation(db)
    role = role_repository.get(db, entry.role_id)
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
            entry.role_id,
            organisation.id if organisation else None,
            user.id,
        )
        return False

    # Réclamer **avant** de donner : le perdant d'une course ne donne rien, et
    # celui qui donne est celui qui a levé.
    if allowed_email_repository.claim_initial_role(db, entry) is None:
        return False

    user_role_repository.grant(
        db, user_id=user.id, role_id=role.id, organisation_id=organisation.id
    )
    logger.info(
        "Initial role granted: user=%s role=%s organisation=%s",
        user.id,
        role.slug,
        organisation.slug,
    )
    return True
