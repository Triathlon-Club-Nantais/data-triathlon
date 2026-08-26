"""Portée des compteurs — chargement et édition (#95).

Ce module est le **seul** à remplir le registre `core/counter_scope.py`. Le sens
du flux ne s'inverse jamais : `core/` n'appelle rien au-dessus de lui, il est
appelé.

`load_from_db` a trois appelants, et trois seulement : le démarrage de l'API
(`app/main.py`), l'entrée de la CLI (`app/cli/__main__.py`), et chaque écriture
d'administration ci-dessous.
"""
from sqlalchemy.orm import Session

from app.core import counter_scope
from app.core.club import normalize_club
from app.core.exceptions import DomainError, DuplicateError, LastClubLabelError, NotFoundError
from app.models.counter_scope_entry import CLUB_LABEL, NON_FEDERAL_DISCIPLINE, CounterScopeEntry
from app.repositories import counter_scope_repository


def load_from_db(db: Session) -> None:
    """Relit les deux listes en base et remplace le registre d'un seul geste."""
    entries = counter_scope_repository.list_entries(db)
    counter_scope.load(
        disciplines={e.value for e in entries if e.kind == NON_FEDERAL_DISCIPLINE},
        club_labels={e.value for e in entries if e.kind == CLUB_LABEL},
    )


def normalize_value(kind: str, value: str) -> str:
    """Forme comparable d'une saisie, selon sa nature.

    Un libellé de club passe par `normalize_club` — la **même** fonction que le
    prédicat et son miroir SQL, sans quoi une entrée enregistrée pourrait ne
    jamais matcher. Un slug de discipline se contente des minuscules et des
    bords rognés : la nomenclature n'en porte ni espaces ni accents.
    """
    if kind == CLUB_LABEL:
        return normalize_club(value)
    return (value or "").strip().lower()


def is_known_discipline(value: str) -> bool:
    """Ce slug appartient-il à la nomenclature des disciplines ?

    Un slug inconnu n'est **pas** refusé (FR-011) : exclure une discipline pas
    encore importée est un geste légitime. Il porte un avertissement, c'est tout.
    """
    from app.scrapers.classify import CANONICAL_TYPES

    return value in CANONICAL_TYPES


def add_entry(
    db: Session, *, kind: str, value: str, admin_user_id: int
) -> CounterScopeEntry:
    """Ajoute une entrée. Rend l'entrée créée, valeur normalisée.

    Ne commite pas : le routeur porte la transaction, et recharge le registre
    **après** le commit.
    """
    normalisee = normalize_value(kind, value)
    if not normalisee:
        raise DomainError("Le libellé ne peut pas être vide.")

    if counter_scope_repository.find_by_value(db, kind=kind, value=normalisee) is not None:
        raise DuplicateError(f"« {normalisee} » figure déjà dans la liste.")

    entry = counter_scope_repository.create_entry(
        db, kind=kind, value=normalisee, created_by_user_id=admin_user_id
    )
    db.flush()
    return entry


def remove_entry(db: Session, *, kind: str, entry_id: int) -> CounterScopeEntry:
    """Retire une entrée. Rend l'entrée retirée, pour le journal.

    Refuse de vider **entièrement** la liste des libellés du club : sans aucun
    libellé, plus aucun résultat n'est compté comme résultat du club et tous les
    compteurs du club tombent à zéro, sans erreur ni avertissement. Vider la
    liste des disciplines exclues, à l'inverse, est légitime — tout devient
    fédéral, ce qui est cohérent, visible et réversible.

    Le comptage verrouille les lignes qu'il compte (`count_entries`) : deux
    suppressions concurrentes qui liraient toutes deux « 2 » videraient la liste
    à elles deux, sans qu'aucune ne voie de refus.
    """
    entry = counter_scope_repository.get_entry(db, kind=kind, entry_id=entry_id)
    if entry is None:
        raise NotFoundError("Cette entrée n'existe pas.")

    if kind == CLUB_LABEL and counter_scope_repository.count_entries(db, kind=kind) <= 1:
        raise LastClubLabelError

    counter_scope_repository.delete_entry(db, entry)
    db.flush()
    return entry
