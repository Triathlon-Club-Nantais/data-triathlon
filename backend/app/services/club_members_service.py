"""Licenciés du club par saison (#1202) : synchro FFTri, fichier, rattachement.

Un licencié rattaché à une fiche fait compter pour le club les résultats de
cette fiche sur la saison de sa licence (`tcn_count_repository`). Chaque
écriture se termine donc par un recalcul des compteurs.

Ne commite pas : le routeur ou la commande porte la transaction.
"""
import logging
import unicodedata
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.athlete_identity import athlete_identity_keys
from app.core.exceptions import DomainError, NotFoundError
from app.core.gender import normalize_gender
from app.core.identity import identity_hash
from app.core.season import SEASON_MAX, SEASON_MIN
from app.models.club_member import (
    LINK_AMBIGUOUS,
    LINK_AUTO,
    LINK_MANUAL,
    LINK_UNLINKED,
    LINKED,
    SOURCE_FFTRI,
    SOURCE_FILE,
    ClubMember,
)
from app.repositories import (
    athlete_alias_repository,
    athlete_repository,
    club_member_repository,
    opposition_repository,
    tcn_count_repository,
)
from app.scrapers import fftri_club_members
from app.scrapers.fftri_club_members import RosterMember
from app.services import audit, sheet_source

logger = logging.getLogger(__name__)

_SEASON_ENTITY = "club_members_season"
_MEMBER_ENTITY = "club_member"

_NOM_HEADERS = {"nom", "nomdefamille", "lastname"}
_PRENOM_HEADERS = {"prenom", "firstname"}
_GENDER_HEADERS = {"sexe", "genre", "gender"}
_LICENCE_HEADERS = {"licence", "numerodelicence", "nlicence", "license"}


class RosterUnavailableError(DomainError):
    status_code = 502
    message = "La liste des licenciés de la FFTri est illisible ou injoignable. Réessayez plus tard."


class MissingMemberColumnsError(DomainError):
    status_code = 422
    message = "Colonnes « Nom » et « Prénom » introuvables dans ce fichier."


class SeasonOutOfRangeError(DomainError):
    status_code = 422
    message = "Saison hors de la plage acceptée."


@dataclass(frozen=True)
class MembersSyncReport:
    season: int
    total: int
    linked: int
    unlinked: int
    ambiguous: int


def report_of(season: int, members: list[ClubMember]) -> MembersSyncReport:
    statuses = [m.link_status for m in members]
    return MembersSyncReport(
        season=season,
        total=len(members),
        linked=sum(s in LINKED for s in statuses),
        unlinked=statuses.count(LINK_UNLINKED),
        ambiguous=statuses.count(LINK_AMBIGUOUS),
    )


def list_season(db: Session, season: int) -> list[ClubMember]:
    return club_member_repository.list_season(db, season)


def seasons(db: Session) -> list[int]:
    return club_member_repository.seasons(db)


def _identity(member: ClubMember | RosterMember) -> tuple:
    if member.licence_id:
        return ("licence", member.licence_id)
    return ("name", athlete_identity_keys(member.nom, member.prenom))


def _deduplicated(members: list[RosterMember]) -> list[RosterMember]:
    seen: dict[tuple, RosterMember] = {}
    for member in members:
        seen.setdefault(_identity(member), member)
    return list(seen.values())


def _auto_match(by_key: dict, by_alias: dict, key: tuple) -> tuple[int | None, str]:
    candidates = {a.id for a in by_key.get(key, [])}
    if key in by_alias:
        candidates.add(by_alias[key].id)
    if len(candidates) == 1:
        return candidates.pop(), LINK_AUTO
    return None, LINK_AMBIGUOUS if candidates else LINK_UNLINKED


def _replace(db: Session, season: int, incoming: list[RosterMember], source: str) -> list[ClubMember]:
    """Remplace la saison, rattache, et garde les rattachements faits à la main.

    Une personne inscrite au registre des oppositions (#334) n'y entre pas.
    """
    opposed = opposition_repository.all_hashes(db)
    incoming = [m for m in incoming if identity_hash(m.nom, m.prenom) not in opposed]
    previous = club_member_repository.list_season(db, season)
    manual = {
        _identity(m): m.athlete_id
        for m in previous
        if m.link_status == LINK_MANUAL and m.athlete_id is not None
    }
    touched_athletes = {m.athlete_id for m in previous if m.athlete_id is not None}
    keys = [athlete_identity_keys(m.nom, m.prenom) for m in incoming]
    by_key = athlete_repository.get_all_ranks_by_identity_keys(db, keys)
    by_alias = athlete_alias_repository.get_by_keys_batch(db, keys)

    rows: list[ClubMember] = []
    # L'index d'unicité ne couvre pas les lignes rattachées sans licence : une
    # fiche n'en garde qu'une par saison.
    licence_less_linked: set[int] = set()
    for member, key in zip(incoming, keys, strict=True):
        athlete_id, status = manual.get(_identity(member)), LINK_MANUAL
        if athlete_id is None:
            athlete_id, status = _auto_match(by_key, by_alias, key)
        if athlete_id is not None and not member.licence_id:
            if athlete_id in licence_less_linked:
                continue
            licence_less_linked.add(athlete_id)
        rows.append(ClubMember(
            season=season, licence_id=member.licence_id, nom=member.nom, prenom=member.prenom,
            gender=member.gender, athlete_id=athlete_id, link_status=status, source=source,
        ))
    club_member_repository.replace_season(db, season, rows)
    touched_athletes.update(row.athlete_id for row in rows if row.athlete_id is not None)
    tcn_count_repository.recompute_counts_for_tcn(db, athlete_ids=touched_athletes)
    return rows


