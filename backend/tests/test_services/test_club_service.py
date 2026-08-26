"""Bucketing des podiums par mode de rang pour /club/summary (#581)."""
from datetime import date

from app.repositories import athlete_repository, course_repository, participation_repository
from app.services import club_service


def _course(db_session, nom, event_type="triathlon-m"):
    return course_repository.get_or_create(
        db_session, name=nom, event_date=date(2026, 5, 16), event_type=event_type
    )


def test_get_club_summary_vide_sans_participation(db_session):
    summary = club_service.get_club_summary(db_session)
    assert summary.roster == []
    assert summary.podiums.scratch == []
    assert summary.podiums.category == []
    assert summary.podiums.gender == []
    assert summary.podiums.all == []


def test_get_club_summary_roster_reprend_les_compteurs_du_repository(db_session):
    ath = athlete_repository.get_or_create(db_session, nom="A", prenom="Alice", club="TCN")
    course = _course(db_session, "C")
    participation_repository.create(
        db_session, athlete_id=ath.id, course_id=course.id, bib_number="1",
        club="TCN", status="finisher", rank_overall=1,
    )
    db_session.flush()

    summary = club_service.get_club_summary(db_session)

    assert len(summary.roster) == 1
    entry = summary.roster[0]
    assert entry.athlete_id == ath.id
    assert entry.nom == "A"
    assert entry.count == 1
    assert entry.podiums == 1
    assert entry.podiums_overall == 1
    assert entry.podiums_gender == 0
    assert entry.podiums_category == 0


def test_get_club_summary_podiums_scratch_ne_prend_que_rank_overall(db_session):
    ath = athlete_repository.get_or_create(db_session, nom="A", prenom="A", club="TCN")
    course = _course(db_session, "C")
    participation_repository.create(
        db_session, athlete_id=ath.id, course_id=course.id, bib_number="1",
        club="TCN", status="finisher", rank_category=1,  # podium cat, pas scratch
    )
    db_session.flush()

    summary = club_service.get_club_summary(db_session)

    assert summary.podiums.scratch == []
    assert len(summary.podiums.category) == 1
    assert summary.podiums.category[0].scope == "category"
    assert summary.podiums.category[0].rank == 1


def test_get_club_summary_podiums_all_prend_le_meilleur_des_trois(db_session):
    # rang égal (5) sur les trois : priorité overall > gender > category,
    # même règle que `_rank_counters`/`bestRank` côté front.
    ath = athlete_repository.get_or_create(db_session, nom="A", prenom="A", club="TCN")
    course = _course(db_session, "C")
    participation_repository.create(
        db_session, athlete_id=ath.id, course_id=course.id, bib_number="1",
        club="TCN", status="finisher", rank_overall=2, rank_gender=2, rank_category=2,
    )
    db_session.flush()

    entry = club_service.get_club_summary(db_session).podiums.all[0]
    assert entry.scope == "overall"
    assert entry.rank == 2


def test_get_club_summary_podiums_gender_exclut_un_genre_non_binaire(db_session):
    # Miroir de stats_service._rank_counters (#376) : le bucket "gender" ne
    # compte que F/M, jamais un genre vide ou hors binaire (#581, revue finale).
    ath = athlete_repository.get_or_create(db_session, nom="A", prenom="A", club="TCN", gender="H")
    course = _course(db_session, "C")
    participation_repository.create(
        db_session, athlete_id=ath.id, course_id=course.id, bib_number="1",
        club="TCN", status="finisher", rank_gender=1,
    )
    db_session.flush()

    summary = club_service.get_club_summary(db_session)

    assert summary.podiums.gender == []
    # Toujours compté en mode "all" — comportement inchangé, aucune
    # restriction de genre sur ce bucket-là.
    assert len(summary.podiums.all) == 1
    assert summary.podiums.all[0].scope == "gender"


def test_get_club_summary_podiums_tries_par_rang_puis_date_desc(db_session):
    ath = athlete_repository.get_or_create(db_session, nom="A", prenom="A", club="TCN")
    ancien = course_repository.get_or_create(
        db_session, name="Ancien", event_date=date(2026, 1, 1), event_type="triathlon-m"
    )
    recent = course_repository.get_or_create(
        db_session, name="Recent", event_date=date(2026, 6, 1), event_type="triathlon-m"
    )
    p_rang3_ancien = participation_repository.create(
        db_session, athlete_id=ath.id, course_id=ancien.id, bib_number="1",
        club="TCN", status="finisher", rank_overall=3,
    )
    p_rang1_recent = participation_repository.create(
        db_session, athlete_id=ath.id, course_id=recent.id, bib_number="2",
        club="TCN", status="finisher", rank_overall=1,
    )
    p_rang3_recent = participation_repository.create(
        db_session, athlete_id=ath.id, course_id=recent.id, bib_number="3",
        club="TCN", status="finisher", rank_overall=3,
    )
    db_session.flush()

    ids = [e.participation_id for e in club_service.get_club_summary(db_session).podiums.scratch]
    # rang 1 en tête, puis les deux rang 3 départagés par date décroissante.
    assert ids == [p_rang1_recent.id, p_rang3_recent.id, p_rang3_ancien.id]
