from datetime import date

from app.core.config import Settings
from app.repositories import course_repository, participation_repository
from app.scrapers.base import ScrapedResult
from app.services import import_service, rescrape_service


def _settings() -> Settings:
    return Settings(cache_ttl_in_progress_seconds=600, cache_ttl_finished_seconds=2592000)


def _course(db, nom: str, url: str, jour: int = 1) -> None:
    course_repository.get_or_create(
        db, name=nom, event_date=date(2026, 1, jour),
        event_type="triathlon-m", source_url=url, provider="klikego",
    )
    db.flush()


def test_run_rescrape_force_et_compte(db_session, monkeypatch):
    _course(db_session, "A", "https://k/1")
    vus: list[tuple[str, bool]] = []

    def _iter(db, url, settings, force=False):
        vus.append((url, force))
        yield {"phase": "done", "imported": 3, "skipped": 0, "total": 3}

    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    out = rescrape_service.run_rescrape_db(db_session, _settings(), delay=0.0)
    assert out.total == 1
    assert out.imported == 3
    assert out.errors == 0
    # force=True : c'est le cœur de la commande
    assert vus == [("https://k/1", True)]


def test_run_rescrape_dry_run_liste_sans_scraper(db_session, monkeypatch):
    _course(db_session, "A", "https://k/1")
    vus: list[str] = []

    def _iter(db, url, settings, force=False):
        vus.append(url)
        yield {"phase": "done", "imported": 0, "skipped": 0, "total": 0}

    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    out = rescrape_service.run_rescrape_db(db_session, _settings(), dry_run=True, delay=0.0)
    assert vus == []
    assert out.dry_run_urls == ["https://k/1"]
    assert out.total == 1


def test_run_rescrape_hors_dry_run_n_embarque_pas_les_urls(db_session, monkeypatch):
    """`dry_run_urls` est une charge utile de dry-run : hors dry-run, la sortie
    `--json` n'a pas à trimbaler l'URL de chaque course (des dizaines de Ko)."""
    _course(db_session, "A", "https://k/1")

    def _iter(db, url, settings, force=False):
        yield {"phase": "done", "imported": 1, "skipped": 0, "total": 1}

    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    out = rescrape_service.run_rescrape_db(db_session, _settings(), delay=0.0)
    assert out.total == 1
    assert out.dry_run_urls == []


def test_run_rescrape_ignore_les_courses_sans_url(db_session, monkeypatch):
    _course(db_session, "SansUrl", "")
    vus: list[str] = []

    def _iter(db, url, settings, force=False):
        vus.append(url)
        yield {"phase": "done", "imported": 0, "skipped": 0, "total": 0}

    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    out = rescrape_service.run_rescrape_db(db_session, _settings(), delay=0.0)
    assert out.total == 0
    assert vus == []


def test_run_rescrape_un_echec_n_interrompt_pas_le_batch(db_session, monkeypatch):
    _course(db_session, "Boom", "https://k/boom", jour=1)
    _course(db_session, "Ok", "https://k/ok", jour=2)

    def _iter(db, url, settings, force=False):
        if "boom" in url:
            yield {"phase": "error", "message": "échec"}
            return
        yield {"phase": "done", "imported": 1, "skipped": 0, "total": 1}

    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    out = rescrape_service.run_rescrape_db(db_session, _settings(), delay=0.0)
    assert out.total == 2
    assert out.errors == 1
    assert out.imported == 1


def test_run_rescrape_dedoublonne_les_courses_partageant_une_url(db_session, monkeypatch):
    """Cas Breizh Chrono : un scrape d'épreuve crée N courses (les heats), toutes
    portées par la même `source_url`. Une seule doit être re-scrapée — sinon on
    frappe N fois le site tiers et on gonfle `skipped` d'autant.
    """
    url = "https://live.breizhchrono.com/external/live5/index.jsp?reference=1488-688"
    for i, nom in enumerate(("Heat 1", "Heat 2", "Heat 3"), start=1):
        _course(db_session, nom, url, jour=i)

    vus: list[str] = []

    def _iter(db, url, settings, force=False):
        vus.append(url)
        yield {"phase": "done", "imported": 2, "skipped": 1, "total": 3}

    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    out = rescrape_service.run_rescrape_db(db_session, _settings(), delay=0.0)

    assert vus == [url]  # un seul scrape, pas trois
    assert out.total == 1  # on compte des épreuves, pas des courses
    assert out.imported == 2
    assert out.skipped == 1


def test_run_rescrape_dry_run_liste_les_urls_uniques(db_session, monkeypatch):
    url = "https://live.breizhchrono.com/external/live5/index.jsp?reference=1488-688"
    _course(db_session, "Heat 1", url, jour=1)
    _course(db_session, "Heat 2", url, jour=2)
    _course(db_session, "Autre", "https://k/2", jour=3)

    out = rescrape_service.run_rescrape_db(db_session, _settings(), dry_run=True, delay=0.0)

    assert out.total == 2
    assert sorted(out.dry_run_urls) == sorted([url, "https://k/2"])


