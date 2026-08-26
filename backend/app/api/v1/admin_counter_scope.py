"""Édition de la portée des compteurs (#95).

Les deux listes qui décident de ce que l'application compte : les disciplines
exclues des compteurs, et les libellés reconnus comme libellés du club.

Routeur **fin**, patron de `admin_site_access.py` : validation et délégation au
service, jamais un appel direct au repository pour une écriture. Le service
normalise, refuse le doublon et protège la liste des libellés ; le routeur
commite, journalise, et **recharge le registre après le commit** — recharger
avant exposerait une configuration que la transaction pourrait encore annuler.
"""
import logging

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.permissions import P
from app.models.counter_scope_entry import CLUB_LABEL, NON_FEDERAL_DISCIPLINE, CounterScopeEntry
from app.models.user import User
from app.repositories import admin_action_log_repository, counter_scope_repository
from app.schemas.counter_scope import (
    CounterScopeEntryIn,
    CounterScopeEntryOut,
    CounterScopeOut,
    ScopeKind,
)
from app.services import counter_scope

router = APIRouter(tags=["admin"])

_ENTITY_TYPE = "counter_scope_entry"

logger = logging.getLogger(__name__)


def _recharger(db: Session) -> None:
    """Recharge le registre, **après** le commit, sans jamais faire échouer l'appel.

    L'écriture est déjà persistée quand on arrive ici : rendre 500 dirait à
    l'administrateur que son geste a échoué alors qu'il a réussi, et il le
    referait. Le registre reste alors périmé jusqu'à la prochaine écriture ou au
    redémarrage — dégradation visible dans les logs, pas perte de donnée.
    """
    try:
        counter_scope.load_from_db(db)
    except Exception:
        logger.warning("counter scope reload failed after write", exc_info=True)


def _vue(entry: CounterScopeEntry) -> CounterScopeEntryOut:
    return CounterScopeEntryOut(
        id=entry.id,
        value=entry.value,
        is_known=(
            counter_scope.is_known_discipline(entry.value)
            if entry.kind == NON_FEDERAL_DISCIPLINE
            else True
        ),
        created_at=entry.created_at,
        created_by=entry.created_by.display_name if entry.created_by else None,
    )


@router.get("/admin/counter-scope", response_model=CounterScopeOut)
def get_counter_scope(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.COUNTER_SCOPE_MANAGE)),
):
    """Les deux listes — l'écran les affiche ensemble, deux appels seraient deux
    allers-retours pour une page."""
    entries = counter_scope_repository.list_entries(db, with_created_by=True)
    return CounterScopeOut(
        disciplines=[_vue(e) for e in entries if e.kind == NON_FEDERAL_DISCIPLINE],
        club_labels=[_vue(e) for e in entries if e.kind == CLUB_LABEL],
    )


@router.post(
    "/admin/counter-scope/{kind}",
    response_model=CounterScopeEntryOut,
    status_code=status.HTTP_201_CREATED,
)
def add_counter_scope_entry(
    kind: ScopeKind,
    body: CounterScopeEntryIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.COUNTER_SCOPE_MANAGE)),
):
    """Déclare une entrée. La valeur rendue est la forme retenue, pas la saisie."""
    entry = counter_scope.add_entry(
        db, kind=kind.stored, value=body.value, admin_user_id=actor.id
    )
    admin_action_log_repository.create(
        db,
        user_id=actor.id,
        action="counter_scope.entry_add",
        entity_type=_ENTITY_TYPE,
        entity_id=entry.id,
    )
    db.commit()
    _recharger(db)
    return _vue(entry)


@router.delete("/admin/counter-scope/{kind}/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_counter_scope_entry(
    kind: ScopeKind,
    entry_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.COUNTER_SCOPE_MANAGE)),
):
    """Retire une entrée.

    L'entrée est désignée par son identifiant, jamais par sa valeur : un libellé
    porte des espaces, et le faire transiter par un segment d'URL est une source
    d'ennuis sans contrepartie.
    """
    entry = counter_scope.remove_entry(db, kind=kind.stored, entry_id=entry_id)
    admin_action_log_repository.create(
        db,
        user_id=actor.id,
        action="counter_scope.entry_remove",
        entity_type=_ENTITY_TYPE,
        entity_id=entry.id,
    )
    db.commit()
    _recharger(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
