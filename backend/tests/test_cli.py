from app import cli


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
