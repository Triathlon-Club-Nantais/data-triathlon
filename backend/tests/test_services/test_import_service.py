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
    assert out == {"imported": 2, "skipped": 0, "reconciled": 0}
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
    assert out == {"imported": 1, "skipped": 1, "reconciled": 0}


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
    assert out == {"imported": 2, "skipped": 1, "reconciled": 0}

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
    assert out == {"imported": 1, "skipped": 1, "reconciled": 0}

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
    assert out == {"imported": 2, "skipped": 0, "reconciled": 0}


def test_reimport_sans_dossard_est_idempotent(db_session, patch_scraper):
    """Le bug : sans dossard, chaque réimport recréait les participations."""
    patch_scraper([_result("", "CASROUGE", "Patrice"), _result("", "HOCHET", "Joséphine")])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    patch_scraper([_result("", "CASROUGE", "Patrice"), _result("", "HOCHET", "Joséphine")])
    out = import_service.import_event(db_session, URL, _settings())
    assert out == {"imported": 0, "skipped": 2, "reconciled": 0}
    assert len(participation_repository.list_participations(db_session, page_size=100)) == 2


def test_import_sans_dossard_conserve_les_homonymes(db_session, patch_scraper):
    """Deux lignes pour le même athlète sans dossard → deux participations."""
    patch_scraper([_result("", "LACOTTE", "Anais"), _result("", "LACOTTE", "Anais")])
    out = import_service.import_event(db_session, URL, _settings())
    assert out == {"imported": 2, "skipped": 0, "reconciled": 0}


def test_reimport_sans_dossard_conserve_le_nombre_d_homonymes(db_session, patch_scraper):
    """Réimport de 2 homonymes : ni doublon, ni perte — on reste à 2."""
    patch_scraper([_result("", "LACOTTE", "Anais"), _result("", "LACOTTE", "Anais")])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    patch_scraper([_result("", "LACOTTE", "Anais"), _result("", "LACOTTE", "Anais")])
    out = import_service.import_event(db_session, URL, _settings())
    assert out == {"imported": 0, "skipped": 2, "reconciled": 0}
    assert len(participation_repository.list_participations(db_session, page_size=100)) == 2


def test_reimport_sans_dossard_ajoute_une_occurrence_supplementaire(db_session, patch_scraper):
    """La source gagne une 3e ligne pour le même athlète → une seule création."""
    patch_scraper([_result("", "LACOTTE", "Anais"), _result("", "LACOTTE", "Anais")])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    patch_scraper([_result("", "LACOTTE", "Anais")] * 3)
    out = import_service.import_event(db_session, URL, _settings())
    assert out == {"imported": 1, "skipped": 2, "reconciled": 0}
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
    assert out == {"imported": 2, "skipped": 2, "reconciled": 0}
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
    assert out == {"imported": 1, "skipped": 1, "reconciled": 0}


def test_iter_import_event_force_bypasse_le_cache_ttl(db_session, patch_scraper):
    """Même garde que ci-dessus, mais sur le **générateur** — le chemin de prod.

    `rescrape-db` ne passe pas par `import_event` : `batch.run_batch` consomme
    `iter_import_event(force=True)`. C'est donc ici que se joue le bypass du
    cache TTL. Sans ce test, inverser la garde (`if not force:` → `if force:`)
    transformerait le rescrape en no-op silencieux sur toute course fraîche
    (bilan « Importées : 0 », indiscernable d'un rescrape sans nouveauté).
    """
    patch_scraper([_result("1", "DUPONT")])
    import_service.import_event(db_session, URL, _settings())

    # Course fraîche, sans force → le générateur court-circuite le scraping.
    phases = list(import_service.iter_import_event(db_session, URL, _settings()))
    assert [p["phase"] for p in phases] == ["done"]
    assert phases[-1]["cached"] is True

    # force=True → la phase `scraping` a bien lieu malgré la fraîcheur, et le
    # dossard 2 (nouveau) est importé : le cache n'a pas été consulté.
    patch_scraper([_result("1", "DUPONT"), _result("2", "MARTIN")])
    phases = list(
        import_service.iter_import_event(db_session, URL, _settings(), force=True)
    )
    assert "scraping" in [p["phase"] for p in phases]
    final = phases[-1]
    assert final["phase"] == "done"
    assert (final["imported"], final["skipped"]) == (1, 1)
    assert "cached" not in final
    assert len(participation_repository.list_participations(db_session, page_size=100)) == 2


# ---------------------------------------------------------------------------
# Garde-fou : une épreuve sans nom n'est jamais persistée
# ---------------------------------------------------------------------------


