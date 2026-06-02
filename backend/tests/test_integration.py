"""
Tests d'intégration — nécessitent un accès réseau réel.

Lancer avec : pytest -m integration

Ces tests utilisent des URLs réelles vérifiées lors du développement.
Pour les tests Klikego, renseignez search=NOM+PRENOM dans l'URL avant de
retirer le @pytest.mark.skip.
"""
import pytest

from scrapers import scrape


# ---------------------------------------------------------------------------
# TimePulse — id_event=3090 (événement avec GOUBAUD Manon, bib=41)
# ---------------------------------------------------------------------------

TP_BIB_URL    = "https://www.timepulse.fr/epreuves/resultats/3090?id_event=3090&bib=41"
TP_SEARCH_URL = "https://www.timepulse.fr/epreuves/resultats/3090?id_event=3090&search=GOUBAUD+Manon"
TP_AMBIG_URL  = "https://www.timepulse.fr/epreuves/resultats/3090?id_event=3090&search=GOUBAUD"


@pytest.mark.integration
def test_timepulse_bib_direct():
    """Accès direct via bib=41 → résultat complet pour GOUBAUD Manon."""
    r = scrape(TP_BIB_URL)

    assert r.provider == "timepulse"
    assert r.athlete_name != ""
    assert r.total_time != ""
    assert r.bib_number == "41"


@pytest.mark.integration
def test_timepulse_search_single():
    """search=GOUBAUD+Manon → un seul athlète résolu, temps total renseigné."""
    r = scrape(TP_SEARCH_URL)

    assert r.provider == "timepulse"
    assert r.bib_number != ""
    assert "GOUBAUD" in r.athlete_name.upper()
    assert r.total_time != ""


@pytest.mark.integration
def test_timepulse_search_multiple_raises():
    """
    search=GOUBAUD → deux athlètes (Céline bib=127, Manon bib=41)
    → ValueError listant les deux noms.
    """
    with pytest.raises(ValueError, match="GOUBAUD"):
        scrape(TP_AMBIG_URL)


# ---------------------------------------------------------------------------
# Klikego — stubs à compléter avec un nom d'athlète réel
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.skip(reason="Ajouter &search=NOM+PRENOM à l'URL pour activer ce test")
def test_klikego_redon_sprint_no_splits():
    """
    Redon Sprint 2026 — pas de splits intermédiaires.
    URL : https://www.klikego.com/resultats/triathlon-de-redon-2026/1759801418691-2
          ?heat=triathlon-s&search=NOM+PRENOM
    """
    url = (
        "https://www.klikego.com/resultats/triathlon-de-redon-2026/1759801418691-2"
        "?heat=triathlon-s&search=NOM+PRENOM"
    )
    r = scrape(url)

    assert r.provider == "klikego"
    assert r.total_time != ""
    assert r.swim_time == "" and r.bike_time == "" and r.run_time == ""


@pytest.mark.integration
@pytest.mark.skip(reason="Ajouter &search=NOM+PRENOM à l'URL pour activer ce test")
def test_klikego_domino_chg_nat_velo():
    """
    Domino Val-de-Loire 2026 — T1/T2 labellisés "Chg Nat." / "Chg Vé.".
    URL : https://www.klikego.com/resultats/triathlon-du-domino-val-de-loire-2026/1646273536851-6
          ?heat=triathlon-m---individuel&search=NOM+PRENOM
    """
    url = (
        "https://www.klikego.com/resultats/triathlon-du-domino-val-de-loire-2026/1646273536851-6"
        "?heat=triathlon-m---individuel&search=NOM+PRENOM"
    )
    r = scrape(url)

    assert r.t1_time != ""
    assert r.t2_time != ""


@pytest.mark.integration
@pytest.mark.skip(reason="Ajouter &search=NOM+PRENOM à l'URL pour activer ce test")
def test_klikego_frenchman_xxl_no_heat():
    """
    Frenchman XXL 2026 — pas de heat= dans l'URL d'origine, auto-détecté.
    URL : https://www.klikego.com/resultats/medoc-atlantique-frenchman-triathlon-carcans-2026/1354050643080-23
          ?search=NOM+PRENOM
    """
    url = (
        "https://www.klikego.com/resultats/medoc-atlantique-frenchman-triathlon-carcans-2026/1354050643080-23"
        "?search=NOM+PRENOM"
    )
    r = scrape(url)

    assert r.provider == "klikego"
    assert r.event_type == "triathlon-xl"
    assert r.total_time != ""


@pytest.mark.integration
@pytest.mark.skip(reason="Ajouter &search=NOM+PRENOM à l'URL pour activer ce test")
def test_klikego_lac_au_duc_format_s():
    """
    Lac au Duc 2025 — heat auto-détecté comme 'format-s-en-individuel' → triathlon-s.
    URL : https://www.klikego.com/resultats/triathlon-du-lac-au-duc-2025/1640295575773-4
          ?search=NOM+PRENOM
    """
    url = (
        "https://www.klikego.com/resultats/triathlon-du-lac-au-duc-2025/1640295575773-4"
        "?search=NOM+PRENOM"
    )
    r = scrape(url)

    assert r.provider == "klikego"
    assert r.event_type == "triathlon-s"


@pytest.mark.integration
@pytest.mark.skip(reason="Ajouter &search=NOM+PRENOM à l'URL pour activer ce test")
def test_klikego_lacanau_cumulative():
    """
    Lacanau 2025 — temps cumulés → le scraper calcule les déltas.
    URL : https://www.klikego.com/resultats/triathlon-de-lacanau-2025/1599610745249-68
          ?search=NOM+PRENOM
    Vérifier que les splits sont cohérents (swim+t1+bike+t2+run ≈ total).
    """
    url = (
        "https://www.klikego.com/resultats/triathlon-de-lacanau-2025/1599610745249-68"
        "?search=NOM+PRENOM"
    )
    r = scrape(url)

    assert r.raw_data.get("cumulative") is True
    # La somme des splits doit reconstituer le temps total (± 1 s d'arrondi)
    def secs(t):
        if not t:
            return 0
        p = t.split(":")
        return int(p[0]) * 3600 + int(p[1]) * 60 + int(p[2])

    total = secs(r.total_time)
    splits_sum = sum(secs(t) for t in [
        r.swim_time, r.t1_time, r.bike_time, r.t2_time, r.run_time
    ])
    assert abs(total - splits_sum) <= 1
