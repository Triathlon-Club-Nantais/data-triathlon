"""Réclamer un résultat rangé sur une autre fiche (#1637).

Un compte rattaché (#1325) dit « ce résultat est à moi » pour un résultat
validé et individuel d'une autre fiche, typiquement celle d'un homonyme. Jamais
d'office : un responsable valide, et la validation passe par le geste existant
`admin_actions.reassign_participation` (résultat figé contre l'import, fiche
d'origine purgée si elle se vide, journal). La file est celle des rattachements
de fiche (`/admin/rattachements`), en section distincte.
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
from app.models.result_claim import KIND_RESULT, KIND_TEAM, STATUS_PENDING, ResultClaim
from app.models.user import User
from app.repositories import (
    athlete_repository,
    club_member_repository,
    opposition_repository,
    participation_repository,
    result_claim_repository,
)
from app.services import admin_actions, audit

logger = logging.getLogger(__name__)

MAX_PENDING = 5
_ENTITY = "participation"


class NoClaimedAthleteError(DomainError):
    status_code = 409
    message = "Rattachez d'abord votre fiche athlète (« C'est moi » sur votre fiche) pour réclamer un résultat."


class UnclaimableResultError(DomainError):
    status_code = 409
    message = "Ce résultat ne peut pas être réclamé : il est déjà sur votre fiche, en attente de validation, ou d'un relais."


class TooManyClaimsError(DomainError):
    status_code = 409
    message = f"Vous avez déjà {MAX_PENDING} réclamations en attente : attendez la réponse du club."


class CompositionToDecideError(DomainError):
    status_code = 409
    message = (
        "La composition de cette équipe a été posée à la main : composez l'équipe dans "
        "« Attribuer aux équipiers », puis validez la demande."
    )


def _claim_not_pending() -> NotFoundError:
    return NotFoundError("Cette réclamation n'est plus en attente.")


def _claimable(participation: Participation, athlete_id: int, kind: str) -> bool:
    if participation.athlete_id == athlete_id or participation.is_pending_validation:
        return False
    if kind == KIND_TEAM:
        is_relay = participation.is_relay or participation.course.is_relay
        return is_relay and athlete_id not in {link.athlete_id for link in participation.teammate_links}
    return not participation.is_relay


def request_claim(db: Session, user: User, participation_id: int, *, kind: str = KIND_RESULT) -> ResultClaim:
    if user.athlete_id is None:
        raise NoClaimedAthleteError()
    participation = participation_repository.get(db, participation_id)
    if participation is None:
        raise NotFoundError("Résultat introuvable.")
    if not _claimable(participation, user.athlete_id, kind):
        raise UnclaimableResultError()
    existing = result_claim_repository.get_for_participation(db, user.id, participation_id)
    if existing is not None and existing.status == STATUS_PENDING:
        return existing  # un second clic ne la renvoie pas en fin de file
    if result_claim_repository.count_pending_for_user(db, user.id) >= MAX_PENDING:
        raise TooManyClaimsError()
    claim = result_claim_repository.replace_pending(db, user_id=user.id, participation_id=participation_id, kind=kind)
    logger.info("Result claim requested: user=%s participation=%s", user.id, participation_id)
    return claim


def cancel_claim(db: Session, user: User, claim_id: int) -> None:
    claim = result_claim_repository.get_for_user(db, user.id, claim_id)
    if claim is None:
        raise NotFoundError("Réclamation introuvable.")
    result_claim_repository.delete_claim(db, claim)


def is_team_record(athlete: Athlete) -> bool:
    """Fiche d'équipe : un nom sans prénom (même règle que la recherche SQL)."""
    return not athlete.prenom.strip() and bool(athlete.nom.strip())


@dataclass(frozen=True)
class TeamResultHit:
    participation: Participation
    team_name: str
    teammates: list[str]


def search_team_results(db: Session, user: User, term: str) -> list[TeamResultHit]:
    """Relais à rejoindre (#1739), filtrés comme le classement public : rien d'une identité opposée."""
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


def list_mine(db: Session, user: User) -> list[ResultClaim]:
    return result_claim_repository.list_for_user(db, user.id)


