"""#1359 : un événement admin ne porte l'identifiant du compte qu'avec l'accord du navigateur."""
from datetime import date
from unittest.mock import MagicMock

import pytest

from app.core import analytics
from app.core.analytics import ANALYTICS_CONSENT_COOKIE, ANONYMOUS_DISTINCT_ID
from app.models.user import User
from app.repositories import course_repository


@pytest.fixture
def posthog(monkeypatch):
    fake = MagicMock()
    monkeypatch.setattr(analytics, "posthog_client", fake)
    return fake


@pytest.fixture
def course_id(db_session):
    course = course_repository.get_or_create(
        db_session, name="Tri A", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    db_session.commit()
    return course.id


def test_admin_event_with_consent_is_tied_to_the_user(client, db_session, posthog, course_id):
    client.cookies.set(ANALYTICS_CONSENT_COOKIE, "granted")

    assert client.delete(f"/api/v1/admin/courses/{course_id}").status_code == 204

    user = db_session.query(User).filter_by(email="saisie@exemple.fr").one()
    assert posthog.capture.call_args.kwargs["distinct_id"] == str(user.id)


def test_admin_event_without_consent_stays_anonymous(client, posthog, course_id):
    assert client.delete(f"/api/v1/admin/courses/{course_id}").status_code == 204

    assert posthog.capture.call_args.kwargs["event"] == "course_deleted"
    assert posthog.capture.call_args.kwargs["distinct_id"] == ANONYMOUS_DISTINCT_ID
