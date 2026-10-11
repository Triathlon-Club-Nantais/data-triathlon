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


def fftri_category(birth_date: date | None, on: date) -> str | None:
    if birth_date is None:
        return None
    season = on.year + 1 if on.month >= SEASON_SWITCH_MONTH else on.year
    age = season - 1 - birth_date.year
    return next((label for minimum, label in _CATEGORIES if age >= minimum), UNDER_SIX)
