"""Gestion de la liste d'autorisation — qui a le droit d'ouvrir une session (#170).

Distinct de `provisioning.py`, qui **lit** cette liste au passage d'une
connexion : ici on l'**écrit**, depuis le back-office ou depuis la CLI
d'amorçage. Les deux responsabilités n'ont ni les mêmes appelants, ni les mêmes
invariants — celui-ci importe `authorization`, l'autre n'a rien à en savoir.

**L'ajout et le retrait sont symétriques sur les comptes**, et cette symétrie
n'est pas un raffinement : le retrait désactive les comptes portant l'adresse,
donc sans réactivation à l'ajout, réinscrire quelqu'un ne rouvrirait rien. Le
refus tomberait en `account_not_allowed` sur un compte pourtant listé à l'écran,
et rien ne l'expliquerait.
"""
import logging

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.models.allowed_email import AllowedEmail
from app.models.user import User
from app.repositories import allowed_email_repository, user_repository
from app.services.auth import authorization

logger = logging.getLogger(__name__)

#: `EmailStr` s'appuie sur `email-validator`, déjà installé par
#: `fastapi[standard]`. Employé ici plutôt que sur le DTO : posé sur le champ, il
#: fait rendre à FastAPI un 422 dont le `detail` est une liste et le message
#: anglais — deux contrats rompus d'un coup (FR-010, et la forme
#: `{"detail": "<chaîne>"}` que le front réaffiche).
_ADRESSE = TypeAdapter(EmailStr)


class InvalidEmailError(DomainError):
    """Saisie qui n'est pas une adresse électronique (FR-010).

    422 comme `ProviderNotSupportedError` : la requête est bien formée, c'est la
    **valeur** qui ne convient pas.
    """

    status_code = 422
    message = "Cette adresse électronique n'est pas valide."


def validate_email(email: str) -> str:
    """Rend l'adresse telle quelle si elle est valide, sinon lève en français.

    Le message **nomme la saisie** : « ce n'est pas valide » sans dire quoi
    oblige à retrouver ce qu'on a tapé, dans un formulaire qui vient de se vider.
    """
    try:
        _ADRESSE.validate_python(email.strip())
    except ValidationError as invalide:
        raise InvalidEmailError(
            f"« {email.strip()} » n'est pas une adresse électronique valide. "
            "Forme attendue : prenom.nom@exemple.fr."
        ) from invalide
    return email


def list_all(db: Session) -> list[AllowedEmail]:
    return allowed_email_repository.list_all(db)


def add(
    db: Session, actor: User | None, *, email: str
) -> tuple[AllowedEmail, bool, int]:
    """Inscrit l'adresse et **rouvre** les comptes qui la portent.

    Rend `(entrée, créée, comptes rouverts)` — réinscrire est un succès (FR-005),
    et le troisième terme est ce que la CLI rend à l'opérateur (« 2 compte(s)
    réactivé(s) ») : sans lui, « rien à faire » ne se distinguerait pas de « j'ai
    rouvert deux accès ». `actor` est `None` quand l'appel vient de la CLI
    d'amorçage, qui n'a pas de session.
    """
    entree, creee = allowed_email_repository.add(
        db, email=validate_email(email), created_by_user_id=actor.id if actor else None
    )
    reactives = user_repository.set_active(
        db, user_repository.find_by_email(db, entree.email), active=True
    )
    if creee or reactives:
        logger.info(
            "Allow-list: address added (actor=%s, created=%s, reactivated=%s)",
            actor.id if actor else "cli",
            creee,
            reactives,
        )
    return entree, creee, reactives


def remove(db: Session, actor: User, entry: AllowedEmail) -> int:
    """Retire l'adresse et **ferme** les comptes qui la portent (FR-016).

    Rend le nombre de comptes fermés. La désactivation fait tomber leurs sessions
    à la requête suivante — l'invariant de validité est une jointure — sans que
    `user_sessions` soit touchée. Ni l'utilisateur, ni ses rôles, ni son
    historique ne sont supprimés : le geste se défait par une réinscription
    (FR-017).

    **L'invariant du dernier administrateur est celui de #115, réutilisé tel
    quel** (FR-018). Retirer l'adresse du dernier administrateur actif
    verrouillerait le back-office pour tout le monde, sans recours autre que la
    CLI sur le serveur. La règle qui vient à l'esprit — « on ne retire pas sa
    propre adresse » — est à la fois trop stricte (un administrateur qui part,
    alors qu'un autre reste, en a le droit) et trop laxiste (retirer *l'autre*
    verrouille tout autant). Ce qui se garde est la **perte** du dernier
    administrateur, jamais l'identité du demandeur.
    """
    with authorization.administrateurs_preserves(db):
        comptes = user_repository.find_by_email(db, entry.email)
        fermes = user_repository.set_active(db, comptes, active=False)
        allowed_email_repository.delete(db, entry)

    logger.info(
        "Allow-list: address removed (actor=%s, deactivated=%s)", actor.id, fermes
    )
    return fermes
