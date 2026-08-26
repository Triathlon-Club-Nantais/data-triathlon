"""GET /stats/events-geo : géolocalisation des épreuves pour la carte (issue #495).

Le lien de la carte vers la fiche d'une épreuve suppose que la réponse porte
`course_id` — la requête groupée le sélectionne déjà (une ligne par `Course`),
la route se contentait de le jeter en construisant son dict.

#579 : la route ne géocode plus rien elle-même — elle ne fait qu'un `SELECT`
sur `Course.latitude`/`longitude`, persistées ailleurs (`geocode-courses`).
`geocode_service.geocode` est donc espionné pour **échouer** si la route le
touche encore : c'était le défaut mesuré (165 à 330 s de premier octet).
"""
from datetime import date

import pytest

from app.repositories import athlete_repository, course_repository, participation_repository


def _fail_if_called(event_name: str):
    raise AssertionError(
        "GET /stats/events-geo ne doit plus jamais appeler geocode_service.geocode (#579)"
    )


@pytest.fixture(autouse=True)
def nominatim_interdit(monkeypatch):
    """Espion qui échoue si la route retombe sur un appel réseau."""
    monkeypatch.setattr("app.services.geocode_service.geocode", _fail_if_called)


def _course(db_session, *, nom, lat=None, lon=None):
    course = course_repository.get_or_create(
        db_session, name=nom, event_date=date(2026, 6, 14), event_type="triathlon"
    )
    if lat is not None:
        course.latitude, course.longitude = lat, lon
    athlete = athlete_repository.get_or_create(
        db_session, nom=f"NOM-{nom}", prenom="Test", gender="M", club="TCN"
    )
    participation_repository.create(
        db_session,
        athlete_id=athlete.id,
        course_id=course.id,
        bib_number="1",
        club="TCN",
        category="SEM",
        status="finisher",
        rank_overall=1,
        total_time="01:00:00",
    )
    # Compteur dénormalisé (#623) : posé directement, fixture hors import.
    course_repository.set_counts(db_session, course, participation_count=1, tcn_count=1)
    db_session.commit()
    return course


@pytest.fixture
def epreuve_geolocalisee(db_session):
    return _course(db_session, nom="Tri Vertou", lat=47.2, lon=-1.5)


def test_events_geo_porte_le_course_id_de_l_epreuve(client, epreuve_geolocalisee):
    body = client.get("/api/v1/stats/events-geo").json()

    assert len(body) == 1
    assert body[0]["course_id"] == epreuve_geolocalisee.id


def test_events_geo_rend_les_coordonnees_persistees_sans_appeler_nominatim(
    client, db_session
):
    _course(db_session, nom="Tri Nantes", lat=47.2181, lon=-1.5528)

    body = client.get("/api/v1/stats/events-geo").json()

    assert len(body) == 1
    assert body[0]["lat"] == 47.2181
    assert body[0]["lon"] == -1.5528


def test_une_epreuve_sans_coordonnees_est_rendue_sans_marqueur(client, db_session):
    """Pas géocodée = pas de marqueur, jamais une erreur (#579)."""
    _course(db_session, nom="Tri Jamais Géocodé")

    response = client.get("/api/v1/stats/events-geo")

    assert response.status_code == 200
    assert response.json() == []
