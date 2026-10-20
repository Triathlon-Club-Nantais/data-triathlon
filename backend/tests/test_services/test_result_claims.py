"""A claimed member asks for a result filed under another record (#1637)."""
from datetime import date

import pytest

from app.core.exceptions import DomainError, DuplicateError, NotFoundError
from app.models.admin_action_log import AdminActionLog
from app.models.athlete import Athlete
from app.models.course import Course
from app.models.participation import Participation, ParticipationTeammate
from app.models.result_claim import (
    KIND_RESULT,
    KIND_TEAM,
    STATUS_PENDING,
    STATUS_REJECTED,
    ResultClaim,
)
from app.models.user import SYSTEM_USER_EMAIL
from app.repositories import user_repository
from app.services import athlete_claims, result_claims
from app.services.auth import accounts

_NUMBER = iter(range(1, 10_000))


def _athlete(db, nom="Martin", prenom="Léa") -> Athlete:
    athlete = Athlete(nom=nom, prenom=prenom)
    db.add(athlete)
    db.flush()
    return athlete


def _result(db, athlete, **extra) -> Participation:
    number = next(_NUMBER)
    course = Course(name=f"Épreuve {number}", event_date=date(2026, 6, 7), event_type="triathlon-m",
                    is_relay=extra.pop("course_relay", False))
    db.add(course)
    db.flush()
    row = Participation(course_id=course.id, athlete_id=athlete.id, bib_number=str(number), total_time="2:30:00",
                        status="finisher", **extra)
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def lea(db_session):
    user = user_repository.create(db_session, email="lea@exemple.fr", display_name="Léa M.")
    user.athlete_id = _athlete(db_session).id
    db_session.flush()
    return user


@pytest.fixture
def reviewer(db_session):
    return user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")


@pytest.fixture
def homonym(db_session):
    return _athlete(db_session, prenom="Léa", nom="Martin-Homonyme")


def test_a_request_is_pending(db_session, lea, homonym):
    result = _result(db_session, homonym)

    claim = result_claims.request_claim(db_session, lea, result.id)

    assert (claim.participation_id, claim.status) == (result.id, STATUS_PENDING)
    assert result.athlete_id == homonym.id


@pytest.mark.parametrize("case", ["own", "pending", "relay", "relay_course", "unknown"])
def test_a_result_that_cannot_be_claimed_is_refused(db_session, lea, homonym, case):
    if case == "own":
        target = _result(db_session, db_session.get(Athlete, lea.athlete_id)).id
    elif case == "pending":
        target = _result(db_session, homonym, is_pending_validation=True).id
    elif case == "relay":
        target = _result(db_session, homonym, is_relay=True).id
    elif case == "relay_course":
        target = _result(db_session, homonym, course_relay=True).id
    else:
        target = 999_999

    with pytest.raises((NotFoundError, result_claims.UnclaimableResultError)):
        result_claims.request_claim(db_session, lea, target)


def test_a_request_needs_a_claimed_athlete(db_session, homonym):
    bare = user_repository.create(db_session, email="bare@exemple.fr", display_name="")

    with pytest.raises(result_claims.NoClaimedAthleteError):
        result_claims.request_claim(db_session, bare, _result(db_session, homonym).id)


def test_five_pending_claims_at_most(db_session, lea, homonym):
    for _ in range(result_claims.MAX_PENDING):
        result_claims.request_claim(db_session, lea, _result(db_session, homonym).id)

    with pytest.raises(result_claims.TooManyClaimsError):
        result_claims.request_claim(db_session, lea, _result(db_session, homonym).id)


def test_a_rejected_claim_can_be_asked_again(db_session, lea, homonym, reviewer):
    result = _result(db_session, homonym)
    claim = result_claims.request_claim(db_session, lea, result.id)
    result_claims.reject(db_session, claim.id, actor_id=reviewer.id)

    again = result_claims.request_claim(db_session, lea, result.id)

    assert db_session.query(ResultClaim).count() == 1
    assert (again.status, again.decided_at) == (STATUS_PENDING, None)


