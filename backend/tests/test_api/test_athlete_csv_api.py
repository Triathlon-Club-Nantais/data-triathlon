"""`GET /athletes/{id}/participations.csv` : la fiche athlète en CSV (#1375)."""
import csv
import io
from datetime import date

import pytest

from app.repositories import athlete_repository, course_repository, participation_repository

BOM = "﻿"


@pytest.fixture
def athlete(db_session):
    athlete = athlete_repository.get_or_create(db_session, nom="DÉSIRÉ", prenom="Léa", club="TCN")
    ancienne = course_repository.get_or_create(
        db_session, name="Tri de Nantes", event_date=date(2025, 6, 1), event_type="triathlon-m",
        distance_km=51.5, source_url="https://k/a", provider="klikego",
    )
    recente = course_repository.get_or_create(
        db_session, name="Duathlon de Rezé", event_date=date(2026, 3, 8), event_type="duathlon-s",
        source_url="https://k/b", provider="klikego",
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=ancienne.id, bib_number="12", club="TCN",
        category="SEH", status="finisher", rank_overall=3, rank_category=1, rank_gender=2,
        total_time="02:10:00", splits={"swim": "00:25:00", "bike": "01:05:00"},
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=recente.id, bib_number="7", club="TCN",
        status="finisher", rank_overall=5, total_time="01:00:00", is_pending_validation=True,
        splits={"course1": "00:20:00"},
    )
    db_session.commit()
    return athlete


def _rows(response):
    text = response.content.decode("utf-8")
    assert text.startswith(BOM)
    return list(csv.DictReader(io.StringIO(text[1:]), delimiter=";"))


def test_csv_headers_and_filename(client, athlete):
    response = client.get(f"/api/v1/athletes/{athlete.id}/participations.csv")

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert response.headers["content-disposition"] == 'attachment; filename="resultats-lea-desire.csv"'


def test_csv_rows_sorted_by_date_with_splits_as_columns(client, athlete):
    rows = _rows(client.get(f"/api/v1/athletes/{athlete.id}/participations.csv"))

    assert [r["Épreuve"] for r in rows] == ["Duathlon de Rezé", "Tri de Nantes"]
    validated = rows[1]
    assert validated["Date"] == "2025-06-01"
    assert validated["Distance (km)"] == "51,5"
    assert validated["Temps"] == "02:10:00"
    assert validated["Rang général"] == "3"
    assert validated["Rang catégorie"] == "1"
    assert validated["Rang sexe"] == "2"
    assert validated["Catégorie"] == "SEH"
    assert validated["Validation"] == "Validé"
    assert validated["Classés"] == "1"
    assert validated["Segment Natation"] == "00:25:00"
    assert validated["Segment Vélo"] == "01:05:00"
    assert validated["Segment Course 1"] == ""


def test_csv_pending_row_has_no_rank(client, athlete):
    pending = _rows(client.get(f"/api/v1/athletes/{athlete.id}/participations.csv"))[0]

    assert pending["Validation"] == "En attente"
    assert pending["Rang général"] == ""
    assert pending["Temps"] == "01:00:00"
    assert pending["Segment Course 1"] == "00:20:00"


def test_csv_rejected_row_is_flagged(client, db_session, athlete):
    for participation in participation_repository.list_for_athlete(db_session, athlete.id):
        participation.is_rejected = participation.is_pending_validation
    db_session.commit()

    rows = _rows(client.get(f"/api/v1/athletes/{athlete.id}/participations.csv"))

    assert rows[0]["Épreuve"] == "Duathlon de Rezé"
    assert rows[0]["Validation"] == "Refusé"


def test_csv_undated_relay_row_comes_last(client, db_session, athlete):
    relay = course_repository.get_or_create(
        db_session, name="Relais sans date", event_date=None, event_type="triathlon-s", is_relay=True,
        source_url="https://k/c", provider="klikego",
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=relay.id, bib_number="R1", club="TCN",
        status="dnf", is_relay=True, team_name="Les Requins",
    )
    db_session.commit()

    last = _rows(client.get(f"/api/v1/athletes/{athlete.id}/participations.csv"))[-1]

    assert last["Épreuve"] == "Relais sans date"
    assert last["Date"] == ""
    assert last["Distance (km)"] == ""
    assert last["Statut"] == "dnf"
    assert last["Équipe"] == "Les Requins"


def test_csv_neutralises_spreadsheet_formulas(client, db_session, athlete):
    course = course_repository.get_or_create(
        db_session, name='=HYPERLINK("https://x")', event_date=date(2026, 9, 1),
        event_type="triathlon-s", source_url="https://k/d", provider="manuel",
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="9", club="TCN",
        team_name="@SUM(1)", total_time="-01:00", splits={"=cmd": "+1"},
        is_pending_validation=True,
    )
    db_session.commit()

    row = _rows(client.get(f"/api/v1/athletes/{athlete.id}/participations.csv"))[0]

    assert row["Épreuve"] == "'=HYPERLINK(\"https://x\")"
    assert row["Équipe"] == "'@SUM(1)"
    assert row["Temps"] == "-01:00"
    assert row["Segment =cmd"] == "'+1"


def test_csv_unknown_athlete_is_404(client):
    assert client.get("/api/v1/athletes/999999/participations.csv").status_code == 404


def test_csv_requires_the_site_password(client, athlete):
    from app.api.deps import require_site_access
    from app.main import app

    app.dependency_overrides.pop(require_site_access, None)

    assert client.get(f"/api/v1/athletes/{athlete.id}/participations.csv").status_code == 401
