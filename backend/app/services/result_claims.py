"""Réclamer un résultat rangé sur une autre fiche (#1637).

Un compte rattaché (#1325) dit « ce résultat est à moi » pour un résultat
validé d'une autre fiche, typiquement celle d'un homonyme. Jamais d'office : un
responsable valide, et la validation passe par le geste existant
`admin_actions.reassign_participation` (résultat figé contre l'import, fiche
d'origine purgée si elle se vide, journal). La file est celle des rattachements
de fiche (`/admin/rattachements`), en section distincte.

Un relais (#1739) se réclame aussi : la fiche du compte rejoint sa composition
(#894). Sans composition, elle s'ajoute à côté du porteur, sauf si le porteur
n'est qu'une étiquette d'équipe (sans prénom) : elle la remplace. Avec une
composition, la fiche s'y ajoute en dernier.

Le relais se trouve par son nom d'équipe (`search_team_results`), sans rien
changer au geste de réclamation.
"""
import logging
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.core.exceptions import DomainError, NotFoundError
from app.core.identity import identity_hash
from app.core.season import season_of
from app.core.time import utcnow
from app.models.athlete import Athlete
from app.models.club_member import ClubMember
from app.models.participation import Participation
from app.models.result_claim import STATUS_PENDING, ResultClaim
from app.models.user import User
from app.repositories import (
    athlete_repository,
    club_member_repository,
    opposition_repository,
    participation_repository,
    result_claim_repository,
)
from app.services import admin_actions, audit, opposition_service
from app.services.course_locks import lock_courses_or_409

logger = logging.getLogger(__name__)

MAX_PENDING = 5
_ENTITY = "participation"


class NoClaimedAthleteError(DomainError):
    status_code = 409
    message = "Rattachez d'abord votre fiche athlète (« C'est moi » sur votre fiche) pour réclamer un résultat."


class UnclaimableResultError(DomainError):
    status_code = 409
    message = "Ce résultat ne peut pas être réclamé : il est déjà sur votre fiche, ou vous figurez déjà dans l'équipe."


class TooManyClaimsError(DomainError):
    status_code = 409
    message = f"Vous avez déjà {MAX_PENDING} réclamations en attente : attendez la réponse du club."


def _claim_not_pending() -> NotFoundError:
    return NotFoundError("Cette réclamation n'est plus en attente.")


def request_claim(db: Session, user: User, participation_id: int) -> ResultClaim:
    if user.athlete_id is None:
        raise NoClaimedAthleteError()
    participation = participation_repository.get(db, participation_id)
    # Une saisie en attente ou refusée ne se devine pas : même réponse qu'un id inconnu.
    if participation is None or participation.is_pending_validation:
        raise NotFoundError("Résultat introuvable.")
    if (
        participation.athlete_id == user.athlete_id
        or opposition_service.is_anonymous(participation.athlete.prenom, participation.athlete.nom)
        or user.athlete_id in participation_repository.teammate_athlete_ids(db, participation_id)
    ):
        raise UnclaimableResultError()
    existing = result_claim_repository.get_for_participation(db, user.id, participation_id)
    if existing is not None and existing.status == STATUS_PENDING:
        return existing  # un second clic ne la renvoie pas en fin de file
    if result_claim_repository.count_pending_for_user(db, user.id) >= MAX_PENDING:
        raise TooManyClaimsError()
    claim = result_claim_repository.replace_pending(db, user_id=user.id, participation_id=participation_id)
    logger.info("Result claim requested: user=%s participation=%s", user.id, participation_id)
    return claim


def cancel_claim(db: Session, user: User, claim_id: int) -> None:
    claim = result_claim_repository.get_for_user(db, user.id, claim_id)
    if claim is None:
        raise NotFoundError("Réclamation introuvable.")
    result_claim_repository.delete_claim(db, claim)


def list_mine(db: Session, user: User) -> list[ResultClaim]:
    return result_claim_repository.list_for_user(db, user.id)


@dataclass(frozen=True)
class TeamResultHit:
    participation: Participation
    team_name: str
    teammates: list[str]


def search_team_results(db: Session, user: User, term: str) -> list[TeamResultHit]:
    """Relais à rejoindre (#1773), filtrés comme le classement public : rien d'une identité opposée."""
    if user.athlete_id is None:
        return []
    rows = participation_repository.search_team_results(db, term=term, exclude_athlete_id=user.athlete_id)
    opposed = opposition_repository.all_hashes(db)
    hits = []
    for row in rows:
        people = [row.athlete, *row.teammates]
        if any(identity_hash(person.nom, person.prenom) in opposed for person in people):
            continue
        hits.append(TeamResultHit(
            participation=row,
            team_name=row.team_name or row.athlete.nom,
            teammates=[f"{mate.prenom} {mate.nom}".strip() for mate in row.teammates],
        ))
    return hits


