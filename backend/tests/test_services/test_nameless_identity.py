"""Aucune ligne ne se résout sur l'identité vide (\'\', \'\') (#897).

Une ligne sans nom ni prénom tombait sur une fiche unique, épreuves et
événements confondus : 771 participations en 31 courses sur la fiche 53076.
"""
import logging
from datetime import date

from app.models.athlete import Athlete
from app.models.participation import Participation
from app.scrapers.base import ScrapedResult
from app.services import import_service

URL = "https://exemple.fr/resultats"


def _ligne(bib: str, nom: str = "", event_name: str = "Tri A") -> ScrapedResult:
    return ScrapedResult(
        source_url=URL, provider="timepulse", athlete_name=nom, bib_number=bib,
        event_name=event_name, event_date=date(2026, 6, 1), event_type="triathlon-s",
        total_time="01:00:00",
    )


def test_une_ligne_sans_nom_avec_dossard_recoit_une_identite_par_epreuve(db_session):
    import_service.persist_results(
        db_session, URL, [_ligne("1"), _ligne("2"), _ligne("1", event_name="Tri B")]
    )

    noms = sorted(a.nom for a in db_session.query(Athlete).all())
    assert len(noms) == 3
    assert all(nom.startswith("Anonyme ") for nom in noms)
    assert db_session.query(Athlete).filter(Athlete.nom == "").count() == 0


def test_une_ligne_sans_nom_ni_dossard_est_ecartee_et_journalisee(db_session, caplog):
    with caplog.at_level(logging.WARNING):
        import_service.persist_results(db_session, URL, [_ligne(""), _ligne("", nom="DUPONT")])

    assert [a.nom for a in db_session.query(Athlete).all()] == ["DUPONT"]
    assert db_session.query(Participation).count() == 1
    assert any("without name nor bib" in r.getMessage() for r in caplog.records)


def test_le_rescrape_retrouve_la_meme_identite_synthetique(db_session):
    import_service.persist_results(db_session, URL, [_ligne("1")])
    import_service.persist_results(db_session, URL, [_ligne("1")])

    assert db_session.query(Athlete).count() == 1
    assert db_session.query(Participation).count() == 1



def test_le_rescrape_detache_les_lignes_de_la_fiche_vide_heritee(db_session):
    """Les fiches fourre-tout d'avant #897 : un rescrape les vide, dossard par dossard."""
    from app.repositories import athlete_repository, course_repository, participation_repository

    course = course_repository.get_or_create(
        db_session, name="Tri A", event_date=date(2026, 6, 1), event_type="triathlon-s"
    )
    vide = athlete_repository.get_or_create(db_session, nom="", prenom="")
    participation_repository.create(
        db_session, athlete_id=vide.id, course_id=course.id, bib_number="1"
    )
    db_session.flush()

    import_service.persist_results(db_session, URL, [_ligne("1")])

    participation = db_session.query(Participation).one()
    assert participation.athlete.nom == f"Anonyme {course.id}-1"