def test_import_refuses_event_without_name(db_session, patch_scraper):
    """Un scrape qui ne trouve pas le nom de l'épreuve échoue, sans rien écrire.

    Sans ce garde-fou, une course sans nom se retrouve en base (cas réel de la
    course 103, importée depuis une URL `coureur.jsp` sans slug) : illisible
    dans l'UI, et invisible à la recherche.
    """
    from app.core.exceptions import ScraperError

    patch_scraper([_result("1", "DUPONT", event_name=""), _result("2", "MARTIN", event_name="")])

    with pytest.raises(ScraperError):
        import_service.import_event(db_session, URL, _settings())

    assert course_repository.list_all(db_session) == []
    assert participation_repository.list_participations(db_session, page_size=100) == []


def test_iter_import_refuses_event_without_name(db_session, patch_scraper):
    """Même refus côté SSE : une phase `error` explicite, aucune course créée."""
    patch_scraper([_result("1", "DUPONT", event_name="")])

    phases = list(import_service.iter_import_event(db_session, URL, _settings()))

    assert phases[-1]["phase"] == "error"
    assert "nom" in phases[-1]["message"].lower()
    assert course_repository.list_all(db_session) == []


# ---------------------------------------------------------------------------
# Réconciliation d'identité au re-scrape (issue #66)
# ---------------------------------------------------------------------------

def test_dossard_connu_athlete_divergent_est_reconcilie(db_session, patch_scraper):
    """La graphie fautive stockée est réassignée vers la graphie corrigée."""
    patch_scraper([_result("1", "BERRE", "Audrey LE")])
    import_service.import_event(db_session, URL, _settings())

    # Même dossard, identité corrigée. force=True : re-scrape malgré le cache frais.
    patch_scraper([_result("1", "LE BERRE", "Audrey")])
    out = import_service.import_event(db_session, URL, _settings(), force=True)

    assert out["reconciled"] == 1
    assert out["imported"] == 0
    parts = participation_repository.list_participations(db_session, page_size=100)
    assert len(parts) == 1
    assert (parts[0].athlete.nom, parts[0].athlete.prenom) == ("LE BERRE", "Audrey")


def test_dossard_connu_meme_athlete_reste_un_skip(db_session, patch_scraper):
    """Identité inchangée : aucune réassignation, `skipped` comme aujourd'hui."""
    patch_scraper([_result("1", "LE BERRE", "Audrey")])
    import_service.import_event(db_session, URL, _settings())

    patch_scraper([_result("1", "LE BERRE", "Audrey")])
    out = import_service.import_event(db_session, URL, _settings(), force=True)

    assert out["reconciled"] == 0
    assert out["skipped"] == 1


def test_reconciliation_fusionne_vers_un_athlete_existant(db_session, patch_scraper):
    """La cible corrigée existe déjà (autre course) → fusion, pas de création."""
    from app.repositories import athlete_repository

    # La graphie fautive, sur l'épreuve à re-scraper.
    patch_scraper([_result("1", "BERRE", "Audrey LE")])
    import_service.import_event(db_session, URL, _settings())
    # La graphie correcte existe déjà, portée par une autre épreuve.
    url2 = "https://www.klikego.com/resultats/event/999"
    patch_scraper([_result("7", "LE BERRE", "Audrey", event_name="Autre Tri")])
    import_service.import_event(db_session, url2, _settings())

    nb_athletes = len(athlete_repository.search(db_session, page_size=500))

    # Re-scrape de la 1re épreuve : la graphie fautive fusionne vers l'existante.
    patch_scraper([_result("1", "LE BERRE", "Audrey")])
    phases = list(import_service.iter_import_event(db_session, URL, _settings(), force=True))
    done = phases[-1]

    assert done["reconciled"] == 1
    assert done["reassignments"][0].fusion is True
    assert done["reassignments"][0].ancien == "BERRE | Audrey LE"
    assert done["reassignments"][0].nouveau == "LE BERRE | Audrey"
    # Aucun athlète créé : fusion, pas renommage.
    assert len(athlete_repository.search(db_session, page_size=500)) == nb_athletes


def test_reconciliation_ne_vide_jamais_le_prenom(db_session, patch_scraper):
    """Garde des ambigus : une correction qui viderait le prénom est refusée."""
    # Prénom stocké en majuscules par un fournisseur à champs séparés.
    patch_scraper([_result("1", "BERGE", "LOLA")])
    import_service.import_event(db_session, URL, _settings())

    # Le re-scrape produirait ("LOLA BERGE", "") — destruction du prénom.
    patch_scraper([_result("1", "LOLA BERGE", "")])
    out = import_service.import_event(db_session, URL, _settings(), force=True)

    assert out["reconciled"] == 0
    assert out["skipped"] == 1
    parts = participation_repository.list_participations(db_session, page_size=100)
    assert (parts[0].athlete.nom, parts[0].athlete.prenom) == ("BERGE", "LOLA")
