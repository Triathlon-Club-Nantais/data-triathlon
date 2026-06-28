"""Helpers de saison sportive : du 1ᵉʳ septembre Y au 31 août Y+1.

Module pur (aucune dépendance DB). L'identifiant d'une saison est son année de
début Y. La saison Y couvre [Y-09-01, (Y+1)-08-31] et s'affiche « Saison Y — Y+1 ».
"""
from datetime import date

from app.core.time import utcnow


def season_of(d: date) -> int:
    """Année de début de la saison contenant `d` (bascule au 1ᵉʳ septembre)."""
    return d.year if d.month >= 9 else d.year - 1


def season_bounds(start_year: int) -> tuple[date, date]:
    """Bornes incluses (date_from, date_to) de la saison d'année de début `start_year`."""
    return date(start_year, 9, 1), date(start_year + 1, 8, 31)


def current_season() -> int:
    """Saison en cours, calculée depuis l'horloge centralisée (figeable en test)."""
    return season_of(utcnow().date())


def season_label(start_year: int) -> str:
    """Libellé d'affichage « Saison Y — Y+1 »."""
    return f"Saison {start_year} — {start_year + 1}"


def parse_seasons(raw: str | None) -> list[int]:
    """Parse un CSV d'années de début (« 2025,2023 ») → liste d'entiers.

    Tolère les espaces, ignore les valeurs non entières, dédoublonne en
    conservant l'ordre d'apparition.
    """
    if not raw:
        return []
    out: list[int] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            year = int(token)
        except ValueError:
            continue
        if year not in out:
            out.append(year)
    return out
