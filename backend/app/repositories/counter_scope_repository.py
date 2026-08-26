"""Accès données pour `CounterScopeEntry` (#95) — seule couche qui touche la Session.

Ne commite jamais : la transaction reste portée par le service appelant, patron
de `site_access_config_repository.py`.
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.counter_scope_entry import CounterScopeEntry


def list_entries(
    db: Session, *, kind: str | None = None, with_created_by: bool = False
) -> list[CounterScopeEntry]:
    """Les entrées, triées par valeur — un ordre stable, et le seul qui aide à
    chercher une entrée à l'œil.

    `with_created_by=False` par défaut : le chargement du registre au démarrage
    et à chaque écriture ne lit que `kind` et `value`, et n'a aucune raison de
    payer la jointure sur l'auteur — utile à la seule vue d'administration.
    """
    query = select(CounterScopeEntry).order_by(CounterScopeEntry.value)
    if kind is not None:
        query = query.where(CounterScopeEntry.kind == kind)
    if with_created_by:
        query = query.options(joinedload(CounterScopeEntry.created_by))
    return list(db.scalars(query))


def get_entry(db: Session, *, kind: str, entry_id: int) -> CounterScopeEntry | None:
    """L'entrée de cette nature portant cet identifiant.

    La nature fait partie de la question, elle n'est pas décorative : un
    identifiant de discipline demandé sous la nature « libellé » est une entrée
    introuvable, jamais l'entrée de l'autre liste.
    """
    return db.scalar(
        select(CounterScopeEntry).where(
            CounterScopeEntry.id == entry_id, CounterScopeEntry.kind == kind
        )
    )


def find_by_value(db: Session, *, kind: str, value: str) -> CounterScopeEntry | None:
    """L'entrée de cette nature portant cette valeur, ou `None`."""
    return db.scalar(
        select(CounterScopeEntry).where(
            CounterScopeEntry.kind == kind, CounterScopeEntry.value == value
        )
    )


def count_entries(db: Session, *, kind: str) -> int:
    return db.scalar(
        select(func.count()).select_from(CounterScopeEntry).where(
            CounterScopeEntry.kind == kind
        )
    )


def create_entry(
    db: Session, *, kind: str, value: str, created_by_user_id: int | None
) -> CounterScopeEntry:
    entry = CounterScopeEntry(kind=kind, value=value, created_by_user_id=created_by_user_id)
    db.add(entry)
    return entry


def delete_entry(db: Session, entry: CounterScopeEntry) -> None:
    db.delete(entry)
