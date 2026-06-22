"""Accès données pour Athlete — seule couche qui touche la Session pour cette table."""
from datetime import date

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.athlete import Athlete


def get(db: Session, athlete_id: int) -> Athlete | None:
    return db.get(Athlete, athlete_id)


def get_by_identity(
    db: Session, nom: str, prenom: str, birth_date: date | None
) -> Athlete | None:
    """Recherche insensible à la casse sur (nom, prénom, date de naissance)."""
    return (
        db.query(Athlete)
        .filter(
            func.lower(Athlete.nom) == (nom or "").strip().lower(),
            func.lower(Athlete.prenom) == (prenom or "").strip().lower(),
            Athlete.birth_date == birth_date,
        )
        .first()
    )


def get_or_create(
    db: Session,
    *,
    nom: str,
    prenom: str = "",
    gender: str = "",
    birth_date: date | None = None,
    club: str | None = None,
) -> Athlete:
    """Retourne l'athlète existant (dédoublonné) ou en crée un nouveau (flush pour l'id)."""
    existing = get_by_identity(db, nom, prenom, birth_date)
    if existing:
        # Met à jour le club courant si l'info est plus récente
        if club and existing.club != club:
            existing.club = club
        return existing

    athlete = Athlete(
        nom=(nom or "").strip(),
        prenom=(prenom or "").strip(),
        gender=gender or "",
        birth_date=birth_date,
        club=club,
    )
    db.add(athlete)
    db.flush()  # peuple athlete.id sans commit (la transaction est gérée par le service)
    return athlete


def search(
    db: Session,
    *,
    name: str | None = None,
    club: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> list[Athlete]:
    q = db.query(Athlete)
    if name:
        pattern = f"%{name}%"
        q = q.filter(
            or_(Athlete.nom.ilike(pattern), Athlete.prenom.ilike(pattern))
        )
    if club:
        keywords = [k.strip() for k in club.split("|") if k.strip()]
        if keywords:
            q = q.filter(or_(*[Athlete.club.ilike(f"%{k}%") for k in keywords]))
    offset = (page - 1) * page_size
    return q.order_by(Athlete.nom, Athlete.prenom).offset(offset).limit(page_size).all()
