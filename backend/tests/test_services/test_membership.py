"""Derived member status and retained address (#1322)."""
from datetime import date

from app.models.athlete import Athlete
from app.models.club_member import LINK_AMBIGUOUS, LINK_AUTO, SOURCE_FFTRI, ClubMember
from app.models.member_email import SOURCE_IMPORT, SOURCE_MANUAL, MemberEmail
from app.models.user import SYSTEM_USER_EMAIL
from app.repositories import allowed_email_repository, member_email_repository, user_repository
from app.services import membership
from app.services.auth.idp.base import ExternalIdentity

TODAY = date(2026, 10, 11)  # season 2026


def _list(db, email, season=2026, source=SOURCE_IMPORT) -> MemberEmail:
    entry = MemberEmail(email=email, season=season, source=source)
    db.add(entry)
    db.flush()
    return entry


def _user(db, email="adherent@exemple.fr", *, active=True):
    user = user_repository.create(db, email=email, display_name="")
    user.is_active = active
    db.flush()
    return user


def test_a_user_whose_address_counts_is_a_member(db_session):
    _list(db_session, "adherent@exemple.fr")
    assert membership.is_member(db_session, _user(db_session, "Adherent@Exemple.fr"), TODAY)


def test_a_user_absent_from_the_list_is_not_a_member(db_session):
    _list(db_session, "autre@exemple.fr")
    assert not membership.is_member(db_session, _user(db_session), TODAY)


def test_an_inactive_account_is_never_a_member(db_session):
    _list(db_session, "adherent@exemple.fr")
    assert not membership.is_member(db_session, _user(db_session, active=False), TODAY)


def test_the_volunteer_system_account_is_never_a_member(db_session):
    _list(db_session, SYSTEM_USER_EMAIL)
    assert not membership.is_member(db_session, _user(db_session, SYSTEM_USER_EMAIL), TODAY)


def test_an_address_from_an_older_season_does_not_count(db_session):
    _list(db_session, "adherent@exemple.fr", season=2025)
    _list(db_session, "autre@exemple.fr", season=2026)
    assert not membership.is_member(db_session, _user(db_session), TODAY)


def test_removing_the_address_takes_effect_immediately(db_session):
    entry = _list(db_session, "adherent@exemple.fr")
    user = _user(db_session)
    assert membership.is_member(db_session, user, TODAY)
    member_email_repository.remove(db_session, entry.id)
    assert not membership.is_member(db_session, user, TODAY)


def _linked(db, *, season=None, status=LINK_AUTO):
    """A user linked to an athlete record (#1325), licensed TCN for `season` if given (#1633)."""
    athlete = Athlete(nom="Martin", prenom="Léa")
    db.add(athlete)
    db.flush()
    if season is not None:
        db.add(ClubMember(season=season, nom="MARTIN", prenom="Léa", athlete_id=athlete.id,
                          link_status=status, source=SOURCE_FFTRI))
    user = _user(db)
    user.athlete_id = athlete.id
    db.flush()
    return user


def test_a_linked_account_licensed_this_season_is_a_member(db_session):
    assert membership.is_member(db_session, _linked(db_session, season=2026), TODAY)


def test_a_linked_account_licensed_only_last_season_is_not_a_member(db_session):
    """#1633: the link alone no longer counts, the licence of the season does."""
    user = _linked(db_session, season=2025)

    assert not membership.is_member(db_session, user, TODAY)
    assert user.athlete_id is not None


def test_an_unsettled_licence_does_not_count(db_session):
    assert not membership.is_member(db_session, _linked(db_session, season=2026, status=LINK_AMBIGUOUS), TODAY)


def test_a_linked_account_on_the_member_list_stays_a_member(db_session):
    _list(db_session, "adherent@exemple.fr")
    assert membership.is_member(db_session, _linked(db_session), TODAY)


def test_no_user_is_not_a_member(db_session):
    assert not membership.is_member(db_session, None, TODAY)


def _identity(*emails: str) -> ExternalIdentity:
    return ExternalIdentity(
        provider="doublure",
        subject="s-1",
        email=emails[0],
        email_verified=True,
        verified_emails=emails,
    )


def test_retained_email_prefers_the_allow_list(db_session):
    _list(db_session, "perso@exemple.fr")
    allowed_email_repository.add(db_session, email="club@exemple.fr")
    identity = _identity("perso@exemple.fr", "club@exemple.fr")
    assert membership.retained_email(db_session, identity, TODAY) == "club@exemple.fr"


def test_retained_email_then_prefers_a_counting_member_address(db_session):
    _list(db_session, "club@exemple.fr", source=SOURCE_MANUAL)
    identity = _identity("perso@exemple.fr", "club@exemple.fr")
    assert membership.retained_email(db_session, identity, TODAY) == "club@exemple.fr"


def test_retained_email_falls_back_to_the_primary_address(db_session):
    identity = _identity("perso@exemple.fr", "autre@exemple.fr")
    assert membership.retained_email(db_session, identity, TODAY) == "perso@exemple.fr"