def team_composition_with(current: list[Athlete], carrier: Athlete, claimant_id: int) -> list[int] | None:
    """Composition du relais une fois l'adhérent ajouté (#1739), `None` quand l'admin tranche.

    La fiche d'équipe tient lieu du « reste de l'équipe » : l'adhérent la remplace
    tant qu'il reste une vraie personne à ses côtés, sinon il s'y ajoute.
    """
    if not current:
        return [claimant_id, carrier.id] if is_team_record(carrier) else None
    team_records = [mate for mate in current if is_team_record(mate)]
    if not team_records:
        return None
    ids = [mate.id for mate in current]
    if len(team_records) < len(current):
        ids[ids.index(team_records[0].id)] = claimant_id
    else:
        ids.append(claimant_id)
    return ids


def _is_on_team(participation: Participation, athlete_id: int) -> bool:
    return athlete_id == participation.athlete_id or athlete_id in {mate.id for mate in participation.teammates}


def _approve_team(db: Session, claim: ResultClaim, *, actor_id: int) -> None:
    participation, target = claim.participation, claim.user.athlete_id
    # Déjà composée à la main avec l'adhérent : il ne reste qu'à clore la demande.
    if not _is_on_team(participation, target):
        ids = team_composition_with(participation.teammates, participation.athlete, target)
        if ids is None:
            raise CompositionToDecideError()
        admin_actions.set_teammates(db, participation_id=participation.id, teammates=ids, user_id=actor_id)
    participation_id, user_id, claim_id = claim.participation_id, claim.user_id, claim.id
    result_claim_repository.delete_claim(db, claim)
    audit.record(
        db, actor_id, action="result_claim.approve_team", entity_type=_ENTITY, entity_id=participation_id,
        payload={"user_id": user_id, "athlete_id": target, "claim_id": claim_id},
    )


def approve(db: Session, claim_id: int, *, actor_id: int) -> None:
    claim = result_claim_repository.get_pending(db, claim_id)
    if claim is None or claim.user.athlete_id is None:
        raise _claim_not_pending()
    if claim.kind == KIND_TEAM:
        _approve_team(db, claim, actor_id=actor_id)
        return
    participation_id, user_id, target = claim.participation_id, claim.user_id, claim.user.athlete_id
    # Le geste du back-office : verrou de l'épreuve, conflit si la fiche du compte
    # y a déjà un résultat, figement contre l'import, purge de la fiche vidée.
    admin_actions.reassign_participation(db, participation_id=participation_id, athlete_id=target, user_id=actor_id)
    result_claim_repository.delete_claim(db, claim)
    audit.record(
        db, actor_id, action="result_claim.approve", entity_type=_ENTITY, entity_id=participation_id,
        payload={"user_id": user_id, "athlete_id": target, "claim_id": claim_id},
    )


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
    kind: str
    #: Composition actuelle du relais, vide sans composition.
    teammates: list[Athlete]
    #: Composition après validation d'une demande d'équipe ; `None` : l'admin tranche, ou demande de résultat.
    proposed_teammates: list[Athlete] | None
    #: `set_teammates` refuserait la validation (`DuplicateError`).
    claimant_has_result_on_course: bool


def _proposed_teammates(claim: ResultClaim, claimant: Athlete | None) -> list[Athlete] | None:
    participation = claim.participation
    if claim.kind != KIND_TEAM or claimant is None:
        return None
    if _is_on_team(participation, claimant.id):
        return participation.teammates
    ids = team_composition_with(participation.teammates, participation.athlete, claimant.id)
    if ids is None:
        return None
    known = {mate.id: mate for mate in [participation.athlete, *participation.teammates, claimant]}
    return [known[athlete_id] for athlete_id in ids]


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
            kind=claim.kind,
            teammates=claim.participation.teammates,
            proposed_teammates=_proposed_teammates(claim, claimants.get(claim.user.athlete_id)),
            claimant_has_result_on_course=claim.user.athlete_id is not None
            and participation_repository.exists_for_athlete_on_course(
                db, athlete_id=claim.user.athlete_id, course_id=claim.participation.course_id,
            ),
        )
        for claim in claims
    ]