def test_cancel_and_list_mine(db_session, lea, homonym):
    first = result_claims.request_claim(db_session, lea, _result(db_session, homonym).id)
    second = result_claims.request_claim(db_session, lea, _result(db_session, homonym).id)

    result_claims.cancel_claim(db_session, lea, first.id)

    assert [c.id for c in result_claims.list_mine(db_session, lea)] == [second.id]
    with pytest.raises(NotFoundError):
        result_claims.cancel_claim(db_session, user_repository.create(db_session, email="x@x.fr"), second.id)


def test_approve_moves_the_result_to_the_member_and_logs(db_session, lea, homonym, reviewer):
    result = _result(db_session, homonym)
    _result(db_session, homonym)  # the homonym keeps another result, so its record survives
    claim = result_claims.request_claim(db_session, lea, result.id)

    result_claims.approve(db_session, claim.id, actor_id=reviewer.id)

    db_session.refresh(result)
    assert (result.athlete_id, result.athlete_locked) == (lea.athlete_id, True)
    assert db_session.query(ResultClaim).count() == 0
    actions = {log.action for log in db_session.query(AdminActionLog)}
    assert {"participation.reassign", "result_claim.approve"} <= actions


def test_approve_purges_the_record_it_empties(db_session, lea, homonym, reviewer):
    result = _result(db_session, homonym)
    claim = result_claims.request_claim(db_session, lea, result.id)

    result_claims.approve(db_session, claim.id, actor_id=reviewer.id)

    assert db_session.get(Athlete, homonym.id) is None


def test_approve_is_refused_when_the_member_already_has_a_result_on_that_race(db_session, lea, homonym, reviewer):
    result = _result(db_session, homonym)
    db_session.add(Participation(course_id=result.course_id, athlete_id=lea.athlete_id, bib_number="X1",
                                 total_time="2:40:00", status="finisher"))
    db_session.flush()
    claim = result_claims.request_claim(db_session, lea, result.id)

    with pytest.raises(DomainError):
        result_claims.approve(db_session, claim.id, actor_id=reviewer.id)


def test_reject_leaves_the_result_and_logs(db_session, lea, homonym, reviewer):
    result = _result(db_session, homonym)
    claim = result_claims.request_claim(db_session, lea, result.id)

    result_claims.reject(db_session, claim.id, actor_id=reviewer.id)

    assert result.athlete_id == homonym.id
    assert claim.status == STATUS_REJECTED
    assert db_session.query(AdminActionLog).one().action == "result_claim.reject"
    with pytest.raises(NotFoundError):
        result_claims.approve(db_session, claim.id, actor_id=reviewer.id)


def test_the_queue_carries_its_hints(db_session, lea, homonym, reviewer):
    result = _result(db_session, homonym, club="AUTRE CLUB", category="SEF")
    _result(db_session, homonym)
    result_claims.request_claim(db_session, lea, result.id)

    (review,) = result_claims.list_pending_with_hints(db_session, date(2026, 10, 19))

    assert (review.participation.id, review.current_athlete.id, review.current_athlete_results) == (
        result.id, homonym.id, 2,
    )
    assert (review.user.id, review.claimant_athlete.id) == (lea.id, lea.athlete_id)


def test_asking_again_for_a_pending_claim_keeps_it_as_is(db_session, lea, homonym):
    """Review: a second click must not move the claim to the back of the queue,
    nor be refused at the cap."""
    claims = [result_claims.request_claim(db_session, lea, _result(db_session, homonym).id)
              for _ in range(result_claims.MAX_PENDING)]
    first = claims[0]
    created_at = first.created_at

    again = result_claims.request_claim(db_session, lea, first.participation_id)

    assert (again.id, again.created_at) == (first.id, created_at)


