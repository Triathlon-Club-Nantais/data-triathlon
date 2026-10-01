"""An admin correction survives rescrapes and later imports (#900, #896, epic #1146)."""
from datetime import date

import pytest

from app.core.exceptions import DuplicateError
from app.models.athlete import Athlete
from app.models.participation import Participation
from app.repositories import athlete_repository, user_repository
from app.services import admin_actions, import_service
from tests.test_services.test_import_service import URL, _expire_cache, _result, _settings

OTHER_URL = "https://www.klikego.com/resultats/event/456"


def _import(db_session, patch_scraper, rows, url=URL) -> dict:
    patch_scraper(rows)
    out = import_service.import_event(db_session, url, _settings())
    db_session.commit()
    return out


def _admin(db_session) -> int:
    admin = user_repository.create(db_session, email="admin@exemple.fr")
    db_session.commit()
    return admin.id


def _martin_elsewhere(db_session, patch_scraper) -> Athlete:
    _import(db_session, patch_scraper, [
        _result("9", "MARTIN", "Paul", event_name="Duathlon", event_date=date(2025, 4, 1), source_url=OTHER_URL)
    ], url=OTHER_URL)
    return athlete_repository.get_by_identity_keys(db_session, "MARTIN", "Paul")


def _rows(db_session, nom: str) -> list[Participation]:
    return db_session.query(Participation).join(Athlete).filter(Athlete.nom == nom).all()


def test_an_admin_set_birth_date_does_not_split_the_record(db_session, patch_scraper):
    """#900 : la fiche datée garde ses résultats et gagne ceux d'une nouvelle épreuve."""
    _import(db_session, patch_scraper, [_result("1", "DUPONT", "Jean")])
    dupont = athlete_repository.get_by_identity_keys(db_session, "DUPONT", "Jean")
    admin_actions.update_athlete(
        db_session, athlete_id=dupont.id, champs={"birth_date": date(1990, 1, 1)}, user_id=_admin(db_session)
    )
    db_session.commit()
    _expire_cache(db_session)

    _import(db_session, patch_scraper, [_result("1", "DUPONT", "Jean", total_time="02:01:00")])
    _import(db_session, patch_scraper, [
        _result("7", "DUPONT", "Jean", event_name="Duathlon", event_date=date(2025, 4, 1), source_url=OTHER_URL)
    ], url=OTHER_URL)

    assert db_session.query(Athlete).filter_by(nom="DUPONT").count() == 1
    assert len(dupont.participations) == 2


def test_a_reassigned_result_with_a_bib_stays_reassigned(db_session, patch_scraper):
    martin = _martin_elsewhere(db_session, patch_scraper)
    _import(db_session, patch_scraper, [_result("1", "DUPONT", "Jean")])
    [moved] = _rows(db_session, "DUPONT")
    admin_actions.reassign_participation(
        db_session, participation_id=moved.id, athlete_id=martin.id, user_id=_admin(db_session)
    )
    db_session.commit()
    _expire_cache(db_session)

    out = _import(db_session, patch_scraper, [_result("1", "DUPONT", "Jean", total_time="02:01:00")])

    assert (out["reconciled"], out["updated"]) == (0, 1)
    assert db_session.get(Participation, moved.id).athlete_id == martin.id
    assert db_session.get(Participation, moved.id).total_time == "02:01:00"
    assert athlete_repository.get_by_identity_keys(db_session, "DUPONT", "Jean") is None


def test_a_reassigned_result_without_a_bib_stays_reassigned_and_unique(db_session, patch_scraper):
    martin = _martin_elsewhere(db_session, patch_scraper)
    _import(db_session, patch_scraper, [_result("", "DUPONT", "Jean")])
    [moved] = _rows(db_session, "DUPONT")
    admin_actions.reassign_participation(
        db_session, participation_id=moved.id, athlete_id=martin.id, user_id=_admin(db_session)
    )
    db_session.commit()
    _expire_cache(db_session)

    out = _import(db_session, patch_scraper, [_result("", "DUPONT", "Jean", total_time="02:01:00")])

    assert out["imported"] == 0
    assert db_session.query(Participation).count() == 2
    assert db_session.get(Participation, moved.id).athlete_id == martin.id
    assert athlete_repository.get_by_identity_keys(db_session, "DUPONT", "Jean") is None


def test_a_never_corrected_result_follows_the_timer_correction(db_session, patch_scraper):
    """FR-014 : le chronométreur corrige « DUPOMT » en « DUPONT », le résultat suit."""
    _import(db_session, patch_scraper, [_result("1", "DUPOMT", "Jean")])
    _expire_cache(db_session)

    out = _import(db_session, patch_scraper, [_result("1", "DUPONT", "Jean")])

    assert out["reconciled"] == 1
    [row] = db_session.query(Participation).all()
    assert (row.athlete.nom, row.source_identity_key) == ("DUPONT", "dupont|jean")


def test_an_admin_rename_is_not_undone_by_the_next_rescrape(db_session, patch_scraper):
    """La source écrit toujours « DUPOMT » : la fiche renommée par l'admin garde son résultat."""
    _import(db_session, patch_scraper, [_result("1", "DUPOMT", "Jean")])
    fiche = athlete_repository.get_by_identity_keys(db_session, "DUPOMT", "Jean")
    admin_actions.update_athlete(
        db_session, athlete_id=fiche.id, champs={"nom": "DUPONT"}, user_id=_admin(db_session)
    )
    db_session.commit()
    _expire_cache(db_session)

    out = _import(db_session, patch_scraper, [_result("1", "DUPOMT", "Jean", total_time="02:01:00")])

    assert out["reconciled"] == 0
    [row] = db_session.query(Participation).all()
    assert row.athlete_id == fiche.id
    assert db_session.query(Athlete).count() == 1


def test_new_participations_record_their_source_identity(db_session, patch_scraper):
    _import(db_session, patch_scraper, [_result("1", "LE GLOANIC", "Léo"), _result("", "L'APPARTIEN", "Marie")])

    keys = sorted(row.source_identity_key for row in db_session.query(Participation))
    assert keys == ["lappartien|marie", "legloanic|leo"]


def test_reassign_locks_the_result(db_session, patch_scraper):
    martin = _martin_elsewhere(db_session, patch_scraper)
    _import(db_session, patch_scraper, [_result("1", "DUPONT", "Jean")])
    [moved] = _rows(db_session, "DUPONT")

    admin_actions.reassign_participation(
        db_session, participation_id=moved.id, athlete_id=martin.id, user_id=_admin(db_session)
    )

    assert moved.athlete_locked is True


def test_renaming_onto_an_equivalent_spelling_of_another_record_is_refused(db_session, patch_scraper):
    _import(db_session, patch_scraper, [_result("1", "LETORT", "Léo"), _result("2", "LETORD", "Leo")])
    letord = athlete_repository.get_by_identity_keys(db_session, "LETORD", "Leo")

    with pytest.raises(DuplicateError):
        admin_actions.update_athlete(
            db_session, athlete_id=letord.id, champs={"nom": "LETORT"}, user_id=_admin(db_session)
        )
