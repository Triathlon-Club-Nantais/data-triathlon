"""A claimed member asks for a result filed under another record (#1637)."""
from datetime import date

import pytest

from app.core.exceptions import DomainError, NotFoundError
from app.models.admin_action_log import AdminActionLog
from app.models.athlete import Athlete
from app.models.course import Course
from app.models.participation import Participation
from app.models.result_claim import STATUS_PENDING, STATUS_REJECTED, ResultClaim
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


@pytest.mark.parametrize("case", ["own", "pending", "relay", "unknown"])
def test_a_result_that_cannot_be_claimed_is_refused(db_session, lea, homonym, case):
    if case == "own":
        target = _result(db_session, db_session.get(Athlete, lea.athlete_id)).id
    elif case == "pending":
        target = _result(db_session, homonym, is_pending_validation=True).id
    elif case == "relay":
        target = _result(db_session, homonym, is_relay=True).id
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
