"""Météo du jour de course, Open-Meteo (`app/services/weather_service.py`, #1370).

Aucun réseau : la vraie fabrique `http.client` reçoit un `httpx.MockTransport`,
sur le patron de `test_geocode_service.py`. Seul le dernier test, marqué
`integration`, interroge l'API réelle.
"""
from datetime import date, timedelta

import httpx
import pytest

from app.core import http
from app.core.time import utcnow
from app.repositories import course_repository
from app.services import weather_service


@pytest.fixture
def stub_open_meteo(monkeypatch):
    """Installe un handler comme transport interne ; rend la liste des requêtes vues."""
    monkeypatch.setattr(http, "_resolve", lambda host, port: ["93.184.216.34"])
    seen: list[httpx.Request] = []
    real_factory = http.client

    def install(handler):
        def factory(**kwargs):
            def spy(request):
                seen.append(request)
                return handler(request)

            return real_factory(transport=httpx.MockTransport(spy), **kwargs)

        monkeypatch.setattr(weather_service.http, "client", factory)
        return seen

    return install


def _daily(temperature=18.0, wind=11.3, rain=0.4):
    return httpx.Response(200, json={"daily": {
        "time": ["2025-06-01"],
        "temperature_2m_mean": [temperature],
        "wind_speed_10m_mean": [wind],
        "precipitation_sum": [rain],
    }})


def test_fetch_daily_weather_reads_the_three_daily_values(stub_open_meteo):
    seen = stub_open_meteo(lambda _: _daily())

    weather = weather_service.fetch_daily_weather(47.2, -1.55, date(2025, 6, 1))

    assert weather == weather_service.DailyWeather(18.0, 11.3, 0.4)
    params = seen[0].url.params
    assert seen[0].url.host == "archive-api.open-meteo.com"
    assert params["start_date"] == params["end_date"] == "2025-06-01"
    assert params["timezone"] == "Europe/Paris"


@pytest.mark.parametrize("response", [
    httpx.Response(500),
    httpx.Response(200, json={"error": True}),
    httpx.Response(200, text="pas du json"),
    _daily(temperature=None),
])
def test_fetch_daily_weather_returns_none_on_unusable_answer(stub_open_meteo, response):
    stub_open_meteo(lambda _: response)

    assert weather_service.fetch_daily_weather(47.2, -1.55, date(2025, 6, 1)) is None


def test_fetch_daily_weather_returns_none_on_network_error(stub_open_meteo):
    def boom(_):
        raise httpx.ConnectError("down")

    stub_open_meteo(boom)

    assert weather_service.fetch_daily_weather(47.2, -1.55, date(2025, 6, 1)) is None


def _course(db, name, *, days_ago=30, coords=(47.2, -1.55)):
    course = course_repository.get_or_create(
        db, name=name, event_date=date.today() - timedelta(days=days_ago), event_type="triathlon-m"
    )
    course.latitude, course.longitude = coords if coords else (None, None)
    db.flush()
    return course


def test_run_stores_weather_once_per_event_and_propagates_to_heats(db_session, stub_open_meteo):
    heat_s = _course(db_session, "Triathlon de Nantes - S")
    heat_m = _course(db_session, "Triathlon de Nantes - M")
    seen = stub_open_meteo(lambda _: _daily())

    outcome = weather_service.run_weather_courses(db_session)

    assert len(seen) == 1
    assert (outcome.total, outcome.fetched, outcome.errors) == (2, 2, 0)
    for course in (heat_s, heat_m):
        db_session.refresh(course)
        assert (course.weather_temperature_c, course.weather_wind_kmh,
                course.weather_precipitation_mm) == (18.0, 11.3, 0.4)
        assert course.weather_fetched_at is not None


def test_run_skips_ungeocoded_recent_undated_and_already_fetched(db_session, stub_open_meteo):
    _course(db_session, "Sans coordonnées", coords=None)
    _course(db_session, "Trop récente", days_ago=2)
    undated = _course(db_session, "Sans date")
    undated.event_date = None
    done = _course(db_session, "Déjà servie")
    done.weather_fetched_at = utcnow()
    db_session.flush()
    seen = stub_open_meteo(lambda _: _daily())

    outcome = weather_service.run_weather_courses(db_session)

    assert outcome.total == 0
    assert seen == []


def test_run_failure_persists_nothing_so_it_is_retried(db_session, stub_open_meteo):
    course = _course(db_session, "Triathlon Muet")
    stub_open_meteo(lambda _: httpx.Response(503))

    outcome = weather_service.run_weather_courses(db_session)

    assert (outcome.errors, outcome.is_total_failure) == (1, True)
    db_session.refresh(course)
    assert course.weather_fetched_at is None


def test_run_dry_run_lists_targets_without_calling(db_session, stub_open_meteo):
    _course(db_session, "Triathlon Aperçu")
    seen = stub_open_meteo(lambda _: _daily())

    outcome = weather_service.run_weather_courses(db_session, dry_run=True)

    assert outcome.dry_run_names == ["Triathlon Aperçu"]
    assert seen == []


@pytest.mark.integration
def test_real_open_meteo_archive_answers_for_nantes():
    weather = weather_service.fetch_daily_weather(47.2181, -1.5528, date(2025, 6, 1))

    assert weather is not None
    assert -10 < weather.temperature_c < 40
