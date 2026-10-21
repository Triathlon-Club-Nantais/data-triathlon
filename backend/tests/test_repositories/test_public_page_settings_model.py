from app.models.public_page_settings import PublicPageSettings
from app.models.season_goal import SeasonGoal
from app.models.user import SYSTEM_USER_EMAIL, User
from app.services.auth import accounts


def _user(db, email="lea@exemple.fr") -> User:
    user = User(email=email)
    db.add(user)
    db.flush()
    return user


def test_settings_leave_with_the_account(db_session):
    _user(db_session, SYSTEM_USER_EMAIL)
    user = _user(db_session)
    other = _user(db_session, "autre@exemple.fr")
    db_session.add_all(
        [
            PublicPageSettings(user_id=user.id, links=["https://strava.com/x"]),
            PublicPageSettings(user_id=other.id),
        ]
    )
    db_session.flush()

    accounts.delete_account(db_session, user, origin="request")
    db_session.flush()

    assert [row.user_id for row in db_session.query(PublicPageSettings)] == [other.id]


def test_settings_default_to_nothing_hidden(db_session):
    user = _user(db_session)
    db_session.add(PublicPageSettings(user_id=user.id))
    db_session.flush()
    db_session.expire_all()

    row = db_session.get(PublicPageSettings, user.id)
    assert (row.hide_best_times, row.hide_progression, row.hide_comparison) == (False, False, False)
    assert row.links == [] and row.pinned_participation_id is None


def test_season_goal_public_defaults_to_false(db_session):
    user = _user(db_session)
    goal = SeasonGoal(user_id=user.id, season=2026, kind="count")
    db_session.add(goal)
    db_session.flush()
    db_session.expire_all()

    assert db_session.get(SeasonGoal, goal.id).public is False
