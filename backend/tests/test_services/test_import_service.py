from datetime import date, timedelta
from types import SimpleNamespace

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
    assert out == {"imported": 2, "updated": 0, "skipped": 0}
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
    assert out == {"imported": 1, "updated": 0, "skipped": 1}


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
    assert out == {"imported": 2, "updated": 0, "skipped": 1}

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
    assert out == {"imported": 1, "updated": 0, "skipped": 1}

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
    assert out == {"imported": 2, "updated": 0, "skipped": 0}


def test_reimport_sans_dossard_est_idempotent(db_session, patch_scraper):
    """Le bug : sans dossard, chaque réimport recréait les participations."""
    patch_scraper([_result("", "CASROUGE", "Patrice"), _result("", "HOCHET", "Joséphine")])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    patch_scraper([_result("", "CASROUGE", "Patrice"), _result("", "HOCHET", "Joséphine")])
    out = import_service.import_event(db_session, URL, _settings())
    assert out == {"imported": 0, "updated": 0, "skipped": 2}
    assert len(participation_repository.list_participations(db_session, page_size=100)) == 2


def test_import_sans_dossard_conserve_les_homonymes(db_session, patch_scraper):
    """Deux lignes pour le même athlète sans dossard → deux participations."""
    patch_scraper([_result("", "LACOTTE", "Anais"), _result("", "LACOTTE", "Anais")])
    out = import_service.import_event(db_session, URL, _settings())
    assert out == {"imported": 2, "updated": 0, "skipped": 0}


def test_reimport_sans_dossard_conserve_le_nombre_d_homonymes(db_session, patch_scraper):
    """Réimport de 2 homonymes : ni doublon, ni perte — on reste à 2."""
    patch_scraper([_result("", "LACOTTE", "Anais"), _result("", "LACOTTE", "Anais")])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    patch_scraper([_result("", "LACOTTE", "Anais"), _result("", "LACOTTE", "Anais")])
    out = import_service.import_event(db_session, URL, _settings())
    assert out == {"imported": 0, "updated": 0, "skipped": 2}
    assert len(participation_repository.list_participations(db_session, page_size=100)) == 2


def test_reimport_sans_dossard_ajoute_une_occurrence_supplementaire(db_session, patch_scraper):
    """La source gagne une 3e ligne pour le même athlète → une seule création."""
    patch_scraper([_result("", "LACOTTE", "Anais"), _result("", "LACOTTE", "Anais")])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    patch_scraper([_result("", "LACOTTE", "Anais")] * 3)
    out = import_service.import_event(db_session, URL, _settings())
    assert out == {"imported": 1, "updated": 0, "skipped": 2}
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
    assert out == {"imported": 2, "updated": 0, "skipped": 2}
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
    assert out == {"imported": 1, "updated": 0, "skipped": 1}


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
# Upsert prudent par dossard — un réimport corrige les lignes existantes au
# lieu de les ignorer (fusion prudente : la source n'écrase que ses valeurs
# non vides).
# ---------------------------------------------------------------------------


def test_reimport_rafraichit_un_temps_corrige(db_session, patch_scraper):
    """Un temps corrigé à la source met à jour la participation existante."""
    patch_scraper([_result("1", "DUPONT", total_time="01:59:00", rank_overall=5)])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    patch_scraper([_result("1", "DUPONT", total_time="01:58:30", rank_overall=3)])
    out = import_service.import_event(db_session, URL, _settings(), force=True)
    assert out == {"imported": 0, "updated": 1, "skipped": 0}

    parts = participation_repository.list_participations(db_session, page_size=100)
    assert len(parts) == 1
    assert parts[0].total_time == "01:58:30"
    assert parts[0].rank_overall == 3


def test_reimport_valeur_vide_n_ecrase_pas(db_session, patch_scraper):
    """Une valeur vide venue de la source ne remplace jamais une valeur en base."""
    patch_scraper([_result("1", "DUPONT", total_time="01:59:00")])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    # Source temporairement amputée du temps total.
    patch_scraper([_result("1", "DUPONT", total_time="")])
    out = import_service.import_event(db_session, URL, _settings(), force=True)
    assert out == {"imported": 0, "updated": 0, "skipped": 1}

    parts = participation_repository.list_participations(db_session, page_size=100)
    assert parts[0].total_time == "01:59:00"  # survit
    assert parts[0].status == "finisher"       # re-dérivé du temps FUSIONNÉ


def test_reimport_ligne_identique_compte_en_skipped(db_session, patch_scraper):
    """Une ligne inchangée ne déclenche aucun UPDATE : elle compte en skipped."""
    patch_scraper([_result("1", "DUPONT", total_time="01:59:00", rank_overall=2)])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    patch_scraper([_result("1", "DUPONT", total_time="01:59:00", rank_overall=2)])
    out = import_service.import_event(db_session, URL, _settings(), force=True)
    assert out == {"imported": 0, "updated": 0, "skipped": 1}


def test_is_empty_distingue_false_et_zero_des_valeurs_vides():
    """`False` et `0` ne sont pas « vides » : ils peuvent corriger une valeur en base."""
    assert import_service._is_empty(None) is True
    assert import_service._is_empty("") is True
    assert import_service._is_empty({}) is True
    assert import_service._is_empty(False) is False
    assert import_service._is_empty(0) is False


def test_merge_fields_ecrit_false_sur_true_et_ignore_vide_et_cles():
    """Champ non vide et différent → retenu ; `is_relay=False` corrige un `True` ;
    valeur vide ignorée ; clé d'appariement jamais réécrite."""
    existing = SimpleNamespace(is_relay=True, total_time="01:00:00", bib_number="1")
    changes = import_service._merge_fields(
        existing, {"is_relay": False, "total_time": "", "bib_number": "9"}
    )
    assert changes == {"is_relay": False}


def test_reimport_statut_explicite_ecrase(db_session, patch_scraper):
    """Un statut affirmé par le scraper écrase celui en base."""
    patch_scraper([_result("1", "DUPONT", total_time="01:59:00")])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    patch_scraper([_result("1", "DUPONT", total_time="01:59:00", status="DSQ")])
    out = import_service.import_event(db_session, URL, _settings(), force=True)
    assert out == {"imported": 0, "updated": 1, "skipped": 0}
    assert participation_repository.list_participations(db_session, page_size=100)[0].status == "DSQ"


def test_reimport_ajoute_un_nouveau_dossard_et_met_a_jour_l_ancien(db_session, patch_scraper):
    """Mélange : dossard connu corrigé (updated) + dossard neuf (imported)."""
    patch_scraper([_result("1", "DUPONT", total_time="01:59:00")])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    patch_scraper([
        _result("1", "DUPONT", total_time="01:58:00"),  # updated
        _result("2", "MARTIN", total_time="02:05:00"),  # imported
    ])
    out = import_service.import_event(db_session, URL, _settings(), force=True)
    assert out == {"imported": 1, "updated": 1, "skipped": 0}
