from types import SimpleNamespace

import pytest

from app.core.splits_reliability import (
    UNRELIABLE_SPLIT_PROVIDERS,
    has_reliable_splits,
    is_stats_eligible,
)


@pytest.mark.parametrize(
    "provider",
    ["raceresult", "klikego", "oktime", "sporthive", "chronoweb", "wiclax", "timepulse"],
)
def test_unlisted_providers_are_eligible(provider):
    """Liste d'exclusion : un fournisseur inconnu est éligible par défaut."""
    assert has_reliable_splits(provider) is True


@pytest.mark.parametrize("provider", [None, "", "manuel", "t2area", "breizhchrono"])
def test_manual_and_partial_providers_are_rejected(provider):
    assert has_reliable_splits(provider) is False


@pytest.mark.parametrize("provider", ["T2Area", " breizhchrono ", "MANUEL"])
def test_provider_is_compared_on_a_normalized_form(provider):
    assert has_reliable_splits(provider) is False


def test_is_stats_eligible_delegates_to_course_provider():
    assert is_stats_eligible(SimpleNamespace(provider="raceresult")) is True
    assert is_stats_eligible(SimpleNamespace(provider="t2area")) is False


def test_exclusion_list_is_already_normalized():
    """Elle est comparée à des formes normalisées : elle doit l'être."""
    for provider in UNRELIABLE_SPLIT_PROVIDERS:
        assert provider == provider.strip().lower()
