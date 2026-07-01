from datetime import date

import pytest

from app.core import season


def test_season_of_borne_31_aout_appartient_saison_precedente():
    assert season.season_of(date(2026, 8, 31)) == 2025


def test_season_of_borne_1er_septembre_ouvre_nouvelle_saison():
    assert season.season_of(date(2026, 9, 1)) == 2026


def test_season_of_janvier_appartient_saison_de_l_annee_precedente():
    assert season.season_of(date(2026, 1, 15)) == 2025


def test_season_bounds():
    assert season.season_bounds(2025) == (date(2025, 9, 1), date(2026, 8, 31))


def test_season_label():
    assert season.season_label(2025) == "Saison 2025 — 2026"


def test_current_season_utilise_horloge_figee(monkeypatch):
    from datetime import datetime

    monkeypatch.setattr(season, "utcnow", lambda: datetime(2026, 6, 27, 10, 0, 0))
    assert season.current_season() == 2025


def test_parse_seasons_nominal():
    assert season.parse_seasons("2025,2023") == [2025, 2023]


def test_parse_seasons_tolere_espaces_dedoublonne_ignore_non_entiers():
    assert season.parse_seasons(" 2025 , 2025, abc, 2023 ") == [2025, 2023]


@pytest.mark.parametrize("raw", [None, "", "   ", ","])
def test_parse_seasons_vide(raw):
    assert season.parse_seasons(raw) == []
