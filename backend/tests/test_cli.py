from app import cli
from app.core.config import Settings


def _settings() -> Settings:
    return Settings(cache_ttl_in_progress_seconds=600, cache_ttl_finished_seconds=2592000)


def test_normalize_url_trim_casse_slash_fragment():
    variantes = [
        "  https://WWW.Klikego.COM/resultats/event/1/#top  ",
        "https://www.klikego.com/resultats/event/1",
    ]
    assert cli.normalize_url(variantes[0]) == cli.normalize_url(variantes[1])


def test_normalize_url_conserve_la_query():
    a = cli.normalize_url("https://www.klikego.com/e?heat=42")
    b = cli.normalize_url("https://www.klikego.com/e?heat=7")
    assert a != b  # la query distingue deux heats


def test_dedupe_collapse_les_variantes_normalisees():
    links = [
        "https://www.klikego.com/resultats/event/1",
        "https://www.klikego.com/resultats/event/1/",    # slash final
        "https://WWW.KLIKEGO.COM/resultats/event/1",      # casse host
        "https://www.klikego.com/resultats/event/1#top",  # fragment
        "https://www.klikego.com/resultats/event/2",
    ]
    assert cli.dedupe_links(links) == [
        "https://www.klikego.com/resultats/event/1",
        "https://www.klikego.com/resultats/event/2",
    ]


def test_parse_sheet_csv_extrait_la_colonne_par_en_tete():
    csv_text = (
        "Horodateur,Nom,Donne-nous un lien pour accéder aux résultats.\n"
        "x,Jean,https://www.klikego.com/resultats/event/1\n"
        "x,Paul,\n"          # Paul : ligne avec contenu mais sans lien
        ",,\n"                # ligne vide → ignorée
    )
    links, sans_lien = cli.parse_sheet_csv(csv_text)
    assert links == ["https://www.klikego.com/resultats/event/1"]
    assert sans_lien == 1


def test_parse_sheet_csv_repli_sur_index_9_si_en_tete_absent():
    header = ",".join(f"c{i}" for i in range(10))
    row = ",".join(["x"] * 9 + ["https://www.timepulse.fr/e/1"])
    links, _ = cli.parse_sheet_csv(f"{header}\n{row}\n")
    assert links == ["https://www.timepulse.fr/e/1"]


def test_is_supported_playwright_est_faux(monkeypatch):
    from app.scrapers import registry

    monkeypatch.setattr(registry, "detect_provider", lambda url: "playwright")
    assert cli.is_supported("http://x") is False

    monkeypatch.setattr(registry, "detect_provider", lambda url: "klikego")
    assert cli.is_supported("http://x") is True


def test_run_import_sheet_compteurs_et_rapport(db_session, monkeypatch):
    from app.scrapers import registry
    from app.services import import_service

    monkeypatch.setattr(
        registry, "detect_provider",
        lambda url: "klikego" if "klikego" in url else "playwright",
    )
    calls = []

    def _import(db, url, settings, force=False):
        calls.append((url, force))
        return {"imported": 2, "skipped": 1}

    monkeypatch.setattr(import_service, "import_event", _import)

    csv_text = (
        "a,Donne-nous un lien pour accéder aux résultats.\n"
        "x,https://www.klikego.com/e/1\n"
        "x,https://www.klikego.com/e/1/\n"        # doublon du précédent
        "x,https://inconnu.example/e/2\n"          # non supporté
        "x,\n"                                      # sans lien
    )
    out = cli.run_import_sheet(db_session, csv_text, _settings(), delay=0.0)

    assert out.imported == 2
    assert out.skipped == 1
    assert out.errors == 0
    assert out.rows_without_link == 1
    assert out.ignored_by_host == {"inconnu.example": 1}
    assert out.unique_supported == 1
    # 1 seul lien supporté unique, importé avec force=False
    assert calls == [("https://www.klikego.com/e/1", False)]


def test_run_import_sheet_un_echec_n_interrompt_pas_le_batch(db_session, monkeypatch):
    from app.scrapers import registry
    from app.services import import_service

    monkeypatch.setattr(registry, "detect_provider", lambda url: "klikego")

    def _import(db, url, settings, force=False):
        if "boom" in url:
            raise RuntimeError("échec scrape")
        return {"imported": 1, "skipped": 0}

    monkeypatch.setattr(import_service, "import_event", _import)

    csv_text = (
        "a,Donne-nous un lien pour accéder aux résultats.\n"
        "x,https://www.klikego.com/boom\n"
        "x,https://www.klikego.com/ok\n"
    )
    out = cli.run_import_sheet(db_session, csv_text, _settings(), delay=0.0)
    assert out.errors == 1
    assert out.imported == 1


def test_run_import_sheet_dry_run_ne_scrape_pas(db_session, monkeypatch):
    from app.scrapers import registry
    from app.services import import_service

    monkeypatch.setattr(registry, "detect_provider", lambda url: "klikego")
    appels = []
    monkeypatch.setattr(
        import_service, "import_event",
        lambda *a, **k: appels.append(1) or {"imported": 0, "skipped": 0},
    )

    csv_text = (
        "a,Donne-nous un lien pour accéder aux résultats.\n"
        "x,https://www.klikego.com/e/1\n"
    )
    out = cli.run_import_sheet(db_session, csv_text, _settings(), dry_run=True, delay=0.0)
    assert appels == []
    assert out.unique_supported == 1


def test_run_import_sheet_only_provider_restreint(db_session, monkeypatch):
    from app.scrapers import registry
    from app.services import import_service

    monkeypatch.setattr(
        registry, "detect_provider",
        lambda url: "klikego" if "klikego" in url else "timepulse",
    )
    calls = []
    monkeypatch.setattr(
        import_service, "import_event",
        lambda db, url, settings, force=False: calls.append(url) or {"imported": 1, "skipped": 0},
    )

    csv_text = (
        "a,Donne-nous un lien pour accéder aux résultats.\n"
        "x,https://www.klikego.com/e/1\n"
        "x,https://www.timepulse.fr/e/2\n"
    )
    out = cli.run_import_sheet(
        db_session, csv_text, _settings(), only_provider="klikego", delay=0.0
    )
    assert calls == ["https://www.klikego.com/e/1"]
    assert out.imported == 1
