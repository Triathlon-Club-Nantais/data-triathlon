from datetime import date, timedelta

import pytest

from app.core.config import Settings
from app.core.exceptions import ProviderNotSupportedError
from app.core.time import utcnow
from app.repositories import course_repository, participation_repository
from app.scrapers.base import ScrapedResult
from app.services import import_service, quality


def _settings() -> Settings:
    return Settings(cache_ttl_in_progress_seconds=600, cache_ttl_finished_seconds=2592000)


def _result(bib, nom, prenom="Jean", **kw) -> ScrapedResult:
    base = dict(
        source_url="http://detail",
        provider="klikego",
        athlete_name=nom,
        athlete_firstname=prenom,
        bib_number=bib,
        event_name="Triathlon de Nantes",
        event_date=date(2026, 5, 16),
        event_type="triathlon-m",
        total_time="01:59:00",
    )
    base.update(kw)
    return ScrapedResult(**base)


@pytest.fixture
def patch_scraper(monkeypatch):
    def _set(results):
        monkeypatch.setattr(
            import_service, "registry_scrape_event_all", lambda url: results
        )
    return _set


URL = "https://www.klikego.com/resultats/event/123"


def test_import_creates_entities(db_session, patch_scraper):
    patch_scraper([_result("1", "DUPONT"), _result("2", "MARTIN")])
    out = import_service.import_event(db_session, URL, _settings())
    assert out == {"imported": 2, "skipped": 0}
    assert len(participation_repository.list_participations(db_session, page_size=100)) == 2


def test_reimport_is_cached_and_skips(db_session, patch_scraper):
    patch_scraper([_result("1", "DUPONT"), _result("2", "MARTIN")])
    import_service.import_event(db_session, URL, _settings())

    # 2e import immédiat → court-circuité par le cache TTL
    out = import_service.import_event(db_session, URL, _settings())
    assert out["cached"] is True
    assert out["imported"] == 0
    assert out["skipped"] == 2


def test_reimport_after_cache_dedups_by_bib(db_session, patch_scraper):
    patch_scraper([_result("1", "DUPONT")])
    import_service.import_event(db_session, URL, _settings())

    # Force l'expiration du cache → re-scrape, mais le dossard 1 existe déjà
    course = course_repository.get_latest_by_source_url(db_session, URL)
    course.scraped_at = utcnow() - timedelta(days=40)
    db_session.flush()

    patch_scraper([_result("1", "DUPONT"), _result("2", "MARTIN")])
    out = import_service.import_event(db_session, URL, _settings())
    assert out == {"imported": 1, "skipped": 1}


def test_import_calcule_l_indice_de_fiabilite(db_session, patch_scraper):
    patch_scraper([_result("1", "DUPONT", rank_overall=1), _result("2", "MARTIN", rank_overall=2)])
    import_service.import_event(db_session, URL, _settings())

    course = course_repository.get_latest_by_source_url(db_session, URL)
    assert course.is_reliable is True
    assert course.quality_issues == {}


def test_import_signale_une_course_suspecte(db_session, patch_scraper):
    # Dossard 1 en double dans la source → la 2e ligne est jetée, jamais persistée.
    # « DQ » est hors de la nomenclature finisher/DNF/DNS/DSQ.
    patch_scraper(
        [
            _result("1", "DUPONT", rank_overall=1),
            _result("1", "MARTIN"),
            _result("3", "DURAND", status="DQ", total_time=""),
        ]
    )
    out = import_service.import_event(db_session, URL, _settings())
    assert out == {"imported": 2, "skipped": 1}

    course = course_repository.get_latest_by_source_url(db_session, URL)
    assert course.is_reliable is False
    assert course.quality_issues == {
        quality.ANOMALY_DUPLICATE_BIB: 1,
        quality.ANOMALY_UNKNOWN_STATUS: 1,
    }


def test_reimport_apres_cache_ne_compte_pas_les_dossards_deja_en_base(
    db_session, patch_scraper
):
    """Un dossard déjà persisté est un skip bénin, pas un doublon de la source."""
    patch_scraper([_result("1", "DUPONT", rank_overall=1)])
    import_service.import_event(db_session, URL, _settings())

    course = course_repository.get_latest_by_source_url(db_session, URL)
    course.scraped_at = utcnow() - timedelta(days=40)  # force l'expiration du cache
    db_session.flush()

    patch_scraper([_result("1", "DUPONT", rank_overall=1), _result("2", "MARTIN", rank_overall=2)])
    out = import_service.import_event(db_session, URL, _settings())
    assert out == {"imported": 1, "skipped": 1}

    db_session.refresh(course)
    assert course.is_reliable is True
    assert course.quality_issues == {}


def _expire_cache(db_session, url=URL):
    """Vieillit la course pour forcer un vrai re-scraping au prochain import."""
    from datetime import timedelta

    from app.core.time import utcnow
    from app.repositories import course_repository

    course = course_repository.get_latest_by_source_url(db_session, url)
    course.scraped_at = utcnow() - timedelta(days=40)
    db_session.flush()


