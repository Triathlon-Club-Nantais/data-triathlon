"""Une opposition tient aux imports (#334) : la personne n'y revient qu'anonyme."""
from datetime import date

import pytest

from app.core.identity import identity_hash
from app.models.athlete import Athlete
from app.models.participation import Participation
from app.repositories import opposition_repository, participation_repository
from app.scrapers.base import ScrapedResult
from app.services import import_service

URL = "https://exemple.fr/resultats"


def _ligne(bib: str, nom: str, prenom: str = "", rang: int = 1, **champs) -> ScrapedResult:
    return ScrapedResult(
        source_url=URL, provider="timepulse", athlete_name=nom, athlete_firstname=prenom, bib_number=bib,
        event_name="Tri A", event_date=date(2026, 6, 1), event_type="triathlon-s",
        total_time="01:00:00", rank_overall=rang, club="BLAIN TRI", category="SEM",
        raw_data={"nom": f"{nom} {prenom}"}, **champs,
    )


@pytest.fixture
def opposition(db_session):
    return opposition_repository.create(
        db_session, identity_hash=identity_hash("Dupont", "Jean-Pierre"),
        requested_on=date(2026, 9, 1), applied_by_user_id=None,
    )


def _noms(db):
    return sorted(f"{a.nom}|{a.prenom}" for a in db.query(Athlete).all())


def test_an_opposed_row_arrives_anonymous_whatever_the_spelling(db_session, opposition):
    import_service.persist_results(
        db_session, URL, [_ligne("12", "JEAN PIERRE", "dupont", rang=12), _ligne("13", "MARTIN", "Alix", rang=13)]
    )

    sienne = db_session.query(Participation).filter_by(bib_number="12").one()
    assert sienne.athlete.nom.startswith("Anonyme ") and sienne.athlete.prenom == ""
    assert not (sienne.club or sienne.category or sienne.raw_data)
    assert (sienne.rank_overall, sienne.total_time) == (12, "01:00:00")
    assert db_session.query(Participation).filter_by(bib_number="13").one().rank_overall == 13
    assert not any("dupont" in nom.lower() for nom in _noms(db_session))


def test_an_opposed_row_without_bib_is_skipped(db_session, opposition):
    import_service.persist_results(db_session, URL, [_ligne("", "Dupont", "Jean-Pierre")])

    assert db_session.query(Participation).count() == 0
    assert _noms(db_session) == []


def test_a_rescrape_keeps_the_row_anonymous_and_recreates_no_record(db_session, opposition):
    import_service.persist_results(db_session, URL, [_ligne("12", "Dupont", "Jean-Pierre")])
    import_service.persist_results(db_session, URL, [_ligne("12", "Dupont", "Jean-Pierre")])

    assert db_session.query(Participation).count() == 1
    assert len(_noms(db_session)) == 1 and _noms(db_session)[0].startswith("Anonyme ")


def test_an_opposition_recorded_before_any_result_blocks_the_first_import(db_session, opposition):
    import_service.persist_results(db_session, URL, [_ligne("7", "DUPONT", "Jean Pierre")])

    assert db_session.query(Participation).one().athlete.nom.startswith("Anonyme ")


def _sans_dupont(db):
    return not any("dupont" in nom.lower() for nom in _noms(db))


def test_a_relay_with_an_opposed_member_arrives_anonymous_as_a_whole(db_session, opposition):
    """Ni découpage ni libellé d'équipe : le libellé publié porte le nom de la personne."""
    import_service.persist_results(
        db_session, URL,
        [_ligne("50", "DUPONT Jean-Pierre / MARTIN Alix", "", is_relay=True, team_name="DUPONT Jean-Pierre / MARTIN Alix")],
    )

    relais = db_session.query(Participation).one()
    assert relais.athlete.nom.startswith("Anonyme ")
    assert participation_repository.teammate_athlete_ids(db_session, relais.id) == []
    assert not (relais.team_name or relais.raw_data or relais.club)
    assert _sans_dupont(db_session)


def test_a_rescraped_relay_with_an_opposed_member_stays_anonymous(db_session, opposition):
    lignes = [
        _ligne("50", "MARTIN Alix / DURAND Paul", "", is_relay=True),
        _ligne("51", "DUPONT Jean-Pierre / MARTIN Alix", "", is_relay=True),
    ]
    import_service.persist_results(db_session, URL, lignes)
    import_service.persist_results(db_session, URL, lignes)

    relais = db_session.query(Participation).filter_by(bib_number="51").one()
    assert relais.athlete.nom.startswith("Anonyme ") and not relais.raw_data
    assert _sans_dupont(db_session)
