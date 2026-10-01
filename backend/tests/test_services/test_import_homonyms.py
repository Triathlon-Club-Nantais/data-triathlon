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


def test_a_bib_moving_to_another_runner_does_not_make_a_false_homonym(db_session, patch_scraper):
    """#12 passe de MARTIN à DURAND, MARTIN court sous #21 : une seule fiche MARTIN."""
    _import(db_session, patch_scraper, [_result("12", "MARTIN", "Thomas")])
    _expire_cache(db_session)

    out = _import(db_session, patch_scraper, [_result("12", "DURAND", "Paul"), _result("21", "MARTIN", "Thomas")])

    assert out["homonyms_created"] == []
    assert _martins(db_session) == [(0, 1)]
    assert _carrier(db_session, "21").homonym_rank == 0


def test_a_bib_change_between_scrapes_keeps_the_runner_on_the_principal_record(db_session, patch_scraper):
    """MARTIN passe de #12 à #21, #12 disparaît de la source : pas d'homonyme."""
    _import(db_session, patch_scraper, [_result("12", "MARTIN", "Thomas")])
    _expire_cache(db_session)

    out = _import(db_session, patch_scraper, [_result("21", "MARTIN", "Thomas")])

    assert out["homonyms_created"] == []
    assert [rank for rank, _ in _martins(db_session)] == [0]


def test_a_spelling_correction_never_puts_two_bibs_on_one_record(db_session, patch_scraper):
    """FR-008 : « DUPOND » (#2) corrigé en « DUPONT », alors que DUPONT court sous #1."""
    _import(db_session, patch_scraper, [_result("1", "DUPONT", "Jean"), _result("2", "DUPOND", "Jean")])
    _expire_cache(db_session)

    out = _import(db_session, patch_scraper, [_result("1", "DUPONT", "Jean"), _result("2", "DUPONT", "Jean")])

    assert _carrier(db_session, "1").id != _carrier(db_session, "2").id
    assert _carrier(db_session, "2").homonym_rank == 1
    assert len(out["homonyms_created"]) == 1


def test_a_conflict_after_a_fallback_creates_the_row_principal_not_a_homonym(db_session, patch_scraper):
    """Le repli rattache #1 « THOMAS Martin » à « MARTIN Thomas » ; #2 crée la fiche
    principale « THOMAS Martin », jamais un rang 1 sans rang 0."""
    athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Thomas")
    db_session.commit()

    out = _import(db_session, patch_scraper, [_result("1", "THOMAS", "Martin"), _result("2", "THOMAS", "Martin")])

    second = _carrier(db_session, "2")
    assert (second.nom, second.homonym_rank) == ("THOMAS", 0)
    assert out["homonyms_created"] == []


def test_a_conflict_across_two_tranches_is_detected(db_session, patch_scraper, monkeypatch):
    monkeypatch.setattr(import_service, "_TRANCHE_SIZE", 1)

    _import(db_session, patch_scraper, [_result("1", "MARTIN", "Thomas"), _result("2", "MARTIN", "Thomas")])

    assert _martins(db_session) == [(0, 1), (1, 1)]
