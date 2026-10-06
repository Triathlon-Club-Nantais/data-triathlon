"""Clubs an admin confirmed for an athlete record (#1209)."""
from app.models.athlete import Athlete
from app.repositories import athlete_known_club_repository, ignored_athlete_pair_repository


def _athlete(db, nom="MARTIN", prenom="Thomas") -> Athlete:
    athlete = Athlete(nom=nom, prenom=prenom)
    db.add(athlete)
    db.flush()
    return athlete


def test_added_keys_are_read_back_per_athlete(db_session):
    first, second = _athlete(db_session), _athlete(db_session, "DUPONT", "Jean")
    athlete_known_club_repository.add(db_session, athlete_id=first.id, club_key="vendometriathlon", user_id=None)
    athlete_known_club_repository.add(db_session, athlete_id=first.id, club_key="asptt", user_id=None)

    assert athlete_known_club_repository.keys_by_athlete(db_session, [first.id, second.id]) == {
        first.id: {"vendometriathlon", "asptt"},
    }
    assert athlete_known_club_repository.keys_by_athlete(db_session) == {first.id: {"vendometriathlon", "asptt"}}
    assert athlete_known_club_repository.exists(db_session, athlete_id=first.id, club_key="asptt")
    assert not athlete_known_club_repository.exists(db_session, athlete_id=second.id, club_key="asptt")


def test_repoint_moves_keys_and_drops_duplicates(db_session):
    kept, absorbed = _athlete(db_session), _athlete(db_session, "MARTIN", "Tom")
    athlete_known_club_repository.add(db_session, athlete_id=kept.id, club_key="asptt", user_id=None)
    athlete_known_club_repository.add(db_session, athlete_id=absorbed.id, club_key="asptt", user_id=None)
    athlete_known_club_repository.add(db_session, athlete_id=absorbed.id, club_key="rcnantes", user_id=None)

    moved = athlete_known_club_repository.repoint(db_session, from_athlete_id=absorbed.id, to_athlete_id=kept.id)

    assert moved == 1
    assert athlete_known_club_repository.keys_by_athlete(db_session) == {kept.id: {"asptt", "rcnantes"}}


def test_an_ignored_pair_may_have_no_author(db_session):
    first, second = _athlete(db_session), _athlete(db_session, "MARTIN", "Tom")
    pair = ignored_athlete_pair_repository.create(db_session, athlete_id_a=first.id, athlete_id_b=second.id, user_id=None)

    assert pair.ignored_by_user_id is None
