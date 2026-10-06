"""Un rescrape qui publie une autre identité met l'épreuve à jour en place (#1204, #1197).

L'identité d'une `Course` est `(name, event_date, event_type, is_relay)`. Quand le
fournisseur renomme l'épreuve sous la même URL (Wiclax qui retire l'année :
« Triathlon de Vertou 2025 - Triathlon S » devient « Triathlon de Vertou -
Triathlon S ») ou qu'elle passe en relais (#963), l'identité ne se retrouvait
plus : 44 épreuves recréées à côté des anciennes, et 28 paires solo/relais, au
rescrape de la MEP v0.8.0, résultats comptés deux fois.

Comme pour la reclassification (#294), le signal n'existe qu'au niveau du lot :
une URL publie légitimement plusieurs heats. Ici ce sont les **dossards** qui
tranchent : l'épreuve en place sous cette URL, absente de ce scrape, dont les
dossards sont repris par l'identité neuve, est la même épreuve.
"""
from datetime import date

from app.core.config import Settings
from app.models.course import Course
from app.models.course_source import CourseSource
from app.scrapers.base import ScrapedResult
from app.services import import_service

WICLAX = "https://www.chronosmetron.com/717-triathlon-de-vertou-2025"
JOUR = date(2025, 5, 3)
ANCIEN = "Triathlon de Vertou 2025 - Triathlon S"
NOUVEAU = "Triathlon de Vertou - Triathlon S"


def _settings() -> Settings:
    return Settings(cache_ttl_in_progress_seconds=600, cache_ttl_finished_seconds=2592000)


def _result(bib: str, *, name: str, event_type: str = "triathlon-s", is_relay: bool = False) -> ScrapedResult:
    return ScrapedResult(
        source_url=WICLAX,
        provider="wiclax",
        athlete_name=f"NOM-{bib}",
        athlete_firstname="Jean",
        bib_number=bib,
        event_name=name,
        event_date=JOUR,
        event_type=event_type,
        is_relay=is_relay,
        total_time="01:10:00",
    )


def _importer(db, patch_scraper, resultats) -> None:
    patch_scraper(resultats)
    phases = list(import_service.iter_import_event(db, WICLAX, _settings(), force=True))
    assert phases[-1]["phase"] == "done", phases[-1]


def _bibs(course: Course) -> set[str]:
    return {p.bib_number for p in course.participations}


def test_a_renamed_event_is_renamed_in_place(db_session, patch_scraper):
    _importer(db_session, patch_scraper, [_result(b, name=ANCIEN) for b in "123"])
    (avant,) = db_session.query(Course).all()

    _importer(db_session, patch_scraper, [_result(b, name=NOUVEAU) for b in "123"])

    (epreuve,) = db_session.query(Course).all()
    assert epreuve.id == avant.id
    assert epreuve.name == NOUVEAU
    assert _bibs(epreuve) == {"1", "2", "3"}


def test_a_team_course_typed_solo_becomes_relay_in_place(db_session, patch_scraper):
    """#1197 : `is_relay` entre dans l'identité depuis #963."""
    _importer(db_session, patch_scraper, [_result(b, name=ANCIEN) for b in "12"])

    _importer(db_session, patch_scraper, [_result(b, name=ANCIEN, is_relay=True) for b in "12"])

    (epreuve,) = db_session.query(Course).all()
    assert epreuve.is_relay is True
    assert _bibs(epreuve) == {"1", "2"}


def test_only_the_renamed_heat_moves_among_heats_of_one_url(db_session, patch_scraper):
    autre = "Triathlon de Vertou 2025 - Triathlon M"
    _importer(
        db_session, patch_scraper,
        [_result(b, name=ANCIEN) for b in "12"]
        + [_result(b, name=autre, event_type="triathlon-m") for b in "89"],
    )

    _importer(
        db_session, patch_scraper,
        [_result(b, name=NOUVEAU) for b in "12"]
        + [_result(b, name=autre, event_type="triathlon-m") for b in "89"],
    )

    noms = {c.name: _bibs(c) for c in db_session.query(Course).all()}
    assert noms == {NOUVEAU: {"1", "2"}, autre: {"8", "9"}}


def test_a_new_heat_with_other_bibs_is_a_new_course(db_session, patch_scraper):
    """Un heat ajouté à la page n'emporte pas l'épreuve qui a disparu du scrape."""
    _importer(db_session, patch_scraper, [_result(b, name=ANCIEN) for b in "12"])

    _importer(db_session, patch_scraper, [_result(b, name=NOUVEAU) for b in "89"])

    noms = {c.name: _bibs(c) for c in db_session.query(Course).all()}
    assert noms == {ANCIEN: {"1", "2"}, NOUVEAU: {"8", "9"}}


def test_an_admin_identity_correction_is_kept(db_session, patch_scraper):
    """Un nom corrigé à la main (`course.update`, FR-020) ne revient pas au nom publié."""
    from app.repositories import admin_action_log_repository, user_repository

    _importer(db_session, patch_scraper, [_result(b, name=ANCIEN) for b in "12"])
    (epreuve,) = db_session.query(Course).all()
    admin = user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")
    epreuve.name = "Triathlon de Vertou 2025 - S"
    admin_action_log_repository.create(
        db_session, user_id=admin.id, action="course.update", entity_type="course",
        entity_id=epreuve.id, payload={},
    )
    db_session.commit()

    _importer(db_session, patch_scraper, [_result(b, name=NOUVEAU) for b in "12"])

    assert db_session.get(Course, epreuve.id).name == "Triathlon de Vertou 2025 - S"


def test_a_passive_source_never_renames_the_course(db_session, patch_scraper):
    """La source active fait foi sur l'identité (D2, #303)."""
    _importer(db_session, patch_scraper, [_result(b, name=ANCIEN) for b in "12"])
    (avant,) = db_session.query(Course).all()
    db_session.query(CourseSource).update({CourseSource.is_active: False})
    db_session.flush()

    _importer(db_session, patch_scraper, [_result(b, name=NOUVEAU) for b in "12"])

    assert db_session.get(Course, avant.id).name == ANCIEN
