from datetime import date

from app.repositories import athlete_repository, course_repository, participation_repository
from app.services import stats_service


def _seed(db):
    a1 = athlete_repository.get_or_create(db, nom="DUPONT", prenom="Jean", club="TCN")
    a2 = athlete_repository.get_or_create(db, nom="MARTIN", prenom="Paul", club="ASPTT")
    c = course_repository.get_or_create(
        db, name="Tri de Nantes", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    participation_repository.create(db, athlete_id=a1.id, course_id=c.id, bib_number="1", club="TCN")
    participation_repository.create(db, athlete_id=a2.id, course_id=c.id, bib_number="2", club="ASPTT")
    db.flush()


def test_get_stats_global(db_session):
    _seed(db_session)
    stats = stats_service.get_stats(db_session)
    assert stats["total"] == 2
    assert stats["athletes"] == 2
    assert stats["events"] == 1
    assert stats["by_type"] == {"triathlon-m": 2}
    assert stats["by_month"] == {"2026-05": 2}
    assert len(stats["recent"]) == 2


def test_get_stats_filtered_by_club(db_session):
    _seed(db_session)
    stats = stats_service.get_stats(db_session, club="nantais|tcn")
    assert stats["total"] == 1
    assert stats["athletes"] == 1


def test_list_events_counts_tcn(db_session):
    _seed(db_session)
    page = stats_service.list_events(db_session)
    assert page["total_events"] == 1
    assert page["total_participations"] == 2
    assert len(page["items"]) == 1
    event = page["items"][0]
    assert event["total"] == 2
    assert event["tcn_count"] == 1
    assert event["id"] > 0
    assert event["is_relay"] is False


def test_get_stats_filtre_par_saison(db_session):
    a1 = athlete_repository.get_or_create(db_session, nom="DUPONT", prenom="Jean", club="TCN")
    c_2025 = course_repository.get_or_create(
        db_session, name="Tri 2025", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )  # saison 2025
    c_2023 = course_repository.get_or_create(
        db_session, name="Tri 2023", event_date=date(2023, 10, 1), event_type="triathlon-s"
    )  # saison 2023
    participation_repository.create(db_session, athlete_id=a1.id, course_id=c_2025.id, bib_number="1", club="TCN")
    participation_repository.create(db_session, athlete_id=a1.id, course_id=c_2023.id, bib_number="2", club="TCN")
    db_session.flush()

    stats = stats_service.get_stats(db_session, seasons=[2025])
    assert stats["total"] == 1
    assert stats["by_type"] == {"triathlon-m": 1}


def test_list_seasons_force_saison_courante_et_tri_decroissant(db_session, monkeypatch):
    from app.core import season as season_module

    # Saison en cours figée à 2025, sans aucun résultat 2025.
    monkeypatch.setattr(season_module, "current_season", lambda: 2025)

    a1 = athlete_repository.get_or_create(db_session, nom="DUPONT", prenom="Jean", club="TCN")
    c_2023 = course_repository.get_or_create(
        db_session, name="Tri 2023", event_date=date(2023, 10, 1), event_type="triathlon-s"
    )
    c_2022 = course_repository.get_or_create(
        db_session, name="Tri 2022", event_date=date(2022, 10, 1), event_type="triathlon-s"
    )
    participation_repository.create(db_session, athlete_id=a1.id, course_id=c_2023.id, bib_number="1", club="TCN")
    participation_repository.create(db_session, athlete_id=a1.id, course_id=c_2022.id, bib_number="2", club="TCN")
    db_session.flush()

    seasons = stats_service.list_seasons(db_session)
    years = [s["start_year"] for s in seasons]
    assert years == [2025, 2023, 2022]  # courante forcée en tête, puis décroissant
    current = next(s for s in seasons if s["start_year"] == 2025)
    assert current["is_current"] is True
    assert current["event_count"] == 0
    assert current["label"] == "Saison 2025 — 2026"
    assert seasons[1]["is_current"] is False
