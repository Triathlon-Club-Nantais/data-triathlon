"""Écriture du journal d'administration, depuis les services (#935).

**Le journal s'écrit dans le service, jamais dans la route** : c'est le service
qui connaît l'effet, et la ligne partage sa transaction, ce qui rend les deux
indissociables (FR-015 de #117). Un geste refusé lève avant d'arriver ici, et
n'écrit donc rien.

Sans acteur (`actor_id=None`), rien n'est écrit : c'est le cas des commandes CLI
d'amorçage (`allow-email`, `set-site-code`), qui n'ont pas de session et dont
l'accès au serveur *est* le privilège. `admin_action_log.user_id` est
obligatoire, et un auteur inventé serait pire qu'une absence.
"""
from sqlalchemy.orm import Session

from app.repositories import admin_action_log_repository


def record(
    db: Session,
    actor_id: int | None,
    *,
    action: str,
    entity_type: str,
    entity_id: int,
    payload: dict | None = None,
) -> None:
    if actor_id is None:
        return
    admin_action_log_repository.create(
        db,
        user_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload,
    )
