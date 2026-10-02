"""Une fiche porteuse de lignes Challenge n'est ni orpheline ni oubliée (#1008)."""
from datetime import date

from app.models.athlete import Athlete
from app.models.challenge import ChallengeResult
from app.repositories import athlete_repository, challenge_repository, user_repository
from app.services import admin_actions, opposition_service

DAY = date(2026, 5, 13)


def _admin(db):
    admin = user_repository.create(db, email="admin@exemple.fr", display_name="Admin")
    db.flush()
    return admin


def _challenger(db, nom="DUPONT"):
    athlete = Athlete(nom=nom, prenom="Jean")
    db.add(athlete)
    db.flush()
    challenge = challenge_repository.upsert(db, name="C", event_date=DAY, source_url="u")
    challenge_repository.upsert_result(
        db, challenge, athlete_id=athlete.id, bib_number="1", rank_overall=1, rank_gender=None,
        rank_category=None, total_time="06:50:33", status="finisher", raw_data={"nom": nom},
    )
    return athlete


def test_athlete_with_challenge_rows_is_not_an_orphan(db_session):
    athlete = _challenger(db_session)
    assert athlete_repository.delete_orphans_among(db_session, [athlete.id]) == []


def test_wipe_all_courses_removes_challenges_first(db_session):
    admin = _admin(db_session)
    _challenger(db_session)
    admin_actions.wipe_all_courses(db_session, user_id=admin.id)
    assert db_session.query(ChallengeResult).count() == 0
    assert db_session.query(Athlete).count() == 0


def test_wipe_all_participations_removes_challenges_too(db_session):
    admin = _admin(db_session)
    _challenger(db_session)
    admin_actions.wipe_all_participations(db_session, user_id=admin.id)
    assert db_session.query(ChallengeResult).count() == 0


def test_opposition_anonymises_challenge_rows(db_session):
    admin = _admin(db_session)
    athlete = _challenger(db_session)
    assert opposition_service.preview(db_session, athlete_id=athlete.id).results == 1
    opposition_service.apply(db_session, admin, athlete_id=athlete.id, requested_on=DAY)
    row = db_session.query(ChallengeResult).one()
    assert row.athlete.nom.startswith("Anonyme")
    assert row.raw_data == {}
