"""Accès données pour ClubAlias (#635) — seule couche qui touche la Session.

Ne commite jamais : la transaction reste portée par le service appelant,
patron de `counter_scope_repository.py`.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

# `_normalise_sql` est module-privé (`core/club.py`) mais réutilisé tel quel
# ici plutôt que redoublé — même miroir SQL que `tcn_clause`, single source of
# truth (cf. plan #635, Global Constraints).
from app.core.club import _normalise_sql, normalize_club
from app.models.club_alias import ClubAlias


def list_entries(db: Session, *, with_created_by: bool = False) -> list[ClubAlias]:
    """Toutes les entrées, triées par nom canonique puis par alias — l'écran
    les affiche groupées par club."""
    query = select(ClubAlias).order_by(ClubAlias.canonical_name, ClubAlias.alias_normalized)
    if with_created_by:
        query = query.options(joinedload(ClubAlias.created_by))
    return list(db.scalars(query))


def find_by_alias(db: Session, *, alias_normalized: str) -> ClubAlias | None:
    return db.scalar(select(ClubAlias).where(ClubAlias.alias_normalized == alias_normalized))


def get_entry(db: Session, *, entry_id: int) -> ClubAlias | None:
    return db.get(ClubAlias, entry_id)


def create_entry(
    db: Session, *, canonical_name: str, alias_normalized: str, created_by_user_id: int | None
) -> ClubAlias:
    entry = ClubAlias(
        canonical_name=canonical_name,
        alias_normalized=alias_normalized,
        created_by_user_id=created_by_user_id,
    )
    db.add(entry)
    return entry


def delete_entry(db: Session, entry: ClubAlias) -> None:
    db.delete(entry)


def canonical_map(db: Session) -> dict[str, str]:
    """Alias normalisé → nom canonique, **toutes** les entrées d'un coup.

    Seul appelant : `stats_service.course_summary`, qui en a besoin une fois
    par appel — jamais par ligne (une épreuve porte jusqu'à ~1800
    participations, #163) — d'où un dict chargé en une requête plutôt qu'un
    lookup répété.
    """
    rows = db.execute(select(ClubAlias.alias_normalized, ClubAlias.canonical_name)).all()
    return {alias: canonical for alias, canonical in rows}


def aliases_for_canonical(db: Session, canonical_name: str) -> set[str]:
    """Les alias normalisés déclarés sous ce nom canonique.

    La comparaison porte sur la forme normalisée des **deux côtés** — le nom
    canonique demandé peut venir d'un paramètre d'URL et porter une casse ou
    un espacement différent de celui saisi en admin.
    """
    query = select(ClubAlias.alias_normalized).where(
        _normalise_sql(ClubAlias.canonical_name) == normalize_club(canonical_name)
    )
    return set(db.scalars(query))
