"""Horodatage UTC — un seul point de vérité, sans l'API dépréciée datetime.utcnow()."""
from datetime import UTC, datetime


def utcnow() -> datetime:
    """Datetime UTC naïf (cohérent avec les colonnes DateTime sans fuseau)."""
    return datetime.now(UTC).replace(tzinfo=None)
