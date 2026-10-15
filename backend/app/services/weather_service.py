"""Météo du jour de course, lue dans l'archive Open-Meteo (#1370).

Sur le patron de `geocode_service` : `run_weather_courses` est le seul point
d'écriture des colonnes `weather_*` de `Course`, appelé hors ligne par
`python -m app.cli weather-courses`, jamais par une route. Open-Meteo est
gratuit et sans clé pour un usage non commercial, sous licence CC BY 4.0 :
l'écran qui affiche ces valeurs le crédite.
"""
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta

import httpx
from sqlalchemy.orm import Session

from app.core import http
from app.models.course import Course
from app.repositories import course_repository
from app.services import batch
from app.services.batch import BatchFailure

logger = logging.getLogger(__name__)

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

#: L'archive se consolide quelques jours après la date : une épreuve plus
#: récente attend le lancement suivant plutôt que de figer une valeur provisoire.
ARCHIVE_DELAY = timedelta(days=5)


@dataclass(frozen=True)
class DailyWeather:
    """Moyennes journalières (la pluie est un cumul), faute d'heure de départ."""

    temperature_c: float
    wind_kmh: float | None
    precipitation_mm: float | None


def fetch_daily_weather(latitude: float, longitude: float, day: date) -> DailyWeather | None:
    """Un appel à l'archive Open-Meteo. `None` sur toute réponse inexploitable."""
    try:
        with http.client(timeout=10) as client:
            response = client.get(ARCHIVE_URL, params={
                "latitude": latitude,
                "longitude": longitude,
                "start_date": day.isoformat(),
                "end_date": day.isoformat(),
                "daily": "temperature_2m_mean,wind_speed_10m_mean,precipitation_sum",
                "timezone": "Europe/Paris",
            })
        response.raise_for_status()
        daily = response.json()["daily"]
        temperature = daily["temperature_2m_mean"][0]
        if temperature is None:
            return None
        return DailyWeather(
            temperature, daily["wind_speed_10m_mean"][0], daily["precipitation_sum"][0]
        )
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
        # Ni coordonnées ni message (il porte l'URL) : CodeQL les tient pour sensibles.
        logger.warning("Open-Meteo archive failed on %s: %s", day, type(exc).__name__)
        return None


@dataclass
class WeatherOutcome:
    """Bilan d'un `weather-courses`, sur le patron de `GeocodeOutcome`."""

    total: int = 0
    fetched: int = 0
    errors: int = 0
    processed: int = 0
    interrupted: bool = False
    dry_run: bool = False
    dry_run_names: list[str] = field(default_factory=list)
    failures: list[BatchFailure] = field(default_factory=list)

    @property
    def is_total_failure(self) -> bool:
        if self.dry_run:
            return False
        return batch.is_total_failure(events=self.total, errors=self.errors)


def run_weather_courses(
    db: Session,
    *,
    limit: int | None = None,
    dry_run: bool = False,
    today: date | None = None,
    on_item: Callable[[int, int, str, DailyWeather | None], None] | None = None,
) -> WeatherOutcome:
    """Pose la météo des épreuves géocodées et datées qui n'en ont pas (#1370).

    Idempotent : une épreuve servie n'est plus ciblée. Un échec ne persiste
    rien, il est retenté au lancement suivant (un appel de quelques dizaines de
    millisecondes, sans délai de reprise : un échec durable se lit dans le
    détail du bilan). Un appel par lieu et date,
    propagé aux heats qui les partagent ; chaque épreuve est commitée seule,
    un Ctrl-C ne perd que la tentative en cours.
    """
    cutoff = (today or date.today()) - ARCHIVE_DELAY
    courses = course_repository.list_missing_weather(db, dated_before=cutoff, limit=limit)
    outcome = WeatherOutcome(total=len(courses), dry_run=dry_run)

    if dry_run:
        outcome.dry_run_names = [c.name for c in courses]
        return outcome

    events: dict[tuple[float, float, date], list[Course]] = {}
    for course in courses:
        events.setdefault((course.latitude, course.longitude, course.event_date), []).append(course)

    try:
        for (latitude, longitude, day), heats in events.items():
            weather = fetch_daily_weather(latitude, longitude, day)
            for course in heats:
                if weather is not None:
                    course_repository.save_weather(
                        db, course, temperature_c=weather.temperature_c,
                        wind_kmh=weather.wind_kmh, precipitation_mm=weather.precipitation_mm,
                    )
                    outcome.fetched += 1
                else:
                    outcome.errors += 1
                    outcome.failures.append(
                        BatchFailure(url=course.name, label=course.name, message="météo indisponible")
                    )
                if on_item is not None:
                    on_item(outcome.processed, outcome.total, course.name, weather)
                outcome.processed += 1
    except KeyboardInterrupt:
        outcome.interrupted = True

    return outcome
