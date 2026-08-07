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
from enum import Enum, auto

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.models.allowed_email import AllowedEmail
from app.models.user import User
from app.repositories import allowed_email_repository, role_repository, user_repository
from app.services.auth import authorization

logger = logging.getLogger(__name__)

class _Sentinelle(Enum):
    """Porteuse d'`UNCHANGED`. `Enum` et non `object()` pour que le typage
    resserre bien `role_id` après un `is not UNCHANGED`."""

    UNCHANGED = auto()


#: « Cette demande ne se prononce pas sur le rôle ». **Distincte de `None`**, qui
#: lève celui qui était posé. Sans les deux, « Aucun » serait indicible : le rôle
#: se collerait à l'adresse, plus rien ne l'en retirerait, et le 409 de
#: `delete_role` réclamerait un geste qui n'existe pas.
#:
#: C'est aussi ce qui distingue la CLI de l'écran : `allow-email` réautorise une
#: adresse sans se prononcer sur son rôle, là où le formulaire l'énonce toujours.
UNCHANGED = _Sentinelle.UNCHANGED

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
    db: Session,
    actor: User | None,
    *,
    email: str,
    role_id: int | None | _Sentinelle = UNCHANGED,
) -> tuple[AllowedEmail, bool, int]:
    """Inscrit l'adresse et **rouvre** les comptes qui la portent.

    Rend `(entrée, créée, comptes rouverts)` — réinscrire est un succès (FR-005),
    et le troisième terme est ce que la CLI rend à l'opérateur (« 2 compte(s)
    réactivé(s) ») : sans lui, « rien à faire » ne se distinguerait pas de « j'ai
    rouvert deux accès ». `actor` est `None` quand l'appel vient de la CLI
    d'amorçage, qui n'a pas de session.

    `role_id` est le rôle que portera le compte **à sa création** (#239). Il est
    gardé **ici**, où il y a un acteur dont comparer les pouvoirs, et non à
    l'application — qui se produit pendant une connexion, sans acteur. C'est la
    même asymétrie que `grant-role`, et elle est ce qui empêche la voie
    d'escalade fermée sur l'attribution de rouvrir par ce chemin.

    **Réinscrire une adresse repose son rôle initial**, `None` compris : c'est le
    geste par lequel on corrige un choix, et le seul — la ligne n'a pas d'autre
    éditeur. Omettre le paramètre (`UNCHANGED`) ne se prononce pas.
    """
    adresse = validate_email(email)
    if role_id is not UNCHANGED:
        if actor is None:
            # Une garde qui s'annule pour qui ne passe pas d'acteur n'est pas une
            # garde — et c'est la forme exacte qui a produit le défaut d'origine.
            raise ValueError("Nommer un rôle initial exige un acteur.")
        _assert_may_choose(db, actor, adresse, role_id)

    entree, creee = allowed_email_repository.add(
        db, email=adresse, created_by_user_id=actor.id if actor else None
    )
    if role_id is not UNCHANGED:
        allowed_email_repository.set_initial_role(db, entree, role_id=role_id)
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


def _assert_may_choose(
    db: Session, actor: User, email: str, role_id: int | None
) -> None:
    """Les gardes de `grant_role` **et** de `revoke_role`, portées par le
    troisième guichet.

    C'est exactement ce qui manquait : le chemin du rôle initial est le
    **troisième** écrivain de `user_roles`, et il avait été ajouté avec une seule
    des gardes du premier. Poser un rôle est un geste d'attribution, pas un
    réglage de la liste d'autorisation — qu'il porte sur un compte qui n'existe
    pas encore n'y change rien.

    **Ce qui se garde est le changement, jamais la forme du corps.** Un
    `role_id` qui redit ce qui est déjà posé ne fait changer aucun rôle de
    mains ; l'exiger ferait de `{email, role_id: null}` — corps que beaucoup de
    clients envoient par défaut, et que l'API acceptait avant #239 — un refus
    d'autoriser.

    **Les deux côtés du changement se gardent**, et c'est l'erreur que la revue
    a trouvée : lever un rôle avait été traité comme un non-geste, sous prétexte
    qu'il ne donne rien à comparer. `assert_may_grant` compare des codes, en
    effet ; `assert_may_distribute_superuser`, elle, demande « êtes-vous
    superutilisateur ? », et `revoke_role` la porte déjà — destituer un
    administrateur est un geste d'administrateur. Sans la symétrie ici, un
    porteur de `roles:assign` effaçait le rôle garé sur l'adresse d'un futur
    administrateur, qui naissait alors sans rien : pas une escalade, un sabotage
    de nomination par le pouvoir le plus courant du back-office.

    L'ordre compte : le pouvoir d'attribuer se juge **avant** que le rôle soit
    résolu, sinon un identifiant inconnu rend 404 à qui n'attribue pas et le
    catalogue se balaie par le couple 404/201.
    """
    existante = allowed_email_repository.get_by_email(db, email)
    ancien = existante.role if existante else None
    if (ancien.id if ancien else None) == role_id:
        return  # rien ne change de mains

    authorization.assert_may_assign_roles(db, actor)
    if ancien is not None:
        authorization.assert_may_hand_over(db, actor, ancien)
    if role_id is None:
        return

    role = authorization.get_role_or_404(db, role_id)
    authorization.assert_may_hand_over(db, actor, role)
    organisation = role_repository.default_organisation(db)
    if organisation is not None:
        # FR-008 — refusé là où il se choisit. Le laisser passer ici pour le
        # rattraper à l'application ne rattraperait rien : à la connexion, il n'y
        # a plus personne à qui rendre 422.
        authorization.assert_role_assignable_in(db, role, organisation.id)


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
