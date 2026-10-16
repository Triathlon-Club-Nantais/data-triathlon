"""The shared load-or-404 lookups (#1584)."""
import pytest

from app.core.exceptions import NotFoundError
from app.models.course import Course
from app.repositories import athlete_repository, user_repository
from app.services import not_found


def test_athlete_or_404_returns_the_athlete(db_session):
    athlete = athlete_repository.get_or_create(db_session, nom="DUPONT", prenom="Jean", club="TCN")
    db_session.flush()

    assert not_found.athlete_or_404(db_session, athlete.id) is athlete


def test_athlete_or_404_raises_a_not_found(db_session):
    with pytest.raises(NotFoundError) as exc:
        not_found.athlete_or_404(db_session, 999999)

    assert exc.value.status_code == 404
    assert exc.value.message == "Athlète introuvable."


def test_athlete_or_404_keeps_a_call_site_message(db_session):
    with pytest.raises(NotFoundError, match="^Athlète introuvable$"):
        not_found.athlete_or_404(db_session, 999999, message="Athlète introuvable")


def test_course_or_404_returns_the_course(db_session):
    course = Course(name="Triathlon de Test", event_type="triathlon-m")
    db_session.add(course)
    db_session.flush()

    assert not_found.course_or_404(db_session, course.id) is course


def test_course_or_404_raises_a_not_found(db_session):
    with pytest.raises(NotFoundError) as exc:
        not_found.course_or_404(db_session, 999999)

    assert exc.value.message == "Épreuve introuvable."


def test_course_or_404_keeps_a_call_site_message(db_session):
    with pytest.raises(NotFoundError, match="^Épreuve introuvable$"):
        not_found.course_or_404(db_session, 999999, message="Épreuve introuvable")


def test_user_or_404_returns_the_user(db_session):
    user = user_repository.create(db_session, email="membre@exemple.fr")
    db_session.flush()

    assert not_found.user_or_404(db_session, user.id) is user


def test_user_or_404_raises_a_not_found(db_session):
    with pytest.raises(NotFoundError) as exc:
        not_found.user_or_404(db_session, 999999)

    assert exc.value.message == "Cet utilisateur n'existe pas."
