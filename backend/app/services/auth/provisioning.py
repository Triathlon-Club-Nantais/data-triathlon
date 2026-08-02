"""Politique de provisionnement — qui a le droit d'exister comme utilisateur.

Extraite du flux délibérément : c'est **elle** qui grossira avec les rôles,
l'invitation et la restriction de domaine. La laisser dans l'orchestration du
parcours ferait de `flow.py` un objet-dieu à la première évolution.

L'ordre des trois étapes est contractuel (FR-005) : certification de l'adresse,
**puis** liste des comptes autorisés, **puis** résolution de l'identité.
"""
import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.user import User
from app.repositories import identity_repository, user_repository
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

    if not _is_allowed(identity.email):
        logger.info("Login refused: address not in the allow-list (%s)", identity.provider)
        raise LoginError("account_not_allowed")

    connue = identity_repository.get_by_subject(
        db, provider=identity.provider, subject=identity.subject
    )
    if connue is not None:
        user = user_repository.get(db, connue.user_id)
        user_repository.refresh_profile(
            db, user, email=identity.email, display_name=identity.display_name
        )
        identity_repository.refresh_email(db, connue, email=identity.email)
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
    return user


def _is_allowed(email: str) -> bool:
    """Liste d'autorisation, **fail-closed** et réévaluée à chaque connexion.

    Vide = aucune connexion (FR-007) : une variable absente sur Render est un
    incident ordinaire, et « liste vide = tout le monde » le transformerait en
    ouverture de l'administration à n'importe quel compte GitHub.

    La comparaison ignore la casse et les espaces : ces adresses sont saisies à
    la main dans une variable d'environnement.
    """
    autorisees = {a.strip().lower() for a in get_settings().auth_allowed_emails if a.strip()}
    return email.strip().lower() in autorisees
