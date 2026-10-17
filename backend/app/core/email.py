"""Stored form of an e-mail address, shared by every list (review of #1322)."""


def normalize_email(email: str) -> str:
    """Surrounding spaces removed, lowercase.

    `lower()` and not `casefold()`: `users.email` keeps the provider's case and
    is compared with SQL `lower()` (`user_repository.find_by_email`), which
    `casefold` would not match on `ß`.
    """
    return email.strip().lower()
