"""Catégorie d'âge FFTri, calculée depuis la date de naissance (#1291, research R1).

La saison sportive S court du 1er novembre S-1 au 31 octobre S, et l'âge s'y
compte sur l'année S-1 : en saison 2026, un enfant né en 2013 a 12 ans, Benjamin.
"""
from datetime import date

# ponytail: mois de bascule relevé indirectement (règlements 2026), non trouvé
# dans un texte FFTri ; une ligne à changer si le club donne une autre date.
SEASON_SWITCH_MONTH = 11

#: (âge minimal, libellé), du plus âgé au plus jeune.
_CATEGORIES = (
    (20, "Senior"),
    (18, "Junior"),
    (16, "Cadet"),
    (14, "Minime"),
    (12, "Benjamin"),
    (10, "Pupille"),
    (8, "Poussin"),
    (6, "Mini-poussin"),
)

UNDER_SIX = "Moins de 6 ans"


def _fftri_season(on: date) -> int:
    return on.year + 1 if on.month >= SEASON_SWITCH_MONTH else on.year


def fftri_season_bounds(on: date) -> tuple[date, date]:
    """Bornes incluses (1er novembre S-1, 31 octobre S) de la saison contenant `on`."""
    season = _fftri_season(on)
    return date(season - 1, SEASON_SWITCH_MONTH, 1), date(season, SEASON_SWITCH_MONTH - 1, 31)


def fftri_season_to_date(today: date) -> tuple[date, date]:
    """Saison en cours bornée à aujourd'hui : les séances à venir ne comptent pas encore."""
    season_start, season_end = fftri_season_bounds(today)
    return season_start, min(season_end, today)


def fftri_category(birth_date: date | None, on: date) -> str | None:
    if birth_date is None:
        return None
    season = _fftri_season(on)
    age = season - 1 - birth_date.year
    return next((label for minimum, label in _CATEGORIES if age >= minimum), UNDER_SIX)