@pytest.mark.parametrize("change", ["self_detach", "club_detach"])
def test_changing_the_link_drops_the_claims_made_for_the_old_record(db_session, lea, homonym, reviewer, change):
    """Review: a claim targets the record linked when it was made; once that link
    goes, approving it would move the result elsewhere."""
    result_claims.request_claim(db_session, lea, _result(db_session, homonym).id)

    if change == "self_detach":
        athlete_claims.detach(db_session, lea)
    else:
        athlete_claims.admin_detach(db_session, lea.id, actor_id=reviewer.id)

    assert db_session.query(ResultClaim).count() == 0


def test_claims_go_with_the_account(db_session, lea, homonym):
    user_repository.create(db_session, email=SYSTEM_USER_EMAIL, display_name="")
    claim = result_claims.request_claim(db_session, lea, _result(db_session, homonym).id)

    accounts.delete_account(db_session, lea, origin="request")

    assert db_session.get(ResultClaim, claim.id) is None


def test_a_claim_is_a_result_claim_by_default(db_session, lea, homonym):
    claim = result_claims.request_claim(db_session, lea, _result(db_session, homonym).id)

    assert claim.kind == KIND_RESULT


def test_a_member_asks_to_join_a_team_result(db_session, lea):
    team = _athlete(db_session, nom="LES MOLLETS D'ACIER", prenom="")
    relay = _result(db_session, team, is_relay=True)

    claim = result_claims.request_claim(db_session, lea, relay.id, kind=KIND_TEAM)

    assert (claim.kind, claim.status) == (KIND_TEAM, STATUS_PENDING)
    assert relay.athlete_id == team.id


def test_a_team_claim_accepts_a_relay_flagged_on_the_course_only(db_session, lea):
    team = _athlete(db_session, nom="LES MOLLETS D'ACIER", prenom="")
    relay = _result(db_session, team, course_relay=True)

    claim = result_claims.request_claim(db_session, lea, relay.id, kind=KIND_TEAM)

    assert claim.kind == KIND_TEAM


@pytest.mark.parametrize("case", ["not_relay", "pending", "already_carrier", "already_teammate", "person_carrier"])
def test_a_team_claim_is_refused(db_session, lea, case):
    team = _athlete(db_session, nom="LES MOLLETS D'ACIER", prenom="")
    if case == "not_relay":
        target = _result(db_session, team)
    elif case == "person_carrier":
        # Outside the search: a relay split across person records, without a composition.
        target = _result(db_session, _athlete(db_session, nom="DURAND", prenom="Paul"), is_relay=True)
    elif case == "pending":
        target = _result(db_session, team, is_relay=True, is_pending_validation=True)
    elif case == "already_carrier":
        target = _result(db_session, db_session.get(Athlete, lea.athlete_id), is_relay=True)
    else:
        target = _result(db_session, team, is_relay=True)
        db_session.add(ParticipationTeammate(participation_id=target.id, athlete_id=lea.athlete_id, position=0))
        db_session.flush()
        db_session.refresh(target)

    with pytest.raises(result_claims.UnclaimableResultError):
        result_claims.request_claim(db_session, lea, target.id, kind=KIND_TEAM)


def test_a_second_click_on_a_team_claim_keeps_its_place(db_session, lea):
    relay = _result(db_session, _athlete(db_session, nom="LES MOLLETS D'ACIER", prenom=""), is_relay=True)
    first = result_claims.request_claim(db_session, lea, relay.id, kind=KIND_TEAM)

    again = result_claims.request_claim(db_session, lea, relay.id, kind=KIND_TEAM)

    assert again.id == first.id
    assert db_session.query(ResultClaim).count() == 1


