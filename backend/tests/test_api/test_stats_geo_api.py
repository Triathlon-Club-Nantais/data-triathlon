"""GET /stats/events-geo : géolocalisation des épreuves pour la carte (issue #495).

Le lien de la carte vers la fiche d'une épreuve suppose que la réponse porte
`course_id` — la requête groupée le sélectionne déjà (une ligne par `Course`),
la route se contentait de le jeter en construisant son dict.
"""
from datetime import date

import pytest

from app.repositories import athlete_repository, course_repository, participation_repository


@pytest.fixture
def epreuve_geolocalisee(db_session, monkeypatch):
    monkeypatch.setattr(
        "app.services.geocode_service.geocode", lambda event_name: (47.2, -1.5)
    )
    course = course_repository.get_or_create(
        db_session, name="Tri Vertou", event_date=date(2026, 6, 14), event_type="triathlon"
    )
    athlete = athlete_repository.get_or_create(
        db_session, nom="NOM", prenom="Test", gender="M", club="TCN"
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
    db_session.commit()
    return course


def test_events_geo_porte_le_course_id_de_l_epreuve(client, epreuve_geolocalisee):
    body = client.get("/api/v1/stats/events-geo").json()

    assert len(body) == 1
    assert body[0]["course_id"] == epreuve_geolocalisee.id
