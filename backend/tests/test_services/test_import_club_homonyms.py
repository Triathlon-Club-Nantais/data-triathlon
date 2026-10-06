"""A result under another club than a member record's goes to a homonym (#1209)."""
from datetime import date

from app.models.athlete import Athlete
from app.models.participation import Participation
from app.repositories import athlete_known_club_repository, ignored_athlete_pair_repository
from app.services import import_service
from tests.test_services.test_import_service import URL, _expire_cache, _result, _settings

TCN = "Triathlon Club Nantais"
VENDOME_URL = "https://www.klikego.com/resultats/event/700"
BLOIS_URL = "https://www.klikego.com/resultats/event/701"


def _import(db_session, patch_scraper, rows, url=URL) -> dict:
    patch_scraper(rows)
    out = import_service.import_event(db_session, url, _settings())
    db_session.commit()
    return out


def _elsewhere(url, club, bib="7", **kw):
    event = {VENDOME_URL: "Triathlon de Vendôme", BLOIS_URL: "Triathlon de Blois"}[url]
    return _result(bib, "MARTIN", "Thomas", club=club, source_url=url, event_name=event,
                   event_date=date(2026, 6, 20), **kw)


def _carrier(db_session, url_event: str) -> Athlete:
    return db_session.query(Participation).join(Participation.course).filter_by(name=url_event).one().athlete


def _member(db_session, patch_scraper) -> Athlete:
    _import(db_session, patch_scraper, [_result("1", "MARTIN", "Thomas", club=TCN)])
    return db_session.query(Athlete).filter_by(nom="MARTIN", homonym_rank=0).one()


def test_another_club_than_a_member_record_creates_a_distinct_homonym(db_session, patch_scraper):
    member = _member(db_session, patch_scraper)

    out = _import(db_session, patch_scraper, [_elsewhere(VENDOME_URL, "Vendôme Triathlon")], url=VENDOME_URL)

    carrier = _carrier(db_session, "Triathlon de Vendôme")
    assert carrier.id != member.id and carrier.homonym_rank == 1
    assert out["homonyms_created"] == [
        {"course_id": carrier.participations[0].course_id, "bib": "7", "athlete_id": carrier.id,
         "homonym_of": member.id},
    ]
    assert ignored_athlete_pair_repository.exists(db_session, athlete_id_a=member.id, athlete_id_b=carrier.id)
    assert member.club == TCN
    assert carrier.participations[0].counts_for_tcn is False


def test_the_same_other_club_later_goes_to_the_same_homonym(db_session, patch_scraper):
    _member(db_session, patch_scraper)
    _import(db_session, patch_scraper, [_elsewhere(VENDOME_URL, "Vendôme Triathlon")], url=VENDOME_URL)

    out = _import(db_session, patch_scraper, [_elsewhere(BLOIS_URL, "VENDOME TRIATHLON")], url=BLOIS_URL)

    assert _carrier(db_session, "Triathlon de Blois").id == _carrier(db_session, "Triathlon de Vendôme").id
    assert out["homonyms_created"] == []


def test_two_rows_of_one_scrape_under_the_same_other_club_share_one_homonym(db_session, patch_scraper):
    member = _member(db_session, patch_scraper)

    out = _import(db_session, patch_scraper, [
        _elsewhere(VENDOME_URL, "Vendôme Triathlon", bib="7"),
        _elsewhere(VENDOME_URL, "Vendôme Triathlon", bib="8", event_type="triathlon-s"),
    ], url=VENDOME_URL)

    carriers = {p.athlete_id for p in db_session.query(Participation).filter(Participation.athlete_id != member.id)}
    assert len(carriers) == 1
    assert len(out["homonyms_created"]) == 1


def test_no_club_a_city_or_a_confirmed_club_stays_on_the_member(db_session, patch_scraper):
    member = _member(db_session, patch_scraper)
    athlete_known_club_repository.add(db_session, athlete_id=member.id, club_key="asptt", user_id=None)
    db_session.commit()

    _import(db_session, patch_scraper, [
        _elsewhere(VENDOME_URL, None, bib="7"),
        _result("8", "MARTIN", "Thomas", club="ASPTT", source_url=VENDOME_URL,
                event_name="Triathlon de Vendôme", event_date=date(2026, 6, 20), event_type="triathlon-s"),
    ], url=VENDOME_URL)

    assert {p.athlete_id for p in db_session.query(Participation)} == {member.id}
    _import(db_session, patch_scraper, [_elsewhere(BLOIS_URL, "nantes (44100)")], url=BLOIS_URL)
    assert _carrier(db_session, "Triathlon de Blois").id == member.id


def test_a_record_outside_the_club_keeps_every_club(db_session, patch_scraper):
    _import(db_session, patch_scraper, [_result("1", "MARTIN", "Thomas", club="AC Rezé")])

    _import(db_session, patch_scraper, [_elsewhere(VENDOME_URL, "Vendôme Triathlon")], url=VENDOME_URL)

    assert db_session.query(Athlete).filter_by(nom="MARTIN").count() == 1


def test_a_rescrape_keeps_the_homonym(db_session, patch_scraper):
    _member(db_session, patch_scraper)
    _import(db_session, patch_scraper, [_elsewhere(VENDOME_URL, "Vendôme Triathlon")], url=VENDOME_URL)
    carrier = _carrier(db_session, "Triathlon de Vendôme")
    _expire_cache(db_session, VENDOME_URL)

    out = _import(db_session, patch_scraper, [_elsewhere(VENDOME_URL, "Vendôme Triathlon")], url=VENDOME_URL)

    assert _carrier(db_session, "Triathlon de Vendôme").id == carrier.id
    assert out["homonyms_created"] == []
