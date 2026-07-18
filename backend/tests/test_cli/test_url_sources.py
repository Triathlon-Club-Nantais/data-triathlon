import pytest
import typer

from app.cli import url_sources


def test_aucun_ciblage_renvoie_none():
    """None (et non []) : « pas de ciblage demandé » ≠ « liste vide »."""
    assert url_sources.charger_urls([], None) is None


def test_url_repetee_conserve_l_ordre():
    assert url_sources.charger_urls(["https://k/1", "https://k/2"], None) == [
        "https://k/1",
        "https://k/2",
    ]


def test_urls_from_fichier(tmp_path):
    fichier = tmp_path / "echecs.txt"
    fichier.write_text("https://k/1\nhttps://k/2\n", encoding="utf-8")

    assert url_sources.charger_urls([], str(fichier)) == ["https://k/1", "https://k/2"]


def test_url_et_urls_from_se_cumulent(tmp_path):
    """Ajouter une URL à une liste est un besoin légitime : les deux se cumulent."""
    fichier = tmp_path / "echecs.txt"
    fichier.write_text("https://k/2\n", encoding="utf-8")

    assert url_sources.charger_urls(["https://k/1"], str(fichier)) == [
        "https://k/1",
        "https://k/2",
    ]


def test_urls_from_tiret_lit_stdin(monkeypatch):
    import io
    import sys

    monkeypatch.setattr(sys, "stdin", io.StringIO("https://k/1\nhttps://k/2\n"))

    assert url_sources.charger_urls([], "-") == ["https://k/1", "https://k/2"]


def test_urls_from_tiret_bom_n_altere_pas_la_premiere_url(monkeypatch):
    """Même bug que le fichier (BOM Notepad/Excel), côté stdin : `cat … | --urls-from -`."""
    import io
    import sys

    monkeypatch.setattr(sys, "stdin", io.StringIO("﻿https://k/1\nhttps://k/2\n"))

    assert url_sources.charger_urls([], "-") == ["https://k/1", "https://k/2"]


def test_lignes_vides_et_commentaires_ignorees(tmp_path):
    """Un opérateur commente une URL plutôt que de la supprimer."""
    fichier = tmp_path / "echecs.txt"
    fichier.write_text(
        "# épreuves du 12/07\nhttps://k/1\n\n  \n#https://k/2\n", encoding="utf-8"
    )

    assert url_sources.charger_urls([], str(fichier)) == ["https://k/1"]


def test_fichier_vide_renvoie_liste_vide(tmp_path):
    """[] et non None : le ciblage a bien été demandé → zéro épreuve, code 0."""
    fichier = tmp_path / "vide.txt"
    fichier.write_text("", encoding="utf-8")

    assert url_sources.charger_urls([], str(fichier)) == []


def test_ligne_non_http_cite_le_numero_de_ligne(tmp_path):
    fichier = tmp_path / "echecs.txt"
    fichier.write_text("https://k/1\nsalut\n", encoding="utf-8")

    with pytest.raises(typer.BadParameter) as exc:
        url_sources.charger_urls([], str(fichier))

    assert "ligne 2" in str(exc.value)
    assert "salut" in str(exc.value)


def test_url_option_non_http_rejetee():
    with pytest.raises(typer.BadParameter) as exc:
        url_sources.charger_urls(["ftp://k/1"], None)

    assert "ftp://k/1" in str(exc.value)


def test_fichier_introuvable_rejete(tmp_path):
    with pytest.raises(typer.BadParameter) as exc:
        url_sources.charger_urls([], str(tmp_path / "absent.txt"))

    assert "absent.txt" in str(exc.value)


def test_fichier_avec_bom_utf8_n_altere_pas_la_premiere_url(tmp_path):
    """Un export Notepad/Excel « UTF-8 avec BOM » ne doit pas polluer la 1ère URL."""
    fichier = tmp_path / "echecs.txt"
    fichier.write_bytes("https://k/1\nhttps://k/2\n".encode("utf-8-sig"))

    assert url_sources.charger_urls([], str(fichier)) == ["https://k/1", "https://k/2"]


def test_fichier_non_utf8_rejete_avec_message_parlant(tmp_path):
    """Un byte non-UTF8 (0xff) doit être rejeté par BadParameter, pas par une trace brute."""
    fichier = tmp_path / "echecs.txt"
    fichier.write_bytes(b"\xff\xfe\x00\x01")

    with pytest.raises(typer.BadParameter) as exc:
        url_sources.charger_urls([], str(fichier))

    assert "encod" in str(exc.value).lower()


def test_dedoublonne_en_conservant_la_forme_d_origine():
    """Casse d'hôte et slash final : une seule épreuve, forme d'origine gardée."""
    urls = url_sources.charger_urls(
        ["https://Klikego.com/e/1", "https://klikego.com/e/1/"], None
    )

    assert urls == ["https://Klikego.com/e/1"]


def test_ciblage_exclusif_accepte_le_mode_base():
    url_sources.valider_ciblage_exclusif(
        url=[], urls_from=None, provider="klikego", older_than=30
    )


def test_ciblage_exclusif_accepte_les_urls_seules():
    url_sources.valider_ciblage_exclusif(
        url=["https://k/1"], urls_from=None, provider=None, older_than=None
    )


def test_ciblage_exclusif_refuse_url_avec_provider():
    with pytest.raises(typer.BadParameter) as exc:
        url_sources.valider_ciblage_exclusif(
            url=["https://k/1"], urls_from=None, provider="klikego", older_than=None
        )

    assert "--provider" in str(exc.value)


def test_ciblage_exclusif_refuse_url_avec_older_than():
    """`urls_from` seul (sans `--url`) suffit à déclencher le ciblage."""
    with pytest.raises(typer.BadParameter) as exc:
        url_sources.valider_ciblage_exclusif(
            url=[], urls_from="echecs.txt", provider=None, older_than=30
        )

    assert "--older-than" in str(exc.value)


def test_ciblage_exclusif_valide_avant_toute_lecture():
    """Verrouille le correctif : la validation ne doit rien lire (fichier/stdin).

    Passer un chemin de fichier inexistant à `urls_from` doit tout de même
    déclencher le rejet d'exclusivité — la fonction ne doit jamais tenter de
    l'ouvrir.
    """
    with pytest.raises(typer.BadParameter) as exc:
        url_sources.valider_ciblage_exclusif(
            url=[], urls_from="/chemin/qui-n-existe-pas.txt", provider="klikego", older_than=None
        )

    assert "--provider" in str(exc.value)
