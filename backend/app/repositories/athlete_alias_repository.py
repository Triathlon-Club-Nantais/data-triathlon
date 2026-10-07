"""Accès données pour AthleteAlias, les graphies mémorisées par une fusion (#908)."""
from collections.abc import Sequence

from sqlalchemy import delete as sql_delete
from sqlalchemy import func, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.athlete import Athlete
from app.models.athlete_alias import AthleteAlias
from app.repositories.athlete_repository import IdentityKey


def get_by_keys_batch(db: Session, keys: Sequence[IdentityKey]) -> dict[IdentityKey, Athlete]:
    """Les fiches dont ces clés sont des variantes, en une requête.

    `FOR KEY SHARE` sur la fiche, comme `athlete_repository.get_by_identity_keys_batch` :
    une fusion ne la supprime pas sous l'import qui la résout.
    """
    wanted = {key for key in keys if key[0] is not None}
    if not wanted:
        return {}
    rows = db.execute(
        select(AthleteAlias.last_name_key, AthleteAlias.first_name_key, Athlete)
        .join(Athlete, Athlete.id == AthleteAlias.athlete_id)
        .where(tuple_(AthleteAlias.last_name_key, AthleteAlias.first_name_key).in_(wanted))
        .with_for_update(of=Athlete, read=True, key_share=True)
    )
    return {(last, first): athlete for last, first, athlete in rows}


def add(db: Session, key: IdentityKey, athlete_id: int) -> bool:
    """Inscrit `key` comme variante de la fiche ; faux si elle appartient déjà à une fiche."""
    insert = postgresql_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    inserted = db.scalar(
        insert(AthleteAlias)
        .values(last_name_key=key[0], first_name_key=key[1], athlete_id=athlete_id)
        .on_conflict_do_nothing(index_elements=["last_name_key", "first_name_key"])
        .returning(AthleteAlias.id)
    )
    return inserted is not None


def repoint(db: Session, *, from_athlete_id: int, to_athlete_id: int) -> int:
    return db.execute(
        update(AthleteAlias).where(AthleteAlias.athlete_id == from_athlete_id).values(athlete_id=to_athlete_id)
    ).rowcount


def count_for_athlete(db: Session, athlete_id: int) -> int:
    return db.scalar(select(func.count()).select_from(AthleteAlias).where(AthleteAlias.athlete_id == athlete_id))


def delete_key(db: Session, key: IdentityKey) -> None:
    db.execute(
        sql_delete(AthleteAlias).where(
            AthleteAlias.last_name_key == key[0], AthleteAlias.first_name_key == key[1]
        )
    )


def list_for_athlete(db: Session, athlete_id: int) -> list[AthleteAlias]:
    return list(db.scalars(
        select(AthleteAlias).where(AthleteAlias.athlete_id == athlete_id).order_by(AthleteAlias.id)
    ))


def get(db: Session, alias_id: int) -> AthleteAlias | None:
    return db.get(AthleteAlias, alias_id)


def delete(db: Session, alias: AthleteAlias) -> None:
    db.delete(alias)

