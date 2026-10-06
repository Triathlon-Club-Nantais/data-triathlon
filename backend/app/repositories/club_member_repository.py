"""Accès données des licenciés du club par saison (#1202)."""
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.models.athlete import Athlete
from app.models.club_member import LINKED, ClubMember


def list_season(db: Session, season: int) -> list[ClubMember]:
    return list(db.scalars(
        select(ClubMember).where(ClubMember.season == season).order_by(ClubMember.nom, ClubMember.prenom)
    ))


def seasons(db: Session) -> list[int]:
    return list(db.scalars(select(ClubMember.season).distinct().order_by(ClubMember.season.desc())))


def get(db: Session, member_id: int) -> ClubMember | None:
    return db.get(ClubMember, member_id)


def replace_season(db: Session, season: int, members: list[ClubMember]) -> None:
    """Remplace toute la liste d'une saison, en une transaction."""
    db.execute(delete(ClubMember).where(ClubMember.season == season))
    db.flush()
    db.add_all(members)
    db.flush()


def purge_before(db: Session, season: int, *, dry_run: bool) -> int:
    """Tient la durée de conservation (#1202) : rend le nombre de lignes touchées.

    Une ligne non rattachée, ou rattachée à une fiche disparue, disparaît. Une
    ligne rattachée ne garde que le fait « cette fiche était licenciée cette
    saison », qui fait compter ses résultats d'alors : numéro de licence et
    sexe effacés, nom, prénom et clés d'identité remplacés par ceux de la
    fiche, une seule ligne par fiche et saison.
    """
    old_rows = db.execute(
        select(
            ClubMember.id, ClubMember.athlete_id, ClubMember.season, ClubMember.licence_id,
            ClubMember.link_status, ClubMember.gender, ClubMember.nom, ClubMember.prenom,
            ClubMember.last_name_key, ClubMember.first_name_key,
            Athlete.nom.label("athlete_nom"), Athlete.prenom.label("athlete_prenom"),
            Athlete.last_name_key.label("athlete_last_key"), Athlete.first_name_key.label("athlete_first_key"),
        )
        .outerjoin(Athlete, Athlete.id == ClubMember.athlete_id)
        .where(ClubMember.season < season)
        .order_by(ClubMember.id)
    ).all()
    to_delete: list[int] = []
    to_strip: list[int] = []
    kept: set[tuple[int, int]] = set()
    for row in old_rows:
        if row.link_status not in LINKED or row.athlete_id is None or (row.season, row.athlete_id) in kept:
            to_delete.append(row.id)
            continue
        kept.add((row.season, row.athlete_id))
        if (
            row.licence_id is not None
            or row.gender != ""
            or (row.nom, row.prenom) != (row.athlete_nom, row.athlete_prenom)
            or (row.last_name_key, row.first_name_key) != (row.athlete_last_key, row.athlete_first_key)
        ):
            to_strip.append(row.id)
    touched = len(to_delete) + len(to_strip)
    if dry_run or not touched:
        return touched
    db.execute(delete(ClubMember).where(ClubMember.id.in_(to_delete)))
    db.execute(
        update(ClubMember)
        .where(ClubMember.id.in_(to_strip))
        .values(
            licence_id=None,
            nom=select(Athlete.nom).where(Athlete.id == ClubMember.athlete_id).scalar_subquery(),
            prenom=select(Athlete.prenom).where(Athlete.id == ClubMember.athlete_id).scalar_subquery(),
            gender="",
            last_name_key=select(Athlete.last_name_key).where(Athlete.id == ClubMember.athlete_id).scalar_subquery(),
            first_name_key=select(Athlete.first_name_key).where(Athlete.id == ClubMember.athlete_id).scalar_subquery(),
        )
        .execution_options(synchronize_session=False)
    )
    db.flush()
    return touched


def repoint(db: Session, *, from_athlete_id: int, to_athlete_id: int) -> None:
    """Rattache à la fiche conservée les licenciés de la fiche absorbée.

    Sans cela, la suppression de la fiche absorbée passerait leur `athlete_id`
    à NULL et ferait perdre le fait « licencié cette saison ». Aucune
    contrainte d'unicité ne porte sur `athlete_id` : tout se déplace.
    """
    db.execute(
        update(ClubMember)
        .where(ClubMember.athlete_id == from_athlete_id)
        .values(athlete_id=to_athlete_id)
        .execution_options(synchronize_session=False)
    )
    db.flush()
