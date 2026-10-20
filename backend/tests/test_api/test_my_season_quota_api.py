"""`GET /auth/me/season-quota` over HTTP (#1671)."""

from datetime import date, datetime

from app.core import season
from app.core.permissions import P
from app.models.user import User
from app.repositories import (
    athlete_repository,
    course_repository,
    participation_repository,
    volunteer_action_repository,
)

from .test_admin_data_api import _session_etroite

URL = "/api/v1/auth/me/season-quota"


def _result(db_session, athlete, name, day, status="finisher", bib="1"):
    course = course_repository.get_or_create(
        db_session, name=name, event_date=day, event_type="triathlon-m"
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number=bib, status=status
    )


def test_unauthenticated_is_401(client):
    client.cookies.clear()

    assert client.get(URL).status_code == 401


def test_without_claimed_athlete_returns_null(client, db_session):
    _session_etroite(client, db_session)

    response = client.get(URL)

    assert response.status_code == 200
    assert response.json() is None


def test_counts_current_season_for_claimed_athlete(client, db_session, monkeypatch):
    monkeypatch.setattr(season, "utcnow", lambda: datetime(2026, 10, 15, 12, 0, 0))
    athlete = athlete_repository.get_or_create(db_session, nom="Martin", prenom="Léa")
    db_session.flush()
    _result(db_session, athlete, "A", date(2026, 9, 6), bib="1")
    _result(db_session, athlete, "B", date(2026, 9, 13), bib="2")
    _result(db_session, athlete, "C", date(2026, 9, 20), status="DNS", bib="3")
    _result(db_session, athlete, "D", date(2026, 5, 10), bib="4")
    user = _session_etroite(client, db_session)
    db_session.get(User, user.id).athlete_id = athlete.id
    action = volunteer_action_repository.create_pending(
        db_session,
        athlete_id=athlete.id,
        season=2026,
        declared_by_user_id=user.id,
        title="Ravitaillement",
        description="Tenue du poste.",
    )
    volunteer_action_repository.set_status(db_session, action.id, "validee")
    db_session.commit()

    body = client.get(URL).json()

    assert body["validated_count"] == 2
    assert body["has_volunteer_action"] is True
    assert body["quota_met"] is False
    assert body["season"] == season.current_season() == 2026
    assert body["required_events"] == 3


def test_admin_season_quota_still_works(client, db_session):
    athlete = athlete_repository.get_or_create(db_session, nom="Martin", prenom="Léa")
    db_session.flush()
    _session_etroite(client, db_session, P.ATHLETES_SEASON_VALIDATE)

    body = client.get(
        f"/api/v1/admin/athletes/{athlete.id}/season-quota", params={"season": 2025}
    ).json()

    assert (body["season"], body["required_events"]) == (2025, 3)