def sync_from_fftri(db: Session, *, user_id: int | None) -> MembersSyncReport:
    try:
        roster = fftri_club_members.fetch_club_roster(fftri_club_members.CLUB_URL)
    except Exception as error:
        logger.warning("FFTri roster unavailable", exc_info=True)
        raise RosterUnavailableError from error
    season = roster.licence_year - 1
    rows = _replace(db, season, _deduplicated(roster.members), SOURCE_FFTRI)
    audit.record(db, user_id, action="club_members.sync", entity_type=_SEASON_ENTITY, entity_id=season)
    return report_of(season, rows)


def _header_key(header: str) -> str:
    decomposed = unicodedata.normalize("NFKD", header)
    return "".join(c for c in decomposed if c.isalnum()).casefold()


def _column(headers: list[str], accepted: set[str]) -> int | None:
    return next((i for i, h in enumerate(headers) if _header_key(h) in accepted), None)


def import_file(
    db: Session, *, season: int, content: bytes, filename: str, user_id: int | None
) -> MembersSyncReport:
    if not SEASON_MIN <= season <= SEASON_MAX:
        raise SeasonOutOfRangeError
    headers, lines = sheet_source.read_table(content, filename)
    nom_at, prenom_at = _column(headers, _NOM_HEADERS), _column(headers, _PRENOM_HEADERS)
    if nom_at is None or prenom_at is None:
        raise MissingMemberColumnsError
    gender_at, licence_at = _column(headers, _GENDER_HEADERS), _column(headers, _LICENCE_HEADERS)

    def cell(line: list[str], at: int | None) -> str:
        return line[at].strip() if at is not None and at < len(line) else ""

    members = [
        RosterMember(
            nom=cell(line, nom_at),
            prenom=cell(line, prenom_at),
            gender=normalize_gender(cell(line, gender_at)),
            licence_id=cell(line, licence_at) or None,
        )
        for line in lines
        if cell(line, nom_at)
    ]
    rows = _replace(db, season, _deduplicated(members), SOURCE_FILE)
    audit.record(db, user_id, action="club_members.import", entity_type=_SEASON_ENTITY, entity_id=season)
    return report_of(season, rows)


def link_member(db: Session, *, member_id: int, athlete_id: int, user_id: int | None) -> ClubMember:
    member = club_member_repository.get(db, member_id)
    if member is None:
        raise NotFoundError("Ce licencié n'existe pas.")
    if athlete_repository.get(db, athlete_id) is None:
        raise NotFoundError("Cette fiche d'athlète n'existe pas.")
    touched = {athlete_id}
    if member.athlete_id is not None:
        touched.add(member.athlete_id)
    member.athlete_id, member.link_status = athlete_id, LINK_MANUAL
    db.flush()
    tcn_count_repository.recompute_counts_for_tcn(db, athlete_ids=touched)
    audit.record(
        db, user_id, action="club_member.link", entity_type=_MEMBER_ENTITY, entity_id=member.id,
        payload={"athlete_id": athlete_id},
    )
    return member


class NotManuallyLinkedError(DomainError):
    status_code = 400
    message = "Ce licencié n'a pas été rattaché à la main : il n'y a rien à annuler."


def unlink_member(db: Session, *, member_id: int, user_id: int | None) -> ClubMember:
    """Annule un rattachement manuel (#1243) : le licencié reprend le rattachement
    automatique, comme à la prochaine relecture, et revient à rattacher s'il n'en a pas."""
    member = club_member_repository.get(db, member_id)
    if member is None:
        raise NotFoundError("Ce licencié n'existe pas.")
    if member.link_status != LINK_MANUAL:
        raise NotManuallyLinkedError
    previous = member.athlete_id
    key = athlete_identity_keys(member.nom, member.prenom)
    athlete_id, status = _auto_match(
        athlete_repository.get_all_ranks_by_identity_keys(db, [key]),
        athlete_alias_repository.get_by_keys_batch(db, [key]),
        key,
    )
    # Même règle que `_replace` : une fiche ne garde qu'une ligne sans licence par saison.
    if athlete_id is not None and not member.licence_id and club_member_repository.has_licence_less_link(
        db, season=member.season, athlete_id=athlete_id, except_id=member.id
    ):
        athlete_id, status = None, LINK_UNLINKED
    member.athlete_id, member.link_status = athlete_id, status
    db.flush()
    tcn_count_repository.recompute_counts_for_tcn(
        db, athlete_ids={i for i in (previous, member.athlete_id) if i is not None}
    )
    audit.record(
        db, user_id, action="club_member.unlink", entity_type=_MEMBER_ENTITY, entity_id=member.id,
        payload={"athlete_id": previous},
    )
    return member
