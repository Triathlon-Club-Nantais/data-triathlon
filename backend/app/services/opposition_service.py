"""Droit d'opposition d'un athlète (#334).

Appliquer une opposition anonymise chaque résultat de la personne (motif
« Anonyme {épreuve}-{dossard} », celui des noms masqués à l'import), retire sa
fiche et ce qui la référence, et consigne le geste sans le nom. Les rangs,
valeurs publiées par la source, ne bougent pas. L'empreinte gardée en base fait
arriver anonymes les résultats importés ensuite (`import_service`).

Les homonymes sont couverts : la clé est le nom et le prénom normalisés
(`core/identity`), seule identité que les imports connaissent.
"""
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.exceptions import DomainError, DuplicateError, NotFoundError
from app.core.identity import identity_hash, opposition_key
from app.core.time import utcnow
from app.models.athlete import Athlete
from app.models.athlete_opposition import AthleteOpposition
from app.models.user import User
from app.repositories import (
    admin_action_log_repository,
    athlete_claim_repository,
    athlete_repository,
    challenge_repository,
    club_member_repository,
    opposition_repository,
    participation_repository,
    season_validation_repository,
    tcn_count_repository,
    user_repository,
    volunteer_action_repository,
)
from app.scrapers.utils import split_relay_teammates
from app.services import audit

_TEAMMATE_SEPARATOR = re.compile(r"\s*[/+&;]\s*|\s+(?:et|-)\s+", re.IGNORECASE)
OVERDUE_AFTER_DAYS = 30
PARIS = ZoneInfo("Europe/Paris")
REDACTED = "[anonymisé]"
OPPOSED_MESSAGE = (
    "Cette personne s'est opposée à la publication de ses résultats : "
    "ce résultat ne peut pas être enregistré."
)


class OpposedIdentityError(DomainError):
    """Saisie manuelle ou composition d'équipe au nom d'une personne opposée."""

    status_code = 422

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


def named_hashes(*labels: str | None) -> set[str]:
    """Empreinte de chaque personne qu'un libellé nomme : lui entier, ou chaque équipier
    d'un libellé de relais. Règle commune à l'import et à la saisie (#1506).

    `+`, `&`, `;`, « et » et un tiret entouré d'espaces séparent des équipiers comme `/`
    (#1514). La virgule aussi, mais elle sépare encore « NOM, Prénom » : elle ne coupe
    que si chaque côté porte au moins deux mots. Une empreinte en trop anonymise à
    l'import la ligne d'une autre personne : un fragment de nom n'en produit pas.
    """
    hashes = set()
    for label in filter(None, labels):
        hashes.add(identity_hash(label, ""))
        for relay in (label, _TEAMMATE_SEPARATOR.sub("/", label)):
            hashes.update(identity_hash(*pair) for pair in split_relay_teammates(relay) or ())
        for segment in _TEAMMATE_SEPARATOR.split(label):
            hashes.add(identity_hash(segment, ""))
            parts = segment.split(",")
            if all(len(part.split()) >= 2 for part in parts):
                hashes.update(identity_hash(part, "") for part in parts)
    return hashes


def names_opposed(db: Session, nom: str, prenom: str, *labels: str | None) -> bool:
    """`labels` : autres libellés publiés avec l'identité, comme le nom d'une équipe de relais."""
    return opposition_repository.any_hash(db, named_hashes(f"{nom} {prenom}", *labels))


def ensure_not_opposed(db: Session, nom: str, prenom: str, *labels: str | None) -> None:
    """Refus explicite, réservé aux gestes des bénévoles : la saisie publique se tait (#1514)."""
    if names_opposed(db, nom, prenom, *labels):
        raise OpposedIdentityError()


def _identity(db: Session, athlete_id: int | None, nom: str | None, prenom: str | None) -> tuple[str, str]:
    if athlete_id is not None:
        athlete = athlete_repository.get(db, athlete_id)
        if athlete is None:
            raise NotFoundError("Cet athlète n'existe pas.")
        nom, prenom = athlete.nom, athlete.prenom
        if not opposition_key(nom, prenom):
            raise DomainError("Cette fiche ne porte aucun nom.")
    elif not opposition_key(nom or "", "") or not opposition_key(prenom or "", ""):
        raise DomainError("Indiquez le nom et le prénom de la personne.")
    return nom or "", prenom or ""


