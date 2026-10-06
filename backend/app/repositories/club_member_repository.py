"""Accès données des licenciés du club par saison (#1202)."""
from sqlalchemy import delete, func, or_, select, update
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

    Une ligne non rattachée disparaît. Une ligne rattachée ne garde que le fait
    « cette fiche était licenciée cette saison », qui fait compter ses
    résultats d'alors : numéro de licence effacé, nom et prénom remplacés par
    ceux de la fiche.
    """
    old = ClubMember.season < season
    pending = or_(ClubMember.licence_id.is_not(None), ClubMember.link_status.not_in(LINKED))
    touched = db.scalar(select(func.count()).select_from(ClubMember).where(old, pending))
    if dry_run:
        return touched
    db.execute(delete(ClubMember).where(old, ClubMember.link_status.not_in(LINKED)))
    db.execute(
        update(ClubMember)
        .where(old, ClubMember.link_status.in_(LINKED))
        .values(
            licence_id=None,
            nom=select(Athlete.nom).where(Athlete.id == ClubMember.athlete_id).scalar_subquery(),
            prenom=select(Athlete.prenom).where(Athlete.id == ClubMember.athlete_id).scalar_subquery(),
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
