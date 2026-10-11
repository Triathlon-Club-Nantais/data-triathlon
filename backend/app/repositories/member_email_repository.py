"""Accès données des adresses d'adhérents par saison (#1334)."""
from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.email import normalize_email
from app.core.season import season_of
from app.models.member_email import SOURCE_IMPORT, SOURCE_MANUAL, MemberEmail

normalize = normalize_email


def list_season(db: Session, season: int) -> list[MemberEmail]:
    return list(db.scalars(
        select(MemberEmail).where(MemberEmail.season == season).order_by(MemberEmail.email)
    ))


def seasons(db: Session) -> list[int]:
    return list(db.scalars(select(MemberEmail.season).distinct().order_by(MemberEmail.season.desc())))


def replace_imported(db: Session, season: int, emails: set[str]) -> tuple[int, int, int]:
    """Remplace les entrées importées de la saison par `emails` (déjà normalisées).

    Les entrées manuelles restent ; une adresse du fichier déjà présente, quelle
    que soit son origine, est inchangée. Rend `(ajoutées, retirées, inchangées)`.

    Sous point de reprise : une adresse ajoutée entre la lecture et l'écriture
    fait céder `UNIQUE(email, season)`, l'`IntegrityError` remonte et la
    transaction de l'appelant reste utilisable.
    """
    existing = {entry.email: entry.source for entry in list_season(db, season)}
    gone = [e for e, source in existing.items() if source == SOURCE_IMPORT and e not in emails]
    new = sorted(emails - existing.keys())
    with db.begin_nested():
        if gone:
            db.execute(delete(MemberEmail).where(MemberEmail.season == season, MemberEmail.email.in_(gone)))
        db.add_all(MemberEmail(email=e, season=season, source=SOURCE_IMPORT) for e in new)
        db.flush()
    return len(new), len(gone), len(emails & existing.keys())


def add_manual(db: Session, email: str, season: int) -> MemberEmail | None:
    """Ajoute à la main, ou promeut une entrée importée. `None` si déjà manuelle.

    L'insertion est tentée d'abord, sous point de reprise : une lecture préalable
    serait franchie par deux ajouts simultanés, `UNIQUE(email, season)` jamais
    (patron d'`allowed_email_repository.add`).
    """
    entry = MemberEmail(email=email, season=season, source=SOURCE_MANUAL)
    try:
        with db.begin_nested():
            db.add(entry)
            db.flush()
        return entry
    except IntegrityError:
        existing = db.scalar(select(MemberEmail).where(MemberEmail.email == email, MemberEmail.season == season))
        if existing is None:  # pragma: no cover, une autre contrainte a cédé
            raise
    if existing.source == SOURCE_MANUAL:
        return None
    existing.source = SOURCE_MANUAL
    db.flush()
    return existing


def remove(db: Session, entry_id: int) -> MemberEmail | None:
    entry = db.get(MemberEmail, entry_id)
    if entry is not None:
        db.delete(entry)
        db.flush()
    return entry


def _has_import(db: Session, season: int) -> bool:
    return db.scalar(select(
        select(MemberEmail.id).where(MemberEmail.season == season, MemberEmail.source == SOURCE_IMPORT).exists()
    ))


def counting_season(db: Session, today: date) -> int:
    """La saison en cours dès qu'elle a une entrée importée, sinon la précédente :
    entre la rentrée et le premier import, la liste de l'an passé continue de
    compter, et un ajout à la main ne la fait pas basculer."""
    current = season_of(today)
    return current if _has_import(db, current) else current - 1


def counts(db: Session, email: str, today: date) -> bool:
    """L'adresse figure dans la saison qui compte, ou dans la saison en cours.

    Tant que la saison en cours n'a aucun import, elle ne porte que des entrées
    manuelles : elles comptent en plus de la liste précédente.
    """
    seasons = {counting_season(db, today), season_of(today)}
    return db.scalar(
        select(MemberEmail.id).where(MemberEmail.email == normalize(email), MemberEmail.season.in_(seasons)).limit(1)
    ) is not None


def purge_before(db: Session, season: int, *, dry_run: bool) -> int:
    """Tient la durée de conservation : supprime les saisons antérieures à `season`."""
    old = MemberEmail.season < season
    if dry_run:
        return db.scalar(select(func.count()).select_from(MemberEmail).where(old))
    removed = db.execute(delete(MemberEmail).where(old)).rowcount
    db.flush()
    return removed
