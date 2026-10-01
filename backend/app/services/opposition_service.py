"""Droit d'opposition d'un athlète (#334).

Appliquer une opposition anonymise chaque résultat de la personne (motif
« Anonyme {épreuve}-{dossard} », celui des noms masqués à l'import), retire sa
fiche et ce qui la référence, et consigne le geste sans le nom. Les rangs,
valeurs publiées par la source, ne bougent pas. L'empreinte gardée en base fait
arriver anonymes les résultats importés ensuite (`import_service`).

Les homonymes sont couverts : la clé est le nom et le prénom normalisés
(`core/identity`), seule identité que les imports connaissent.
"""
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.core.club import is_tcn
from app.core.exceptions import DomainError, NotFoundError
from app.core.identity import identity_hash, opposition_key
from app.core.time import utcnow
from app.models.athlete import Athlete
from app.models.athlete_opposition import AthleteOpposition
from app.models.user import User
from app.repositories import (
    athlete_repository,
    course_repository,
    opposition_repository,
    participation_repository,
    season_validation_repository,
    user_repository,
    volunteer_action_repository,
)
from app.services import audit

OVERDUE_AFTER_DAYS = 30
OPPOSED_MESSAGE = (
    "Cette personne s'est opposée à la publication de ses résultats : "
    "ce résultat ne peut pas être enregistré."
)


class OpposedIdentityError(DomainError):
    """Saisie manuelle ou composition d'équipe au nom d'une personne opposée."""

    def __init__(self) -> None:
        super().__init__(OPPOSED_MESSAGE)


@dataclass(frozen=True)
class OppositionPreview:
    athletes: int
    results: int
    already_opposed: bool


def anonymous_name(course_id: int, bib_number: str | None, participation_id: int) -> str:
    return f"Anonyme {course_id}-{bib_number or f'p{participation_id}'}"


def is_opposed(db: Session, nom: str, prenom: str) -> bool:
    return opposition_repository.get_by_hash(db, identity_hash(nom, prenom)) is not None


def ensure_not_opposed(db: Session, nom: str, prenom: str) -> None:
    if is_opposed(db, nom, prenom):
        raise OpposedIdentityError()


def _identity(db: Session, athlete_id: int | None, nom: str | None, prenom: str | None) -> tuple[str, str]:
    if athlete_id is not None:
        athlete = athlete_repository.get(db, athlete_id)
        if athlete is None:
            raise NotFoundError("Cet athlète n'existe pas.")
        nom, prenom = athlete.nom, athlete.prenom
    if not opposition_key(nom or "", prenom or ""):
        raise DomainError("Indiquez le nom et le prénom de la personne.")
    return nom or "", prenom or ""


def _matching_athletes(db: Session, nom: str, prenom: str) -> list[Athlete]:
    key = opposition_key(nom, prenom)
    return [
        athlete_repository.get(db, athlete_id)
        for athlete_id, other_nom, other_prenom in athlete_repository.list_identities(db)
        if opposition_key(other_nom, other_prenom) == key
    ]


def _appearances(db: Session, athlete: Athlete) -> tuple[list, list]:
    carried = participation_repository.list_carried_by(db, athlete.id)
    carried_ids = {participation.id for participation in carried}
    links = [
        link for link in participation_repository.teammate_links_of(db, athlete.id)
        if link.participation_id not in carried_ids
    ]
    return carried, links


def preview(
    db: Session, *, athlete_id: int | None = None, nom: str | None = None, prenom: str | None = None
) -> OppositionPreview:
    nom, prenom = _identity(db, athlete_id, nom, prenom)
    athletes = _matching_athletes(db, nom, prenom)
    results = 0
    for athlete in athletes:
        carried, links = _appearances(db, athlete)
        results += len(carried) + len(links)
    return OppositionPreview(len(athletes), results, is_opposed(db, nom, prenom))


def _anonymise(db: Session, athlete: Athlete) -> int:
    carried, links = _appearances(db, athlete)
    for participation in carried:
        anonymous = athlete_repository.get_or_create(
            db, nom=anonymous_name(participation.course_id, participation.bib_number, participation.id), prenom=""
        )
        if athlete.id in participation_repository.teammate_athlete_ids(db, participation.id):
            participation_repository.replace_teammate(
                db, participation_id=participation.id, old_athlete_id=athlete.id, new_athlete_id=anonymous.id
            )
        if is_tcn(participation.club):
            course_repository.adjust_counts(db, participation.course, participation_delta=0, tcn_delta=-1)
        participation_repository.reassign(db, participation, athlete_id=anonymous.id)
        participation.club = ""
        participation.category = ""
        participation.raw_data = {}
    for link in links:
        participation = link.participation
        base = anonymous_name(participation.course_id, participation.bib_number, participation.id)
        anonymous = athlete_repository.get_or_create(db, nom=f"{base}-{link.position}", prenom="")
        participation_repository.replace_teammate(
            db, participation_id=participation.id, old_athlete_id=athlete.id, new_athlete_id=anonymous.id
        )
        # La ligne brute d'un relais porte les noms de toute l'équipe.
        participation.raw_data = {}
    user_repository.detach_athlete(db, athlete.id)
    volunteer_action_repository.delete_for_athlete(db, athlete.id)
    season_validation_repository.delete_for_athlete(db, athlete.id)
    db.expire(athlete)
    athlete_repository.delete(db, athlete)
    return len(carried) + len(links)


def apply(
    db: Session,
    actor: User,
    *,
    athlete_id: int | None = None,
    nom: str | None = None,
    prenom: str | None = None,
    requested_on: date,
    today: date | None = None,
) -> tuple[AthleteOpposition, bool]:
    """Anonymise et retire la fiche, enregistre l'empreinte, journalise, commite.

    Rend `(opposition, créée)` : une identité déjà opposée est réappliquée (une
    fiche a pu naître d'une saisie antérieure), sur la même ligne.
    """
    if requested_on > (today or utcnow().date()):
        raise DomainError("La date de la demande ne peut pas être dans le futur.")
    nom, prenom = _identity(db, athlete_id, nom, prenom)
    anonymised = sum(_anonymise(db, athlete) for athlete in _matching_athletes(db, nom, prenom))

    empreinte = identity_hash(nom, prenom)
    opposition = opposition_repository.get_by_hash(db, empreinte)
    created = opposition is None
    if created:
        opposition = opposition_repository.create(
            db, identity_hash=empreinte, requested_on=requested_on, applied_by_user_id=actor.id
        )
    opposition.anonymised_count += anonymised
    audit.record(
        db, actor.id, action="opposition_applied", entity_type="opposition", entity_id=opposition.id,
        payload={"requested_on": requested_on.isoformat(), "anonymised_count": anonymised},
    )
    db.commit()
    return opposition, created


def opposition_view(opposition: AthleteOpposition) -> dict:
    delay_days = (opposition.applied_at.date() - opposition.requested_on).days
    return {
        "id": opposition.id,
        "requested_on": opposition.requested_on,
        "applied_at": opposition.applied_at,
        "delay_days": delay_days,
        "overdue": delay_days > OVERDUE_AFTER_DAYS,
        "applied_by_name": opposition.applied_by.display_name if opposition.applied_by else None,
        "anonymised_count": opposition.anonymised_count,
    }


def list_oppositions(db: Session) -> list[dict]:
    return [opposition_view(opposition) for opposition in opposition_repository.list_recent(db)]
