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
from typing import Literal

from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.models.user import SYSTEM_USER_EMAIL, User
from app.repositories import user_repository
from app.services import audit, benevole_access
from app.services.auth import authorization

logger = logging.getLogger(__name__)

Origin = Literal["request", "inactivity"]


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
    # Point de reprise : un refus du dernier administrateur, levé après le flush,
    # ne laisse pas la suppression en attente dans la transaction de l'appelant.
    with db.begin_nested(), authorization.administrateurs_preserves(db):
        user_repository.detach_optional_references(db, user_id)
        user_repository.delete(db, user)
    logger.info("Account deleted: user=%s origin=%s", user_id, origin)
    audit.record(
        db, benevole_access.system_user_id(db), action="account.delete", entity_type="user", entity_id=user_id,
        payload={"origin": origin},
    )