def _names_person(key: str, label: str) -> bool:
    """`label` désigne la personne : son identité même, ou un libellé de relais non découpé qui la nomme."""
    # `key` est déjà normalisée : `identity_hash(key, "")` est l'empreinte de la personne.
    return identity_hash(key, "") in named_hashes(label)


def _matching_athletes(db: Session, nom: str, prenom: str) -> list[Athlete]:
    key = opposition_key(nom, prenom)
    return [
        athlete_repository.get(db, athlete_id)
        for athlete_id, other_last_name, other_first_name in athlete_repository.list_identities(db)
        if _names_person(key, f"{other_last_name} {other_first_name}")
    ]


def _redacted(value, key: str):
    """Copie de `value` où toute chaîne, ou tout couple nom/prénom, qui désigne la personne est masqué."""
    if isinstance(value, dict):
        if isinstance(value.get("nom"), str) and opposition_key(value["nom"], value.get("prenom") or "") == key:
            value = {**value, "nom": REDACTED, "prenom": REDACTED}
        return {name: _redacted(item, key) for name, item in value.items()}
    if isinstance(value, list):
        return [_redacted(item, key) for item in value]
    if isinstance(value, str) and _names_person(key, value):
        return REDACTED
    return value


def _redact_log(db: Session, nom: str, prenom: str) -> None:
    """Les gestes passés (suppression, correction de fiche) ont pu consigner le nom : il en sort."""
    key = opposition_key(nom, prenom)
    for entry in admin_action_log_repository.list_with_payload(db):
        redacted = _redacted(entry.payload, key)
        if redacted != entry.payload:
            entry.payload = redacted


def club_today(now: datetime | None = None) -> date:
    """Le jour du club, à Paris : une demande saisie à 1 h du matin n'est pas « dans le futur »."""
    return (now or utcnow()).replace(tzinfo=UTC).astimezone(PARIS).date()


def _appearances(db: Session, athlete: Athlete) -> tuple[list, list, list]:
    carried = participation_repository.list_carried_by(db, athlete.id)
    carried_ids = {participation.id for participation in carried}
    links = [
        link for link in participation_repository.teammate_links_of(db, athlete.id)
        if link.participation_id not in carried_ids
    ]
    return carried, links, challenge_repository.list_for_athlete_ids(db, athlete.id)


def preview(
    db: Session, *, athlete_id: int | None = None, nom: str | None = None, prenom: str | None = None
) -> OppositionPreview:
    nom, prenom = _identity(db, athlete_id, nom, prenom)
    athletes = _matching_athletes(db, nom, prenom)
    results = 0
    for athlete in athletes:
        carried, links, challenge_rows = _appearances(db, athlete)
        results += len(carried) + len(links) + len(challenge_rows)
    return OppositionPreview(len(athletes), results, is_opposed(db, nom, prenom))


def _anonymise(db: Session, athlete: Athlete) -> int:
    carried, links, challenge_rows = _appearances(db, athlete)
    for participation in carried:
        # Le genre reste : il ne désigne personne, et les vues par genre gardent la ligne.
        anonymous = athlete_repository.get_or_create(
            db, nom=anonymous_name(participation.course_id, participation.bib_number, participation.id),
            prenom="", gender=athlete.gender or "",
        )
        if athlete.id in participation_repository.teammate_athlete_ids(db, participation.id):
            participation_repository.replace_teammate(
                db, participation_id=participation.id, old_athlete_id=athlete.id, new_athlete_id=anonymous.id
            )
        participation_repository.reassign(db, participation, athlete_id=anonymous.id)
        participation.club = ""
        participation.category = ""
        participation.raw_data = {}
        participation.team_name = ""
        # La clé source (`<nom>|<prénom>`) nomme la personne ; sans elle, la fiche anonyme en tient lieu.
        participation.source_identity_key = None
    for link in links:
        participation = link.participation
        base = anonymous_name(participation.course_id, participation.bib_number, participation.id)
        anonymous = athlete_repository.get_or_create(db, nom=f"{base}-{link.position}", prenom="")
        participation_repository.replace_teammate(
            db, participation_id=participation.id, old_athlete_id=athlete.id, new_athlete_id=anonymous.id
        )
        # La ligne brute, le libellé et la clé source d'un relais portent les noms de toute l'équipe.
        participation.raw_data = {}
        participation.team_name = ""
        participation.source_identity_key = None
    for row in challenge_rows:
        anonymous = athlete_repository.get_or_create(
            db, nom=f"Anonyme challenge {row.challenge_id}-{row.bib_number or f'p{row.id}'}",
            prenom="", gender=athlete.gender or "",
        )
        row.athlete_id = anonymous.id
        row.raw_data = {}
    # Le compte du club se relit : un relais peut compter encore par un autre
    # licencié de l'équipe, ou cesser de compter si la personne en était le licencié.
    touched = [link.participation for link in links] + carried
    teammates = {
        athlete_id
        for participation in touched
        for athlete_id in participation_repository.teammate_athlete_ids(db, participation.id)
    }
    tcn_count_repository.recompute_counts_for_tcn(
        db,
        course_ids={participation.course_id for participation in touched},
        athlete_ids=teammates | {participation.athlete_id for participation in touched},
    )
    user_repository.detach_athlete(db, athlete.id)
    athlete_claim_repository.delete_for_athlete(db, athlete.id)
    volunteer_action_repository.delete_for_athlete(db, athlete.id)
    season_validation_repository.delete_for_athlete(db, athlete.id)
    db.expire(athlete)
    athlete_repository.delete(db, athlete)
    return len(carried) + len(links) + len(challenge_rows)