def test_team_and_result_claims_share_the_pending_ceiling(db_session, lea, homonym):
    for _ in range(result_claims.MAX_PENDING - 1):
        result_claims.request_claim(db_session, lea, _result(db_session, homonym).id)
    relay = _result(db_session, _athlete(db_session, nom="LES MOLLETS D'ACIER", prenom=""), is_relay=True)
    result_claims.request_claim(db_session, lea, relay.id, kind=KIND_TEAM)
    other = _result(db_session, _athlete(db_session, nom="LES AUTRES", prenom=""), is_relay=True)

    with pytest.raises(result_claims.TooManyClaimsError):
        result_claims.request_claim(db_session, lea, other.id, kind=KIND_TEAM)


def test_asking_again_after_a_rejection_overwrites_the_kind(db_session, lea):
    """A relay cannot be a valid `result` claim, so a rejected row of that kind is planted directly."""
    relay = _result(db_session, _athlete(db_session, nom="LES MOLLETS D'ACIER", prenom=""), is_relay=True)
    db_session.add(ResultClaim(user_id=lea.id, participation_id=relay.id, kind=KIND_RESULT, status=STATUS_REJECTED))
    db_session.flush()

    again = result_claims.request_claim(db_session, lea, relay.id, kind=KIND_TEAM)

    assert db_session.query(ResultClaim).count() == 1
    assert (again.kind, again.status) == (KIND_TEAM, STATUS_PENDING)


def _team(db, nom="LES MOLLETS D'ACIER") -> Athlete:
    return _athlete(db, nom=nom, prenom="")


def _compose(db, row, *members: Athlete) -> None:
    """Plant a relay composition directly: the first member carries the result."""
    row.athlete_id = members[0].id
    for position, member in enumerate(members):
        db.add(ParticipationTeammate(participation_id=row.id, athlete_id=member.id, position=position))
    db.flush()
    db.refresh(row)


def _composition(db, row) -> list[int]:
    db.refresh(row)
    return [link.athlete_id for link in row.teammate_links]


_CLAIMANT = 99
_A = Athlete(id=1, nom="DURAND", prenom="Paul")
_B = Athlete(id=2, nom="PETIT", prenom="Zoé")
_T = Athlete(id=10, nom="LES MOLLETS D'ACIER", prenom="")
_T2 = Athlete(id=11, nom="LES AUTRES", prenom=" ")


@pytest.mark.parametrize(("current", "carrier", "expected"), [
    ([], _T, [_CLAIMANT, _T.id]),
    ([], _A, None),
    ([_A, _T], _A, [_A.id, _CLAIMANT]),
    ([_T, _A], _T, [_CLAIMANT, _A.id]),
    ([_A, _B], _A, None),
    ([_T, _T2], _T, [_T.id, _T2.id, _CLAIMANT]),
])
def test_team_composition_with(current, carrier, expected):
    assert result_claims.team_composition_with(current, carrier, _CLAIMANT) == expected


def test_approving_a_first_team_claim_keeps_the_team_record(db_session, lea, reviewer):
    team = _team(db_session)
    relay = _result(db_session, team, is_relay=True)
    claim = result_claims.request_claim(db_session, lea, relay.id, kind=KIND_TEAM)

    result_claims.approve(db_session, claim.id, actor_id=reviewer.id)

    assert _composition(db_session, relay) == [lea.athlete_id, team.id]
    assert (relay.athlete_id, relay.team_name) == (lea.athlete_id, "LES MOLLETS D'ACIER")
    assert db_session.get(Athlete, team.id) is not None
    assert db_session.query(ResultClaim).count() == 0
    log = db_session.query(AdminActionLog).filter_by(action="result_claim.approve_team").one()
    assert (log.entity_type, log.entity_id) == ("participation", relay.id)


def test_approving_the_partner_replaces_the_team_record(db_session, lea, reviewer):
    partner, team = _athlete(db_session, nom="DURAND", prenom="Paul"), _team(db_session)
    relay = _result(db_session, team, is_relay=True, team_name="LES MOLLETS D'ACIER")
    _compose(db_session, relay, partner, team)
    claim = result_claims.request_claim(db_session, lea, relay.id, kind=KIND_TEAM)

    result_claims.approve(db_session, claim.id, actor_id=reviewer.id)

    assert _composition(db_session, relay) == [partner.id, lea.athlete_id]
    assert db_session.get(Athlete, team.id) is None


