"""Registre des providers : la liste des noms ciblables est la source de vérité de la CLI."""
import pytest

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


# ---------------------------------------------------------------------------
# Détection par host — la règle unique (issue #49)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("url", [
    "https://timepulse.fr/resultats/3090",                 # domaine exact
    "https://www.timepulse.fr/resultats/3090",             # sous-domaine
    "https://a.b.timepulse.fr/resultats/3090",             # sous-domaine profond
    "https://www.timepulse.fr:443/resultats/3090",         # port explicite
    "https://WWW.TIMEPULSE.FR/resultats/3090",             # casse
    "https://operateur@www.timepulse.fr/resultats/3090",   # credentials
])
def test_host_match_accepte_le_domaine_et_ses_sous_domaines(url):
    assert registry._host_match(url, ("timepulse.fr",)) is True


@pytest.mark.parametrize("url", [
    # Suffixe sans point : c'est tout l'intérêt du `.` dans la règle.
    "https://evil-timepulse.fr/resultats",
    # Le jeton est un sous-domaine d'un parent hostile.
    "https://timepulse.fr.attaquant.net/resultats",
    # Sous-chaîne en query — le vecteur exact de l'issue #49.
    "https://169.254.169.254/latest/meta-data/?x=timepulse.fr",
    # Sous-chaîne en path.
    "https://evil.example/timepulse.fr/resultats",
    # Sous-chaîne en fragment.
    "https://evil.example/resultats#timepulse.fr",
    # Confusion userinfo : le host réel est l'IP, pas le jeton avant le `@`.
    "https://timepulse.fr@169.254.169.254/latest/meta-data/",
    # Entrées dégradées : pas d'exception, pas de match.
    "pas-une-url",
    "",
])
def test_host_match_rejette_les_contournements(url):
    assert registry._host_match(url, ("timepulse.fr",)) is False


def test_host_match_accepte_plusieurs_hosts():
    hosts = ("raceresult.com", "chronoconsult.fr")
    assert registry._host_match("https://my3.raceresult.com/1/results", hosts) is True
    assert registry._host_match("https://www.chronoconsult.fr/result/x/", hosts) is True
    assert registry._host_match("https://exemple-inconnu.fr/x", hosts) is False


def test_host_matched_provider_derive_matches_de_ses_hosts():
    """Un provider qui hérite n'a pas de `matches` à écrire — donc pas de
    `in url` à réintroduire par mégarde (cf. #76)."""

    class _Faux(registry.HostMatchedProvider):
        name = "chronofictif"
        _HOSTS = ("exemple.fr", "exemple.com")

    provider = _Faux()

    assert provider.matches("https://www.exemple.fr/resultats") is True
    assert provider.matches("https://exemple.com/resultats") is True
    assert provider.matches("https://evil-exemple.fr/resultats") is False


def test_host_matched_provider_sans_hosts_ne_matche_rien():
    """Défaut sûr : un provider qui oublie `_HOSTS` ne capte rien, il ne capte pas tout."""

    class _Vide(registry.HostMatchedProvider):
        name = "vide"

    assert _Vide().matches("https://exemple.fr/resultats") is False
