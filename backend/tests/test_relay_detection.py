"""Chaque fournisseur passe par le détecteur d'équipe commun (#963).

Un test par fournisseur, avec le libellé réel qu'il laissait passer en solo :
la liste de mots vit dans `utils.heat_is_relay`, ces tests vérifient seulement
que chacun la consulte, en plus de ses propres marqueurs.
"""
import xml.etree.ElementTree as ET

from app.scrapers import (
    chronoplace,
    chronoweb,
    klikego_platform,
    oktime,
    prolivesport,
    raceresult,
    runnerbreizh,
    sporthive,
    timepulse,
    wiclax,
)


def test_raceresult_duo_contest_is_a_team_event():
    """Course 342, « Swimrun Côte de Jade S Duo » : 144 lignes d'équipe typées solo."""
    r = raceresult._build_result(
        [], {}, [], {},
        source_url="u", event_name="Swimrun Côte de Jade", event_date=None,
        contest_label="S Duo", status_label="",
    )

    assert r.is_relay is True


def test_wiclax_duo_and_team_parcours_are_team_events():
    """RED OUF S Duo (439) et Armorun « en Equipe » (773)."""
    for parcours in ("S Duo", "Trail en Equipe"):
        comp = ET.fromstring(f'<E n="DUPONT" p="{parcours}"/>')

        assert wiclax._parse_competitor(comp, "u", "RED OUF", "swimrun").is_relay is True


def test_timepulse_team_parcours_is_a_team_event():
    """Triathlon de Sablé « ÉQUIPE M » (855, 881, 882), catégorie non EQ*."""
    assert timepulse._is_relay("ÉQUIPE M", "SEH") is True
    assert timepulse._is_relay("SOLO M", "EQX") is True
    assert timepulse._is_relay("SOLO M", "SEH") is False


def test_klikego_platform_glued_and_plural_forms_are_team_events():
    """Klikego 392 « RelaisM », 398 « équipes », Breizh Chrono 377 « Relai »."""
    for heat in ("Triathlon RelaisM", "Triathlon S par équipes", "Triathlon M Relai"):
        assert klikego_platform.heat_is_relay(heat) is True


def test_chronoplace_binome_category_is_a_team_event():
    r = chronoplace._build_result(
        {"position": "1", "nom": "A / B", "temps": "01:00:00", "categorie": "Binôme mixte"},
        url="u", event_name="E", event_type="bike-and-run", event_date=None, is_team=False,
    )

    assert r.is_relay is True


def test_chronoweb_team_label_is_a_team_event():
    assert chronoweb._is_relay("Swimrun par Équipe") is True
    assert chronoweb._is_relay("Swimrun Solo") is False


def test_sporthive_binome_race_is_a_team_event():
    assert sporthive._is_relay("Bike and Run Binômes") is True


def test_oktime_binome_title_is_a_team_event():
    assert oktime._is_relay_course("Bike & Run Binôme", []) is True


def test_runnerbreizh_binome_event_is_a_team_event():
    assert runnerbreizh._is_relay("TriBreizh en Binôme", "SEH") is True


def test_prolivesport_decides_relay_for_the_whole_heat():
    """Heat « M_relay » : 148 équipes et une ligne sans catégorie Relay, qui
    formait à elle seule un heat solo résiduel (152 à côté de 151)."""
    equipe = {"lastname": "TEAM A", "category": "Relay", "categoryRef": "R"}
    residuelle = {"lastname": "DUPONT", "firstname": "Jean", "category": "Senior", "categoryRef": "SE"}

    assert prolivesport._race_is_relay("M_relay", [equipe, residuelle]) is True
    assert prolivesport._race_is_relay("M", [equipe, equipe, residuelle]) is True
    assert prolivesport._race_is_relay("M", [equipe, residuelle, residuelle]) is False
