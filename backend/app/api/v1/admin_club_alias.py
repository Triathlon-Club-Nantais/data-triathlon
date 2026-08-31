"""Édition des alias de club (#635) — généralisation de la fusion des variantes.

Routeur fin, patron de `admin_counter_scope.py` : validation + délégation au
service, jamais un appel direct au repository pour une écriture.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.permissions import P
from app.models.club_alias import ClubAlias
from app.models.user import User
from app.repositories import admin_action_log_repository, club_alias_repository
from app.schemas.club_alias import ClubAliasIn, ClubAliasList, ClubAliasOut
from app.services import club_alias as club_alias_service

router = APIRouter(tags=["admin"])

_ENTITY_TYPE = "club_alias"


def _vue(entry: ClubAlias) -> ClubAliasOut:
    return ClubAliasOut(
        id=entry.id,
        canonical_name=entry.canonical_name,
        alias=entry.alias_normalized,
        created_at=entry.created_at,
        created_by=entry.created_by.display_name if entry.created_by else None,
    )


@router.get("/admin/club-aliases", response_model=ClubAliasList)
def list_club_aliases(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.CLUB_ALIASES_MANAGE)),
) -> ClubAliasList:
    entries = club_alias_repository.list_entries(db, with_created_by=True)
    return ClubAliasList(entries=[_vue(e) for e in entries])


@router.post("/admin/club-aliases", response_model=ClubAliasOut, status_code=status.HTTP_201_CREATED)
def add_club_alias(
    body: ClubAliasIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.CLUB_ALIASES_MANAGE)),
) -> ClubAliasOut:
    entry = club_alias_service.add_entry(
        db, canonical_name=body.canonical_name, alias=body.alias, admin_user_id=actor.id
    )
    admin_action_log_repository.create(
        db, user_id=actor.id, action="club_alias.add", entity_type=_ENTITY_TYPE, entity_id=entry.id
    )
    db.commit()
    return _vue(entry)


@router.delete("/admin/club-aliases/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_club_alias(
    entry_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.CLUB_ALIASES_MANAGE)),
) -> None:
    entry = club_alias_service.remove_entry(db, entry_id=entry_id)
    admin_action_log_repository.create(
        db,
        user_id=actor.id,
        action="club_alias.remove",
        entity_type=_ENTITY_TYPE,
        entity_id=entry.id,
    )
    db.commit()