def test_approving_a_hand_composed_team_asks_the_admin(db_session, lea, reviewer):
    first, second = _athlete(db_session, nom="DURAND", prenom="Paul"), _athlete(db_session, nom="PETIT", prenom="Zoé")
    relay = _result(db_session, first, is_relay=True)
    _compose(db_session, relay, first, second)
    claim = result_claims.request_claim(db_session, lea, relay.id, kind=KIND_TEAM)

    with pytest.raises(result_claims.CompositionToDecideError) as refused:
        result_claims.approve(db_session, claim.id, actor_id=reviewer.id)

    assert refused.value.status_code == 409
    assert "« Composer l'équipe »" in refused.value.message
    assert "« Clore la demande »" in refused.value.message
    assert claim.status == STATUS_PENDING
    assert _composition(db_session, relay) == [first.id, second.id]


def test_approving_after_the_admin_added_the_member_closes_the_claim(db_session, lea, reviewer):
    partner = _athlete(db_session, nom="DURAND", prenom="Paul")
    relay = _result(db_session, _team(db_session), is_relay=True)
    claim = result_claims.request_claim(db_session, lea, relay.id, kind=KIND_TEAM)
    _compose(db_session, relay, partner, db_session.get(Athlete, lea.athlete_id))

    result_claims.approve(db_session, claim.id, actor_id=reviewer.id)

    assert db_session.query(ResultClaim).count() == 0
    assert _composition(db_session, relay) == [partner.id, lea.athlete_id]
    actions = {log.action for log in db_session.query(AdminActionLog)}
    assert "participation.set_teammates" not in actions


def test_approving_refuses_a_member_who_already_ran_the_course(db_session, lea, reviewer):
    team = _team(db_session)
    relay = _result(db_session, team, is_relay=True)
    db_session.add(Participation(course_id=relay.course_id, athlete_id=lea.athlete_id, bib_number="X1",
                                 total_time="1:20:00", status="finisher"))
    db_session.flush()
    claim = result_claims.request_claim(db_session, lea, relay.id, kind=KIND_TEAM)

    with pytest.raises(DuplicateError, match="a déjà un résultat sur cette épreuve"):
        result_claims.approve(db_session, claim.id, actor_id=reviewer.id)

    assert claim.status == STATUS_PENDING
    assert (relay.athlete_id, _composition(db_session, relay)) == (team.id, [])
    assert db_session.query(AdminActionLog).count() == 0


def test_review_hints_for_a_team_claim(db_session, lea, homonym):
    partner, team = _athlete(db_session, nom="DURAND", prenom="Paul"), _team(db_session)
    relay = _result(db_session, team, is_relay=True)
    _compose(db_session, relay, partner, team)
    db_session.add(Participation(course_id=relay.course_id, athlete_id=lea.athlete_id, bib_number="X1",
                                 total_time="1:20:00", status="finisher"))
    db_session.flush()
    result_claims.request_claim(db_session, lea, relay.id, kind=KIND_TEAM)
    result_claims.request_claim(db_session, lea, _result(db_session, homonym).id)

    reviews = {review.kind: review for review in result_claims.list_pending_with_hints(db_session, date(2026, 10, 19))}

    team_review, result_review = reviews[KIND_TEAM], reviews[KIND_RESULT]
    assert [mate.id for mate in team_review.teammates] == [partner.id, team.id]
    assert [mate.id for mate in team_review.proposed_teammates] == [partner.id, lea.athlete_id]
    assert team_review.claimant_has_result_on_course is True
    assert (result_review.teammates, result_review.proposed_teammates) == ([], None)
    assert result_review.claimant_has_result_on_course is False
