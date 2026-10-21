"""Collecte et rendu du récap du week-end (#1363)."""
from datetime import date

import httpx
import pytest

from app.core import http
from app.repositories import athlete_repository, course_repository, participation_repository
from app.services.weekend_digest import (
    DigestCourse,
    DigestDeliveryError,
    DigestPodium,
    build,
    collect,
    render,
    send,
    weekend_before,
)

SAT, SUN = date(2026, 10, 17), date(2026, 10, 18)


def _course(db_session, day=SAT, name="Tri de Nantes"):
    return course_repository.get_or_create(db_session, name=name, event_date=day, event_type="triathlon-m")


def _result(db_session, course, prenom, nom, *, status="finisher", gender="M", pending=False, bib="1", **fields):
    athlete = athlete_repository.get_or_create(db_session, nom=nom, prenom=prenom, club="TCN", gender=gender)
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number=bib,
        club="TCN", status=status, is_pending_validation=pending, **fields,
    )
    db_session.flush()


def test_weekend_before_a_monday_is_the_weekend_just_ended():
    assert weekend_before(date(2026, 10, 19)) == (SAT, SUN)


def test_weekend_before_a_sunday_or_saturday_is_the_previous_one():
    previous = (date(2026, 10, 10), date(2026, 10, 11))
    assert weekend_before(SUN) == previous
    assert weekend_before(SAT) == previous


def test_collect_counts_classified_tcn_and_their_podiums(db_session):
    course = _course(db_session)
    _result(db_session, course, "Alice", "Martin", bib="1", rank_overall=2)
    _result(db_session, course, "Bea", "Durand", bib="2", rank_overall=10, rank_category=1)
    _result(db_session, course, "Carl", "Petit", bib="3", status="DNF")

    assert collect(db_session, SAT, SUN) == [
        DigestCourse(course.id, "Tri de Nantes", 2, [
            DigestPodium("Bea Durand", 1, "category"),
            DigestPodium("Alice Martin", 2, "overall"),
        ])
    ]


def test_collect_ignores_courses_outside_the_weekend(db_session):
    for day in (date(2026, 10, 16), date(2026, 10, 19)):
        _result(db_session, _course(db_session, day, f"C{day}"), "Alice", "Martin", rank_overall=1)

    assert collect(db_session, SAT, SUN) == []


def test_collect_returns_nothing_for_an_empty_weekend(db_session):
    assert collect(db_session, SAT, SUN) == []


def test_opposed_athletes_and_youths_are_never_named(db_session):
    course = _course(db_session)
    _result(db_session, course, "", "Anonyme 12-34", bib="1", rank_overall=1)
    _result(db_session, course, "Jules", "Jeune", bib="2", category="MIH", rank_overall=5, rank_category=1)

    (digest,) = collect(db_session, SAT, SUN)

    assert digest.podiums == []
    assert digest.finishers == 2


def test_a_gender_podium_needs_a_known_gender(db_session):
    _result(db_session, _course(db_session), "Alex", "Inconnu", gender=None, rank_gender=1)

    (digest,) = collect(db_session, SAT, SUN)

    assert digest.podiums == []


def test_a_known_gender_gets_a_gender_podium(db_session):
    _result(db_session, _course(db_session), "Alice", "Martin", gender="F", rank_gender=1)

    (digest,) = collect(db_session, SAT, SUN)

    assert digest.podiums == [DigestPodium("Alice Martin", 1, "gender")]


def test_equal_ranks_are_ordered_by_name(db_session):
    course = _course(db_session)
    _result(db_session, course, "Zoe", "Zed", bib="1", rank_overall=1)
    _result(db_session, course, "Abel", "Aron", bib="2", rank_category=1)

    (digest,) = collect(db_session, SAT, SUN)

    assert [podium.name for podium in digest.podiums] == ["Abel Aron", "Zoe Zed"]


def test_a_course_without_classified_tcn_is_still_listed(db_session):
    course = _course(db_session)
    _result(db_session, course, "Carl", "Petit", status="DNF")

    (digest,) = collect(db_session, SAT, SUN)
    text = render([digest], saturday=SAT, sunday=SUN, base_url="")

    assert digest.finishers == 0
    assert "0 TCN classé" in text


def test_pending_results_are_left_out(db_session):
    _result(db_session, _course(db_session), "Alice", "Martin", pending=True, rank_overall=1)

    assert collect(db_session, SAT, SUN) == []


def test_render_lists_each_course_with_its_link_and_podiums():
    text = render(
        [DigestCourse(12, "Tri & Co", 3, [DigestPodium("Alice Martin", 1, "overall")])],
        saturday=SAT, sunday=SUN, base_url="https://tcn.example",
    )

    assert "17/10 et 18/10/2026" in text
    assert "<https://tcn.example/courses/12|Tri &amp; Co>" in text
    assert "3 TCN classés" in text
    assert "🥇 Alice Martin (scratch)" in text


def test_render_without_base_url_shows_the_name_without_link():
    text = render([DigestCourse(12, "Tri & Co", 1, [])], saturday=SAT, sunday=SUN, base_url="")

    assert "Tri &amp; Co" in text
    assert "<" not in text
    assert "1 TCN classé" in text and "classés" not in text


def test_build_returns_none_for_an_empty_weekend(db_session):
    assert build(db_session, date(2026, 10, 19), base_url="") is None


def test_build_renders_the_weekend_before_the_given_day(db_session):
    _result(db_session, _course(db_session), "Jean", "Dupont")

    assert "Tri de Nantes" in build(db_session, date(2026, 10, 19), base_url="")


@pytest.fixture
def no_dns(monkeypatch):
    monkeypatch.setattr(http, "_resolve", lambda host, port: ["93.184.216.34"])


def test_send_posts_the_text_as_json(no_dns):
    seen = []

    def handler(request):
        request.read()
        seen.append(request)
        return httpx.Response(200)

    send("x", "https://hooks.slack.com/services/T/B/S", transport=httpx.MockTransport(handler))

    assert [(r.method, str(r.url), r.content) for r in seen] == [
        ("POST", "https://hooks.slack.com/services/T/B/S", b'{"text":"x"}')
    ]


def test_send_raises_on_a_slack_error(no_dns):
    with pytest.raises(DigestDeliveryError, match="404") as error:
        send("x", "https://hooks.slack.com/services/T/B/S", transport=httpx.MockTransport(lambda r: httpx.Response(404)))

    assert "hooks.slack.com" not in str(error.value)


def test_send_raises_on_a_network_error(no_dns):
    def handler(request):
        raise httpx.ConnectError("boom", request=request)

    with pytest.raises(DigestDeliveryError) as error:
        send("x", "https://hooks.slack.com/services/T/B/S", transport=httpx.MockTransport(handler))

    assert "hooks.slack.com" not in str(error.value)
