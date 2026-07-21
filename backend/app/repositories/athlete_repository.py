"""Accès données pour Athlete — seule couche qui touche la Session pour cette table."""
from datetime import date

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.club import club_keyword_filter
from app.models.athlete import Athlete
from app.models.participation import Participation


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


def resolve(
    db: Session,
    *,
    nom: str,
    prenom: str = "",
    gender: str = "",
    birth_date: date | None = None,
    club: str | None = None,
) -> tuple[Athlete, bool]:
    """Retourne (athlète, créé) : `créé` est True si la ligne vient d'être créée.

    Le repli de réconciliation distingue un **renommage** (cible créée) d'une
    **fusion** (cible préexistante) ; ce drapeau est la seule information qui les
    sépare. `get_or_create` reste le point d'entrée quand le drapeau n'importe pas.
    """
    existing = get_by_identity(db, nom, prenom, birth_date)
    if existing:
        # Met à jour le club courant si l'info est plus récente
        if club and existing.club != club:
            existing.club = club
        return existing, False

    athlete = Athlete(
        nom=(nom or "").strip(),
        prenom=(prenom or "").strip(),
        gender=gender or "",
        birth_date=birth_date,
        club=club,
    )
    db.add(athlete)
    db.flush()  # peuple athlete.id sans commit (la transaction est gérée par le service)
    return athlete, True


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
    athlete, _ = resolve(
        db, nom=nom, prenom=prenom, gender=gender, birth_date=birth_date, club=club
    )
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
    clause = club_keyword_filter(Athlete.club, club)
    if clause is not None:
        q = q.filter(clause)
    offset = (page - 1) * page_size
    return q.order_by(Athlete.nom, Athlete.prenom).offset(offset).limit(page_size).all()


def delete_orphans(db: Session) -> int:
    """Supprime les athlètes sans aucune participation. Renvoie le nombre supprimé.

    `Participation.athlete_id` est la **seule** FK vers `Athlete` : un athlète
    sans participation n'est plus référencé nulle part. La base compte 0 orphelin
    en régime normal, donc la règle est un no-op sur l'existant — elle ne peut
    emporter que ce que la réconciliation vient de libérer. Appelée **une fois**
    en fin de batch (jamais par épreuve : un orphelin après l'épreuve A peut être
    ré-attaché par l'épreuve B).
    """
    rows = (
        db.query(Athlete.id)
        .outerjoin(Participation, Participation.athlete_id == Athlete.id)
        .filter(Participation.id.is_(None))
        .all()
    )
    orphan_ids = [r[0] for r in rows]
    if not orphan_ids:
        return 0
    db.query(Athlete).filter(Athlete.id.in_(orphan_ids)).delete(synchronize_session="fetch")
    return len(orphan_ids)
