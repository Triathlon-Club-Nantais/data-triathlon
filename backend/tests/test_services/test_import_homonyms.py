"""Two bibs on one individual race are two people (#967, epic #1146)."""
from datetime import date

from app.models.athlete import Athlete
from app.models.participation import Participation
from app.repositories import athlete_repository
from app.services import import_service
from tests.test_services.test_import_service import URL, _expire_cache, _relay, _result, _settings

OTHER_URL = "https://www.klikego.com/resultats/event/456"


def _import(db_session, patch_scraper, rows, url=URL) -> dict:
    patch_scraper(rows)
    out = import_service.import_event(db_session, url, _settings())
    db_session.commit()
    return out


def _carrier(db_session, bib: str) -> Athlete:
    return db_session.query(Participation).filter_by(bib_number=bib).one().athlete


def _martins(db_session) -> list[tuple[int, int]]:
    return [
        (a.homonym_rank, len(a.participations))
        for a in db_session.query(Athlete).filter_by(nom="MARTIN").order_by(Athlete.homonym_rank)
    ]


def test_two_bibs_of_one_name_on_an_individual_race_get_two_records(db_session, patch_scraper):
    out = _import(db_session, patch_scraper, [
        _result("1", "MARTIN", "Thomas", category="M25-29"), _result("2", "MARTIN", "Thomas", category="M45-49"),
    ])

    first, second = _carrier(db_session, "1"), _carrier(db_session, "2")
    assert (first.homonym_rank, second.homonym_rank) == (0, 1)
    assert out["homonyms_created"] == [
        {"course_id": second.participations[0].course_id, "bib": "2",
         "athlete_id": second.id, "homonym_of": first.id},
    ]


def test_three_bibs_get_three_records(db_session, patch_scraper):
    _import(db_session, patch_scraper, [_result(bib, "MARTIN", "Thomas") for bib in ("1", "2", "3")])

    assert _martins(db_session) == [(0, 1), (1, 1), (2, 1)]


def test_a_known_runner_on_the_race_makes_a_new_bib_a_homonym(db_session, patch_scraper):
    _import(db_session, patch_scraper, [_result("1", "MARTIN", "Thomas")])
    _expire_cache(db_session)

    out = _import(db_session, patch_scraper, [_result("1", "MARTIN", "Thomas"), _result("2", "MARTIN", "Thomas")])

    assert _martins(db_session) == [(0, 1), (1, 1)]
    assert len(out["homonyms_created"]) == 1


def test_a_rescrape_keeps_both_homonyms_on_their_record(db_session, patch_scraper):
    rows = [_result("1", "MARTIN", "Thomas"), _result("2", "MARTIN", "Thomas")]
    _import(db_session, patch_scraper, rows)
    _expire_cache(db_session)

    out = _import(db_session, patch_scraper, [
        _result("1", "MARTIN", "Thomas", total_time="02:01:00"), _result("2", "MARTIN", "Thomas", total_time="02:02:00"),
    ])

    assert (out["reconciled"], out["homonyms_created"]) == (0, [])
    assert _martins(db_session) == [(0, 1), (1, 1)]


def test_a_new_race_without_conflict_goes_to_the_principal_record(db_session, patch_scraper):
    _import(db_session, patch_scraper, [_result("1", "MARTIN", "Thomas"), _result("2", "MARTIN", "Thomas")])

    _import(db_session, patch_scraper, [
        _result("9", "MARTIN", "Thomas", event_name="Duathlon", event_date=date(2025, 4, 1), source_url=OTHER_URL)
    ], url=OTHER_URL)

    assert _martins(db_session) == [(0, 2), (1, 1)]


def test_a_relay_keeps_one_record_for_one_name(db_session, patch_scraper):
    out = _import(db_session, patch_scraper, [_relay("1", "MARTIN", "Thomas"), _relay("2", "MARTIN", "Thomas")])

    assert _carrier(db_session, "1").id == _carrier(db_session, "2").id
    assert out["homonyms_created"] == []


def test_a_swapped_name_racing_next_to_its_twin_gets_its_own_principal_record(db_session, patch_scraper):
    athlete_repository.get_or_create(db_session, nom="THOMAS", prenom="Martin")
    db_session.commit()

    out = _import(db_session, patch_scraper, [_result("1", "THOMAS", "Martin"), _result("2", "MARTIN", "Thomas")])

    assert (_carrier(db_session, "2").nom, _carrier(db_session, "2").homonym_rank) == ("MARTIN", 0)
    assert out["homonyms_created"] == []


def test_the_report_carries_homonyms_on_every_path(db_session, patch_scraper):
    _import(db_session, patch_scraper, [_result("1", "DUPONT", "Jean")])

    cached = import_service.import_event(db_session, URL, _settings())

    assert cached["homonyms_created"] == []