def approve(db: Session, claim_id: int, *, actor_id: int) -> None:
    claim = result_claim_repository.get_pending(db, claim_id)
    if claim is None or claim.user.athlete_id is None:
        raise _claim_not_pending()
    participation, target = claim.participation, claim.user.athlete_id
    lock_courses_or_409(db, participation.course_id)
    athlete = participation.athlete
    if opposition_service.is_anonymous(athlete.prenom, athlete.nom):  # opposition appliquée depuis le dépôt
        raise UnclaimableResultError()
    payload = {"user_id": claim.user_id, "athlete_id": target, "claim_id": claim_id}
    if participation.counts_as_relay:
        payload |= _join_relay(db, participation, target, actor_id)
    else:
        _move(db, participation.id, target, actor_id)
    result_claim_repository.delete_claim(db, claim)
    audit.record(
        db, actor_id, action="result_claim.approve", entity_type=_ENTITY, entity_id=participation.id,
        payload=payload,
    )


def _move(db: Session, participation_id: int, target: int, actor_id: int) -> None:
    # Le geste du back-office : verrou de l'épreuve, conflit si la fiche du compte
    # y a déjà un résultat, figement contre l'import, purge de la fiche vidée.
    admin_actions.reassign_participation(db, participation_id=participation_id, athlete_id=target, user_id=actor_id)


def _join_relay(db: Session, participation: Participation, target: int, actor_id: int) -> dict:
    """La fiche du membre rejoint l'équipe ; rend ce que le journal doit en garder."""
    team = participation_repository.teammate_athlete_ids(db, participation.id)
    if team:
        if target in team:
            return {"mode": "team_completed"}
        admin_actions.set_teammates(
            db, participation_id=participation.id, teammates=[*team, target], user_id=actor_id
        )
        return {"mode": "joined_team"}
    carrier = participation.athlete
    # `nom`/`prenom` groupés : l'opposition (`_redact_log`) efface ce couple du journal.
    trace = {"carrier": {"nom": carrier.nom, "prenom": carrier.prenom}, "former_team_name": participation.team_name}
    if carrier.prenom:
        admin_actions.set_teammates(
            db, participation_id=participation.id, teammates=[carrier.id, target], user_id=actor_id
        )
        return {"mode": "joined_with_carrier", **trace}
    # Sans prénom, le porteur n'est qu'une étiquette d'équipe : le membre la remplace, son
    # nom reste comme nom d'équipe (même formule que `set_teammates`) pour apparier l'import.
    participation.team_name = participation.team_name or carrier.nom
    _move(db, participation.id, target, actor_id)
    participation_repository.replace_teammates(db, participation, [target])
    return {"mode": "replaced_team_label", **trace}


def reject(db: Session, claim_id: int, *, actor_id: int) -> None:
    claim = result_claim_repository.get_pending(db, claim_id)
    if claim is None:
        raise _claim_not_pending()
    result_claim_repository.reject(db, claim, now=utcnow())
    audit.record(
        db, actor_id, action="result_claim.reject", entity_type=_ENTITY, entity_id=claim.participation_id,
        payload={"user_id": claim.user_id, "claim_id": claim_id},
    )


@dataclass(frozen=True)
class ResultClaimReview:
    """Une réclamation de la file et ce qui aide à la juger."""

    claim: ResultClaim
    user: User
    participation: Participation
    current_athlete: Athlete
    #: Résultats de la fiche actuelle, celui-ci compris : 1 veut dire qu'elle sera purgée.
    current_athlete_results: int
    claimant_athlete: Athlete | None
    claimant_licensee: ClubMember | None


def list_pending_with_hints(db: Session, today: date) -> list[ResultClaimReview]:
    claims = result_claim_repository.list_pending(db)
    claimant_ids = [claim.user.athlete_id for claim in claims if claim.user.athlete_id is not None]
    claimants = athlete_repository.get_many(db, claimant_ids)
    licensees = club_member_repository.linked_by_athlete(db, season_of(today), claimant_ids)
    return [
        ResultClaimReview(
            claim=claim,
            user=claim.user,
            participation=claim.participation,
            current_athlete=claim.participation.athlete,
            current_athlete_results=participation_repository.count_for_athlete(db, claim.participation.athlete_id),
            claimant_athlete=claimants.get(claim.user.athlete_id),
            claimant_licensee=licensees.get(claim.user.athlete_id),
        )
        for claim in claims
    ]
