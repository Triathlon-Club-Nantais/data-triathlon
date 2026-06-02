"""
Tests d'intégration — nécessitent un accès réseau réel.

Lancer avec : pytest -m integration

Ces tests utilisent des URLs réelles vérifiées lors du développement.
Chaque test est décrit avec l'événement, l'athlète, et ce qui est vérifié.
"""
import pytest

from scrapers import scrape


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _secs(t: str) -> int:
    """Convertit 'HH:MM:SS' en secondes."""
    if not t:
        return 0
    try:
        p = t.split(":")
        return int(p[0]) * 3600 + int(p[1]) * 60 + int(p[2])
    except (IndexError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# TimePulse — id_event=3090 (GOUBAUD Manon, bib=41)
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
# TimePulse — Sablé Dimanche (id_event=2957)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_timepulse_url_without_id_event_param():
    """
    URL sans query param id_event= — l'ID est dans le chemin :
    https://www.timepulse.fr/epreuves/resultats/3090?bib=41
    Doit retourner le même résultat que l'URL canonique.
    """
    r = scrape("https://www.timepulse.fr/epreuves/resultats/3090?bib=41")

    assert r.provider == "timepulse"
    assert r.bib_number == "41"
    assert r.total_time != ""


@pytest.mark.integration
def test_timepulse_sable_dimanche():
    """TimePulse id=2957 — Triathlon de Sablé Dimanche, bib=117 (FLOCARD Guillaume)."""
    r = scrape("https://www.timepulse.fr/resultats/?id_event=2957&bib=117")

    assert r.provider == "timepulse"
    assert r.total_time != ""
    # Au moins un split attendu
    assert any([r.swim_time, r.bike_time, r.run_time])


# ---------------------------------------------------------------------------
# TimePulse — Bike & Run du Bignon (id_event=2917)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_timepulse_bike_run_bignon():
    """TimePulse id=2917 — Bike & Run du Bignon, bib=1 (ARNAUD Adrien)."""
    r = scrape("https://www.timepulse.fr/resultats/?id_event=2917&bib=1")

    assert r.provider == "timepulse"
    assert r.event_type == "bike-run"
    assert r.total_time != ""


# ---------------------------------------------------------------------------
# Klikego — Triathlon L — Coteaux du Vendômois 2026
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_klikego_vendomois_triathlon_l():
    """
    Triathlon des Coteaux du Vendômois 2026 — ERK Frank (V4, RC Vorwarts Speyer).
    Vérifie : provider, event_type=triathlon-l, total_time non vide.
    Note : cet événement n'expose pas de splits intermédiaires (MISSING_SPLITS attendu).
    Heat mis à jour : "swim-bike-longue-distance-individuel" (renommé lors de l'archivage).
    """
    url = (
        "https://www.klikego.com/resultats/"
        "triathlon-des-coteaux-du-vendomois-2026/1695506183783-4"
        "?heat=swim-bike-longue-distance-individuel&search=ERK"
    )
    r = scrape(url)

    assert r.provider == "klikego"
    assert r.event_type == "triathlon-l"
    assert r.total_time != ""


# ---------------------------------------------------------------------------
# Klikego — Duathlon S — 3 Villages 2026
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_klikego_3villages_duathlon_s():
    """
    Duathlon des 3 Villages 2026 — BELLANGER Quentin (S3, Caen Triathlon).
    Vérifie : event_type=duathlon-s, total_time non vide.
    Heat mis à jour : "duathlon-s---indiv" (renommé lors de l'archivage).
    """
    url = (
        "https://www.klikego.com/resultats/"
        "duathlon-des-3-villages-2026-5-eme-edition/1579145109237-15"
        "?heat=duathlon-s---indiv&search=BELLANGER"
    )
    r = scrape(url)

    assert r.provider == "klikego"
    assert r.event_type == "duathlon-s"
    assert r.total_time != ""


# ---------------------------------------------------------------------------
# Klikego — Duathlon S — Cesson-Sévigné 2026 ("Course à pied" labels)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_klikego_cesson_duathlon_s_course_a_pied():
    """
    Duathlons de Cesson-Sévigné 2026 — CORMIER Titouan (S1, Pontivy Triathlon).
    Cet événement utilise 'Course à pied 1' / 'Course à pied 2' comme labels de splits.
    Vérifie : event_type=duathlon-s, bike_time non vide.
    Heat mis à jour : "duathlon-s-visual-open" (renommé lors de l'archivage).
    """
    url = (
        "https://www.klikego.com/resultats/"
        "duathlons-de-cesson-sevigne-2026/1723364024007-2"
        "?heat=duathlon-s-visual-open&search=CORMIER"
    )
    r = scrape(url)

    assert r.provider == "klikego"
    assert r.event_type == "duathlon-s"
    assert r.total_time != ""
    assert r.bike_time != ""


# ---------------------------------------------------------------------------
# Klikego — SwimRun L — Côte Beauté 2025
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_klikego_swimrun_cote_beaute():
    """
    SwimRun Côte Beauté 2025 — DESSENOIX Boris (MA1, T.C.G. 79 Parthenay).
    Vérifie : event_type=swimrun-l (slug swimrun + heat format-l-individuel).
    """
    url = (
        "https://www.klikego.com/resultats/"
        "swimrun-cote-beaute-2025/1643670876505-4"
        "?heat=format-l-individuel&search=DESSENOIX"
    )
    r = scrape(url)

    assert r.provider == "klikego"
    assert r.event_type == "swimrun-l"
    assert r.total_time != ""


# ---------------------------------------------------------------------------
# Klikego — Aquathlon — Des 2 Amants 2025
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_klikego_aquathlon_2amants():
    """
    Aquathlon des 2 Amants 2025 — CREVIER Louis (JU, Les Piranhas).
    Vérifie : event_type=aquathlon, swim_time et run_time non vides.
    Splits : Natation / Transition / CAP — "Transition" seul mappé → t1_time.
    Heat mis à jour : long slug championnat (renommé lors de l'archivage).
    """
    url = (
        "https://www.klikego.com/resultats/"
        "aquathlon-des-2-amants-2025/1643334174070-7"
        "?heat=aquathlon-s-championnat-normandie-cadetsjuniorsseniors-masters&search=CREVIER"
    )
    r = scrape(url)

    assert r.provider == "klikego"
    assert r.event_type == "aquathlon"
    assert r.total_time != ""
    assert r.swim_time != ""
    assert r.run_time != ""
    # "Transition" seul → t1_time (pas de vélo, donc jamais t2)
    assert r.t1_time != ""
    assert r.bike_time == ""


# ---------------------------------------------------------------------------
# Klikego — stubs conservés pour référence (events de tests en cours de saison)
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.skip(reason="Event de 2026 — résultats disponibles uniquement après course")
def test_klikego_redon_sprint_no_splits():
    """
    Redon Sprint 2026 — pas de splits intermédiaires.
    """
    url = (
        "https://www.klikego.com/resultats/triathlon-de-redon-2026/1759801418691-2"
        "?heat=triathlon-s&search=NOM"
    )
    r = scrape(url)

    assert r.provider == "klikego"
    assert r.total_time != ""
    assert r.swim_time == "" and r.bike_time == "" and r.run_time == ""


@pytest.mark.integration
@pytest.mark.skip(reason="Ajouter un athlète réel présent dans cet événement pour activer")
def test_klikego_domino_chg_nat_velo():
    """
    Domino Val-de-Loire 2026 — T1/T2 labellisés "Chg Nat." / "Chg Vé.".
    """
    url = (
        "https://www.klikego.com/resultats/triathlon-du-domino-val-de-loire-2026/1646273536851-6"
        "?heat=triathlon-m---individuel&search=NOM"
    )
    r = scrape(url)

    assert r.t1_time != ""
    assert r.t2_time != ""


@pytest.mark.integration
@pytest.mark.skip(reason="Ajouter un athlète réel pour activer")
def test_klikego_frenchman_xxl_no_heat():
    """
    Frenchman XXL 2026 — pas de heat= dans l'URL d'origine, auto-détecté.
    """
    url = (
        "https://www.klikego.com/resultats/medoc-atlantique-frenchman-triathlon-carcans-2026/1354050643080-23"
        "?search=NOM"
    )
    r = scrape(url)

    assert r.provider == "klikego"
    assert r.event_type == "triathlon-xl"
    assert r.total_time != ""


@pytest.mark.integration
@pytest.mark.skip(reason="Ajouter un athlète réel pour activer")
def test_klikego_lacanau_cumulative():
    """
    Lacanau 2025 — temps cumulés → le scraper calcule les déltas.
    """
    url = (
        "https://www.klikego.com/resultats/triathlon-de-lacanau-2025/1599610745249-68"
        "?search=NOM"
    )
    r = scrape(url)

    assert r.raw_data.get("cumulative") is True
    total = _secs(r.total_time)
    splits_sum = sum(_secs(t) for t in [
        r.swim_time, r.t1_time, r.bike_time, r.t2_time, r.run_time
    ])
    assert abs(total - splits_sum) <= 1