def _remove_club_members(db: Session, nom: str, prenom: str, athlete_ids: set[int]) -> None:
    """La liste des licenciés ne garde ni le nom ni la licence de la personne opposée."""
    key = opposition_key(nom, prenom)
    removed = [
        (member_id, member_athlete_id)
        for member_id, member_last_name, member_first_name, member_athlete_id in club_member_repository.list_identities(db)
        if member_athlete_id in athlete_ids or opposition_key(member_last_name, member_first_name) == key
    ]
    club_member_repository.delete_ids(db, [member_id for member_id, _ in removed])
    # Une ligne rattachée par une variante d'écriture désigne une autre fiche, dont le compte se relit.
    tcn_count_repository.recompute_counts_for_tcn(
        db, athlete_ids={a for _, a in removed if a is not None and a not in athlete_ids}
    )


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
    if requested_on > (today or club_today()):
        raise DomainError("La date de la demande ne peut pas être dans le futur.")
    nom, prenom = _identity(db, athlete_id, nom, prenom)
    athletes = _matching_athletes(db, nom, prenom)
    _remove_club_members(db, nom, prenom, {athlete.id for athlete in athletes})
    anonymised = sum(_anonymise(db, athlete) for athlete in athletes)
    _redact_log(db, nom, prenom)

    digest = identity_hash(nom, prenom)
    opposition = opposition_repository.get_by_hash(db, digest)
    created = opposition is None
    if created:
        opposition = opposition_repository.create(
            db, identity_hash=digest, requested_on=requested_on, applied_by_user_id=actor.id
        )
    opposition.anonymised_count += anonymised
    audit.record(
        db, actor.id, action="opposition.apply", entity_type="opposition", entity_id=opposition.id,
        payload={"requested_on": requested_on.isoformat(), "anonymised_count": anonymised},
    )
    db.commit()
    return opposition, created


def apply_for_member(db: Session, user: User) -> AthleteOpposition:
    """Un adhérent rattaché s'oppose pour lui-même (#1673) ; ses homonymes passent par le club."""
    nom, prenom = _identity(db, user.athlete_id, None, None)
    key = opposition_key(nom, prenom)
    # Limite acceptée : un homonyme licencié sans fiche n'est pas détecté ; la vérification et l'écriture
    # ne sont pas atomiques, un homonyme créé entre les deux par un import concurrent serait inclus.
    licensed_elsewhere = any(
        member_athlete_id not in (None, user.athlete_id) and opposition_key(last_name, first_name) == key
        for _, last_name, first_name, member_athlete_id in club_member_repository.list_identities(db)
    )
    if licensed_elsewhere or preview(db, athlete_id=user.athlete_id).athletes != 1:
        raise DuplicateError(
            "Votre nom est partagé avec une autre personne connue du club. "
            "Écrivez au club pour exercer votre droit d'opposition."
        )
    opposition, _ = apply(db, user, athlete_id=user.athlete_id, requested_on=club_today())
    return opposition


def opposition_view(opposition: AthleteOpposition) -> dict:
    delay_days = (club_today(opposition.applied_at) - opposition.requested_on).days
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
