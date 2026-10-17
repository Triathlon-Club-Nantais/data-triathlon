"""Claiming one's athlete record (#1325): never automatic, always reviewed."""
from datetime import date

import pytest

from app.core.exceptions import NotFoundError
from app.core.season import current_season
from app.models.admin_action_log import AdminActionLog
from app.models.athlete import Athlete
from app.models.athlete_claim import STATUS_PENDING, STATUS_REJECTED, AthleteClaim
from app.models.club_member import LINK_AUTO, SOURCE_FFTRI, ClubMember
from app.models.member_email import SOURCE_IMPORT, MemberEmail
from app.repositories import user_repository
from app.services import athlete_claims, membership


def _athlete(db, nom="Martin", prenom="Léa") -> Athlete:
    athlete = Athlete(nom=nom, prenom=prenom, club="TRIATHLON CLUB NANTAIS")
    db.add(athlete)
    db.flush()
    return athlete


@pytest.fixture
def lea(db_session):
    return user_repository.create(db_session, email="lea@exemple.fr", display_name="Léa M.")


@pytest.fixture
def reviewer(db_session):
    return user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")


def test_a_request_is_pending_and_links_nothing(db_session, lea):
    athlete = _athlete(db_session)

    claim = athlete_claims.request_claim(db_session, lea, athlete.id)

    assert (claim.athlete_id, claim.status) == (athlete.id, STATUS_PENDING)
    assert lea.athlete_id is None


def test_an_address_on_the_member_list_is_not_validated_automatically(db_session, lea):
    db_session.add(MemberEmail(email=lea.email, season=current_season(), source=SOURCE_IMPORT))
    athlete = _athlete(db_session)

    claim = athlete_claims.request_claim(db_session, lea, athlete.id)

    assert claim.status == STATUS_PENDING
    assert lea.athlete_id is None


def test_a_new_request_replaces_the_previous_one(db_session, lea, reviewer):
    first, second = _athlete(db_session), _athlete(db_session, "Durand")
    claim = athlete_claims.request_claim(db_session, lea, first.id)
    athlete_claims.reject(db_session, claim.id, actor_id=reviewer.id)

    athlete_claims.request_claim(db_session, lea, second.id)

    claims = db_session.query(AthleteClaim).all()
    assert [(c.athlete_id, c.status) for c in claims] == [(second.id, STATUS_PENDING)]


def test_requesting_an_unknown_athlete_is_not_found(db_session, lea):
    with pytest.raises(NotFoundError):
        athlete_claims.request_claim(db_session, lea, 999_999)


def test_a_linked_account_must_detach_first(db_session, lea):
    lea.athlete_id = _athlete(db_session).id
    db_session.flush()

    with pytest.raises(athlete_claims.AlreadyLinkedError):
        athlete_claims.request_claim(db_session, lea, _athlete(db_session, "Durand").id)


def test_cancel_is_idempotent(db_session, lea):
    athlete_claims.request_claim(db_session, lea, _athlete(db_session).id)

    athlete_claims.cancel_claim(db_session, lea)
    athlete_claims.cancel_claim(db_session, lea)

    assert db_session.query(AthleteClaim).count() == 0


def test_approve_links_the_account_removes_the_claim_and_logs(db_session, lea, reviewer):
    athlete = _athlete(db_session)
    claim = athlete_claims.request_claim(db_session, lea, athlete.id)

    athlete_claims.approve(db_session, claim.id, actor_id=reviewer.id)

    assert lea.athlete_id == athlete.id
    assert db_session.query(AthleteClaim).count() == 0
    log = db_session.query(AdminActionLog).one()
    assert (log.user_id, log.action, log.entity_type, log.entity_id) == (
        reviewer.id, "athlete_claim.approve", "user", lea.id,
    )
    assert log.payload == {"athlete_id": athlete.id, "claim_id": claim.id}


def test_reject_links_nothing_and_logs(db_session, lea, reviewer):
    claim = athlete_claims.request_claim(db_session, lea, _athlete(db_session).id)

    athlete_claims.reject(db_session, claim.id, actor_id=reviewer.id)

    assert lea.athlete_id is None
    assert claim.status == STATUS_REJECTED
    assert claim.decided_at is not None
    assert db_session.query(AdminActionLog).one().action == "athlete_claim.reject"


@pytest.mark.parametrize("decide", [athlete_claims.approve, athlete_claims.reject])
def test_a_claim_no_longer_pending_cannot_be_decided(db_session, lea, reviewer, decide):
    claim = athlete_claims.request_claim(db_session, lea, _athlete(db_session).id)
    athlete_claims.reject(db_session, claim.id, actor_id=reviewer.id)

    with pytest.raises(NotFoundError):
        decide(db_session, claim.id, actor_id=reviewer.id)
    with pytest.raises(NotFoundError):
        decide(db_session, 999_999, actor_id=reviewer.id)


def test_detach_unlinks_and_is_idempotent(db_session, lea):
    athlete = _athlete(db_session)
    lea.athlete_id = athlete.id
    db_session.flush()

    athlete_claims.detach(db_session, lea)
    athlete_claims.detach(db_session, lea)

    assert lea.athlete_id is None
    assert db_session.get(Athlete, athlete.id) is not None


def test_detaching_drops_the_membership_it_gave(db_session, lea):
    lea.athlete_id = _athlete(db_session).id
    db_session.flush()
    assert membership.is_member(db_session, lea, date.today())

    athlete_claims.detach(db_session, lea)

    assert not membership.is_member(db_session, lea, date.today())


def test_the_review_list_carries_its_hints(db_session, lea, reviewer):
    season = current_season()
    athlete = _athlete(db_session)
    db_session.add_all([
        MemberEmail(email=lea.email, season=season, source=SOURCE_IMPORT),
        ClubMember(season=season, nom="MARTIN", prenom="Léa", athlete_id=athlete.id,
                   link_status=LINK_AUTO, source=SOURCE_FFTRI),
    ])
    already = user_repository.create(db_session, email="autre@exemple.fr", display_name="")
    already.athlete_id = athlete.id
    bare = user_repository.create(db_session, email="bare@exemple.fr", display_name="")
    athlete_claims.request_claim(db_session, lea, athlete.id)
    athlete_claims.request_claim(db_session, bare, _athlete(db_session, "Durand").id)

    first, second = athlete_claims.list_pending_with_hints(db_session, date.today())

    assert (first.user.id, first.athlete.id) == (lea.id, athlete.id)
    assert (first.licensee.nom, first.licensee.season) == ("MARTIN", season)
    assert first.email_on_member_list is True
    assert first.linked_accounts == 1
    assert (second.licensee, second.email_on_member_list, second.linked_accounts) == (None, False, 0)
