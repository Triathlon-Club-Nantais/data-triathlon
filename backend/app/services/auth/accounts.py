"""Suppression des comptes : sur demande et après 5 ans d'inactivité (#1326).

Suppression **physique** : la ligne `users` et tout ce qui lui appartient
(identités, sessions, rôles, groupes). Les références facultatives d'autres
données sont mises à vide ; une référence obligatoire (journal, validation de
saison, cas ignorés, configuration d'accès) bloque la suppression, jamais
effacée en silence avec le compte.

Le journal est signé par le compte système : le compte supprimé ne peut pas être
l'auteur d'une ligne dont la FK l'exige, et la purge n'a pas d'acteur.
"""
import logging
from datetime import datetime
from typing import Literal

from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.models.user import SYSTEM_USER_EMAIL, User
from app.repositories import user_repository
from app.services import audit, volunteer_access
from app.services.auth import authorization

logger = logging.getLogger(__name__)

Origin = Literal["request", "inactivity"]

#: Durée publiée par la politique de confidentialité : changer l'une sans l'autre la rend fausse.
INACTIVITY_YEARS = 5


class AccountStillReferencedError(DomainError):
    status_code = 409
    message = (
        "Votre compte est encore cité par des actions du club et ne peut pas être "
        "supprimé ici. Contactez le club pour le faire supprimer."
    )


class SystemAccountDeletionError(DomainError):
    status_code = 409
    message = "Le compte système des bénévoles ne peut pas être supprimé."


def delete_account(db: Session, user: User, *, origin: Origin) -> None:
    """Supprime ce compte, ou lève sans rien supprimer. Ne commite pas."""
    if user.email == SYSTEM_USER_EMAIL:
        raise SystemAccountDeletionError()
    if user_repository.has_required_reference(db, user.id):
        raise AccountStillReferencedError()

    user_id = user.id
    # Identifiant pseudonyme chez Microsoft, gardé 12 mois avec le journal pour
    # la seule fin de supprimer l'utilisateur de l'annuaire Entra (à la main).
    entra_oids = [identity.subject for identity in user.identities if identity.provider == "entra"]
    # Point de reprise : un refus du dernier administrateur, levé après le flush,
    # ne laisse pas la suppression en attente dans la transaction de l'appelant.
    with db.begin_nested(), authorization.preserving_admins(db):
        user_repository.detach_optional_references(db, user_id)
        user_repository.delete(db, user)
    logger.info("Account deleted: user=%s origin=%s", user_id, origin)
    audit.record(
        db, volunteer_access.system_user_id(db), action="account.delete", entity_type="user", entity_id=user_id,
        payload={"origin": origin, "entra_oids": entra_oids},
    )


def inactivity_cutoff(now: datetime) -> datetime:
    """Même date du calendrier, 5 ans plus tôt ; un 29 février devient le 28."""
    try:
        return now.replace(year=now.year - INACTIVITY_YEARS)
    except ValueError:
        return now.replace(year=now.year - INACTIVITY_YEARS, day=28)


def purge_inactive(db: Session, *, now: datetime, dry_run: bool) -> tuple[int, int]:
    """Supprime les comptes sans rôle inactifs depuis 5 ans. Rend (supprimés, sautés).

    Ne commite pas. Un compte cité par une référence obligatoire est sauté, jamais
    supprimé avec elle. Le dernier administrateur n'est jamais candidat : il porte
    un rôle.
    """
    deleted = skipped = 0
    for user in user_repository.list_inactive_without_role(db, inactivity_cutoff(now)):
        if user_repository.has_required_reference(db, user.id):
            skipped += 1
            continue
        if not dry_run:
            delete_account(db, user, origin="inactivity")
        deleted += 1
    return deleted, skipped