# ---------------------------------------------------------------------------
# Participations sans dossard — le dédoublonnage ne peut pas s'appuyer sur le bib
#
# Certains chronométreurs n'attribuent pas de dossard (Sportinnovation : 5 599
# participations sans bib, dont des finishers). Le repli se fait sur l'athlète,
# en multiset : la même personne peut légitimement figurer plusieurs fois dans
# la source (257 cas réels), et ces occurrences doivent survivre au réimport.
# ---------------------------------------------------------------------------

def test_import_sans_dossard_cree_les_participations(db_session, patch_scraper):
    patch_scraper([_result("", "CASROUGE", "Patrice"), _result("", "HOCHET", "Joséphine")])
    out = import_service.import_event(db_session, URL, _settings())
    assert out == {"imported": 2, "skipped": 0}


def test_reimport_sans_dossard_est_idempotent(db_session, patch_scraper):
    """Le bug : sans dossard, chaque réimport recréait les participations."""
    patch_scraper([_result("", "CASROUGE", "Patrice"), _result("", "HOCHET", "Joséphine")])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    patch_scraper([_result("", "CASROUGE", "Patrice"), _result("", "HOCHET", "Joséphine")])
    out = import_service.import_event(db_session, URL, _settings())
    assert out == {"imported": 0, "skipped": 2}
    assert len(participation_repository.list_participations(db_session, page_size=100)) == 2


def test_import_sans_dossard_conserve_les_homonymes(db_session, patch_scraper):
    """Deux lignes pour le même athlète sans dossard → deux participations."""
    patch_scraper([_result("", "LACOTTE", "Anais"), _result("", "LACOTTE", "Anais")])
    out = import_service.import_event(db_session, URL, _settings())
    assert out == {"imported": 2, "skipped": 0}


def test_reimport_sans_dossard_conserve_le_nombre_d_homonymes(db_session, patch_scraper):
    """Réimport de 2 homonymes : ni doublon, ni perte — on reste à 2."""
    patch_scraper([_result("", "LACOTTE", "Anais"), _result("", "LACOTTE", "Anais")])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    patch_scraper([_result("", "LACOTTE", "Anais"), _result("", "LACOTTE", "Anais")])
    out = import_service.import_event(db_session, URL, _settings())
    assert out == {"imported": 0, "skipped": 2}
    assert len(participation_repository.list_participations(db_session, page_size=100)) == 2


def test_reimport_sans_dossard_ajoute_une_occurrence_supplementaire(db_session, patch_scraper):
    """La source gagne une 3e ligne pour le même athlète → une seule création."""
    patch_scraper([_result("", "LACOTTE", "Anais"), _result("", "LACOTTE", "Anais")])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    patch_scraper([_result("", "LACOTTE", "Anais")] * 3)
    out = import_service.import_event(db_session, URL, _settings())
    assert out == {"imported": 1, "skipped": 2}
    assert len(participation_repository.list_participations(db_session, page_size=100)) == 3


def test_reimport_melange_avec_et_sans_dossard(db_session, patch_scraper):
    """Les deux clés cohabitent sur une même course sans interférer."""
    patch_scraper([_result("1", "DUPONT"), _result("", "CASROUGE", "Patrice")])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    patch_scraper([
        _result("1", "DUPONT"),                  # skip par dossard
        _result("", "CASROUGE", "Patrice"),      # skip par athlète
        _result("2", "MARTIN"),                  # nouveau, avec dossard
        _result("", "HOCHET", "Joséphine"),      # nouveau, sans dossard
    ])
    out = import_service.import_event(db_session, URL, _settings())
    assert out == {"imported": 2, "skipped": 2}
    assert len(participation_repository.list_participations(db_session, page_size=100)) == 4


def test_unsupported_provider_raises(db_session, monkeypatch):
    def _raise(url):
        raise ValueError("Import non supporté")

    monkeypatch.setattr(import_service, "registry_scrape_event_all", _raise)
    with pytest.raises(ProviderNotSupportedError):
        import_service.import_event(db_session, URL, _settings())


def test_force_bypasse_le_cache_ttl(db_session, patch_scraper):
    """Avec force=True, on re-scrape même si la course est fraîche (cache non expiré)."""
    patch_scraper([_result("1", "DUPONT")])
    import_service.import_event(db_session, URL, _settings())

    # Course fraîche → sans force, le cache court-circuite le re-scraping.
    out = import_service.import_event(db_session, URL, _settings())
    assert out.get("cached") is True

    # Avec force=True → re-scrape malgré la fraîcheur ; le dossard 2 est nouveau.
    patch_scraper([_result("1", "DUPONT"), _result("2", "MARTIN")])
    out = import_service.import_event(db_session, URL, _settings(), force=True)
    assert out == {"imported": 1, "skipped": 1}
