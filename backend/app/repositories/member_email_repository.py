"""Accès données des adresses d'adhérents par saison (#1334)."""
from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.season import season_of
from app.models.member_email import SOURCE_IMPORT, SOURCE_MANUAL, MemberEmail


def normalize(email: str) -> str:
    return email.strip().casefold()


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
    """
    existing = {entry.email: entry.source for entry in list_season(db, season)}
    gone = [e for e, source in existing.items() if source == SOURCE_IMPORT and e not in emails]
    new = sorted(emails - existing.keys())
    if gone:
        db.execute(delete(MemberEmail).where(MemberEmail.season == season, MemberEmail.email.in_(gone)))
    db.add_all(MemberEmail(email=e, season=season, source=SOURCE_IMPORT) for e in new)
    db.flush()
    return len(new), len(gone), len(emails & existing.keys())


def add_manual(db: Session, email: str, season: int) -> MemberEmail | None:
    """Ajoute à la main, ou promeut une entrée importée. `None` si déjà manuelle."""
    entry = db.scalar(select(MemberEmail).where(MemberEmail.email == email, MemberEmail.season == season))
    if entry is None:
        entry = MemberEmail(email=email, season=season, source=SOURCE_MANUAL)
        db.add(entry)
    elif entry.source == SOURCE_MANUAL:
        return None
    entry.source = SOURCE_MANUAL
    db.flush()
    return entry


def remove(db: Session, entry_id: int) -> MemberEmail | None:
    entry = db.get(MemberEmail, entry_id)
    if entry is not None:
        db.delete(entry)
        db.flush()
    return entry


def counting_season(db: Session, today: date) -> int:
    """La saison en cours si elle a une entrée, sinon la précédente : entre la
    rentrée et le premier import, la liste de l'an passé continue de compter."""
    current = season_of(today)
    has_entry = db.scalar(select(select(MemberEmail.id).where(MemberEmail.season == current).exists()))
    return current if has_entry else current - 1


def counts(db: Session, email: str, today: date) -> bool:
    return db.scalar(
        select(MemberEmail.id).where(
            MemberEmail.email == normalize(email), MemberEmail.season == counting_season(db, today)
        ).limit(1)
    ) is not None


def purge_before(db: Session, season: int, *, dry_run: bool) -> int:
    """Tient la durée de conservation : supprime les saisons antérieures à `season`."""
    old = MemberEmail.season < season
    if dry_run:
        return db.scalar(select(func.count()).select_from(MemberEmail).where(old))
    removed = db.execute(delete(MemberEmail).where(old)).rowcount
    db.flush()
    return removed
