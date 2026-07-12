"""Registre des providers : la liste des noms ciblables est la source de vérité de la CLI."""
from app.scrapers import registry


def test_provider_names_derive_de_la_liste_des_providers(monkeypatch):
    """Aucune liste en dur : un provider ajouté à `PROVIDERS` apparaît aussitôt."""

    class _Faux:
        name = "chronofictif"

        def matches(self, url: str) -> bool:
            return False

        def scrape_event_all(self, url: str):  # pragma: no cover - jamais appelé
            return []

    monkeypatch.setattr(registry, "PROVIDERS", [*registry.PROVIDERS, _Faux()])

    assert "chronofictif" in registry.provider_names()


def test_provider_names_couvre_les_providers_reels():
    noms = registry.provider_names()

    assert {"klikego", "breizhchrono", "timepulse", "wiclax"} <= set(noms)


def test_provider_names_exclut_le_fallback_playwright():
    """`playwright` est le fallback des URLs non reconnues, pas une valeur ciblable."""
    assert "playwright" not in registry.provider_names()