def test_run_rescrape_limit_borne_les_epreuves_pas_les_courses(db_session, monkeypatch):
    """`--limit 1` doit couvrir une épreuve entière, pas une course d'une épreuve."""
    # Les heats sont les plus récents (iter_all trie par date décroissante) : sans
    # dédup, `--limit 2` les consommerait à eux seuls et n'atteindrait jamais B.
    url_a = "https://bc/epreuve-a"
    _course(db_session, "Heat 1", url_a, jour=2)
    _course(db_session, "Heat 2", url_a, jour=3)
    _course(db_session, "Heat 3", url_a, jour=4)
    _course(db_session, "Épreuve B", "https://k/b", jour=1)

    vus: list[str] = []

    def _iter(db, url, settings, force=False):
        vus.append(url)
        yield {"phase": "done", "imported": 1, "skipped": 0, "total": 1}

    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    out = rescrape_service.run_rescrape_db(db_session, _settings(), limit=2, delay=0.0)

    assert out.total == 2
    assert sorted(vus) == sorted([url_a, "https://k/b"])  # 2 épreuves, pas 2 heats


def _scraped(bib: str, nom: str) -> ScrapedResult:
    return ScrapedResult(
        source_url="http://detail",
        provider="klikego",
        athlete_name=nom,
        athlete_firstname="Jean",
        bib_number=bib,
        event_name="Triathlon de Nantes",
        event_date=date(2026, 5, 16),
        event_type="triathlon-m",
        total_time="01:59:00",
    )


def test_run_rescrape_traverse_le_vrai_generateur_et_bypasse_le_cache(db_session, monkeypatch):
    """Jonction réelle de `rescrape-db` : run_batch → **vrai** `iter_import_event(force=True)`.

    Tous les autres tests de batch doublent le générateur ; le seul test de `force`
    sur du vrai code portait sur `import_event`, que la CLI n'appelle jamais. Ici
    on ne double que le scraper (zéro réseau) : le bypass du cache TTL est vérifié
    sur le chemin exact qu'exécute la commande.
    """
    url = "https://www.klikego.com/resultats/event/123"

    def _scraper(resultats: list[ScrapedResult]) -> None:
        monkeypatch.setattr(
            import_service, "registry_scrape_event_all", lambda _u: resultats
        )

    # Une course fraîche en base (scraped_at = maintenant) : le cache TTL mord.
    _scraper([_scraped("1", "DUPONT")])
    import_service.import_event(db_session, url, _settings())

    _scraper([_scraped("1", "DUPONT"), _scraped("2", "MARTIN")])
    out = rescrape_service.run_rescrape_db(db_session, _settings(), delay=0.0)

    assert out.total == 1
    assert out.imported == 1  # force=True : re-scrapé malgré la fraîcheur
    assert out.skipped == 1  # le dossard 1 était déjà en base
    assert len(participation_repository.list_participations(db_session, page_size=100)) == 2


def test_run_rescrape_libelle_avec_le_nom_de_course(db_session, monkeypatch, fake_reporter):
    """Ici le nom vient de la DB : contrairement à import-sheet, on l'a avant le scrape."""
    _course(db_session, "Triathlon de Nantes", "https://k/1")

    def _iter(db, url, settings, force=False):
        yield {"phase": "done", "imported": 1, "skipped": 0, "total": 1}

    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    rescrape_service.run_rescrape_db(db_session, _settings(), delay=0.0, reporter=fake_reporter)

    assert ("item_start", 0, "klikego · Triathlon de Nantes") in fake_reporter.calls


def test_run_rescrape_echec_total_quand_toutes_les_epreuves_echouent(db_session, monkeypatch):
    """Site tiers down : le bilan porte l'échec total, la CLI en tirera son code de sortie."""
    _course(db_session, "A", "https://k/1")
    _course(db_session, "B", "https://k/2", jour=2)

    def _iter(db, url, settings, force=False):
        yield {"phase": "error", "message": "503"}

    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    out = rescrape_service.run_rescrape_db(db_session, _settings(), delay=0.0)

    assert out.errors == 2
    assert out.echec_total is True


def test_run_rescrape_dry_run_n_est_jamais_un_echec_total(db_session, monkeypatch):
    """Un dry-run ne scrape rien : il ne peut pas échouer, même sur 53 courses."""
    _course(db_session, "A", "https://k/1")

    out = rescrape_service.run_rescrape_db(db_session, _settings(), dry_run=True, delay=0.0)

    assert out.total == 1
    assert out.echec_total is False
