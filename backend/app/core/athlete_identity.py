"""Normalized athlete identity key (#907).

Two spellings of one person ("LETORT Léo" / "LETORT Leo", "LE GLOANIC" /
"LEGLOANIC", "L'APPARTIEN" / "L APPARTIEN") must share one key. The key is
computed here, in Python, and stored: PostgreSQL's `unaccent` is not
IMMUTABLE, so it can back neither an index nor a unique constraint, and a
stored value is identical on SQLite and PostgreSQL.

`alembic/versions/b7e41c9d2a58_athlete_identity_key.py` freezes a copy of this
rule; `tests/test_migrations.py` keeps the two in step.
"""
import unicodedata

# NFKD leaves these ligatures whole; `casefold` already turns `ß` into `ss`.
_LIGATURES = str.maketrans({"œ": "oe", "æ": "ae"})


def identity_key(text: str | None) -> str:
    decomposed = unicodedata.normalize("NFKD", text or "")
    folded = "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()
    return "".join(c for c in folded.translate(_LIGATURES) if c.isalnum())


def athlete_identity_keys(nom: str | None, prenom: str | None) -> tuple[str | None, str | None]:
    """`(None, None)` when the last name carries no identity (`?`, `-`): such a
    record is never matched against another one, and NULLs never collide in
    the unique constraint."""
    last_name_key = identity_key(nom)
    if not last_name_key:
        return None, None
    return last_name_key, identity_key(prenom)
