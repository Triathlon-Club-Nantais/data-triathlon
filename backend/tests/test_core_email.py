"""One e-mail normalisation for every list (review of #1322)."""
from app.core.email import normalize_email
from app.repositories import allowed_email_repository, member_email_repository


def test_normalize_email_strips_and_lowercases():
    assert normalize_email("  Prenom.Nom@Club.FR ") == "prenom.nom@club.fr"


def test_normalize_email_matches_sql_lower():
    """`users.email` is compared with SQL `lower()`; `casefold` would turn `ß`
    into `ss` and miss it."""
    assert normalize_email("Straße@exemple.fr") == "straße@exemple.fr"


def test_both_lists_share_the_helper():
    assert allowed_email_repository.normalize is normalize_email
    assert member_email_repository.normalize is normalize_email
