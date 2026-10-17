"""Adresses d'adhérents par saison (#1334) : import AssoConnect, ajout, retrait.

Seule la colonne d'adresses du fichier est lue (minimisation). Une adresse est
valide au sens d'`allowed_emails.validate_email`, la seule définition du dépôt.

Ne commite pas : le routeur ou la commande porte la transaction.
"""
from dataclasses import dataclass
from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError, NotFoundError
from app.core.season import SEASON_MAX, SEASON_MIN, SeasonOutOfRangeError
from app.models.member_email import MemberEmail
from app.repositories import member_email_repository
from app.services import audit, sheet_source
from app.services.auth.allowed_emails import InvalidEmailError, validate_email

_SEASON_ENTITY = "member_emails_season"
_ENTRY_ENTITY = "member_email"

_EMAIL_HEADERS = {
    "email",
    "mail",
    "courriel",
    "adressemail",
    "adresseemail",
    "emailaddress",
    "adresseelectronique",
    "adressedecourriel",
}


class MissingEmailColumnError(DomainError):
    status_code = 422
    message = "Colonne d'adresses e-mail introuvable dans ce fichier (« Email », « E-mail » ou « Courriel »)."


class NoValidEmailError(DomainError):
    status_code = 422
    message = "Aucune adresse e-mail valide dans ce fichier : la liste n'a pas été modifiée."


class ConcurrentImportError(DomainError):
    status_code = 409
    message = "La liste a été modifiée pendant l'import, réessayez."


class AlreadyListedError(DomainError):
    status_code = 409
    message = "Cette adresse figure déjà dans la liste de la saison."


@dataclass(frozen=True)
class MemberEmailsImportReport:
    season: int
    added: int
    removed: int
    unchanged: int
    ignored: int


@dataclass(frozen=True)
class MemberEmailsSeason:
    season: int
    counting_season: int
    seasons: list[int]
    entries: list[MemberEmail]


def _check_season(season: int) -> None:
    if not SEASON_MIN <= season <= SEASON_MAX:
        raise SeasonOutOfRangeError


def _validated(email: str) -> str:
    """L'adresse normalisée, ou `InvalidEmailError`. Seule une adresse nue passe :
    `validate_email` accepte la forme « Nom <adresse> », qui serait rangée telle quelle."""
    normalized = member_email_repository.normalize(email)
    validate_email(normalized)
    if any(c.isspace() or c in "<>" for c in normalized):
        raise InvalidEmailError(
            f"« {email.strip()} » n'est pas une adresse électronique valide. "
            "Forme attendue : prenom.nom@exemple.fr."
        )
    return normalized


def _is_valid(email: str) -> bool:
    try:
        _validated(email)
    except InvalidEmailError:
        return False
    return True


def list_season(db: Session, season: int, today: date) -> MemberEmailsSeason:
    return MemberEmailsSeason(
        season=season,
        counting_season=member_email_repository.counting_season(db, today),
        seasons=member_email_repository.seasons(db),
        entries=member_email_repository.list_season(db, season),
    )


def import_file(
    db: Session, *, season: int, content: bytes, filename: str, user_id: int | None
) -> MemberEmailsImportReport:
    _check_season(season)
    headers, lines = sheet_source.read_table(content, filename)
    at = sheet_source.column_index(headers, _EMAIL_HEADERS)
    if at is None:
        raise MissingEmailColumnError
    emails: set[str] = set()
    ignored = 0
    for line in lines:
        if not any(line):
            continue
        email = member_email_repository.normalize(line[at] if at < len(line) else "")
        if _is_valid(email):
            emails.add(email)
        else:
            ignored += 1
    if not emails:
        raise NoValidEmailError
    try:
        added, removed, unchanged = member_email_repository.replace_imported(db, season, emails)
    except IntegrityError as error:
        raise ConcurrentImportError from error
    report = MemberEmailsImportReport(season, added, removed, unchanged, ignored)
    audit.record(
        db, user_id, action="member_emails.import", entity_type=_SEASON_ENTITY, entity_id=season,
        payload={"added": added, "removed": removed, "unchanged": unchanged, "ignored": ignored},
    )
    return report


def add(db: Session, *, email: str, season: int, user_id: int | None) -> MemberEmail:
    _check_season(season)
    entry = member_email_repository.add_manual(db, _validated(email), season)
    if entry is None:
        raise AlreadyListedError
    audit.record(
        db, user_id, action="member_emails.add", entity_type=_ENTRY_ENTITY, entity_id=entry.id,
        payload={"season": season},
    )
    return entry


def remove(db: Session, *, entry_id: int, user_id: int | None) -> None:
    entry = member_email_repository.remove(db, entry_id)
    if entry is None:
        raise NotFoundError("Cette adresse ne figure pas dans la liste.")
    audit.record(
        db, user_id, action="member_emails.remove", entity_type=_ENTRY_ENTITY, entity_id=entry_id,
        payload={"season": entry.season},
    )
