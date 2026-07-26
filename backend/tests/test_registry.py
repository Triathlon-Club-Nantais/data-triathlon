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
    # Host IPv6 malformé : `urlparse` lève `ValueError`, pas un non-match silencieux
    # sans la garde — d'où le `try/except` dans `_host_match`.
    "https://[oops/x",
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


# ---------------------------------------------------------------------------
# Routage : ce qui doit continuer à marcher, et ce qui ne doit plus passer
# ---------------------------------------------------------------------------

#: URLs légitimes, une ou plusieurs par façade réellement supportée.
_ROUTAGE_LEGITIME = [
    ("klikego", "https://www.klikego.com/resultats/triathlon-de-vierzon-2026/1674523163798-4"),
    ("klikego", "https://klikego.com/resultats/x/1674523163798-4"),
    ("breizhchrono",
     "https://resultats.breizhchrono.com/resultats-courses/triathlon-x-129540519-19/triathlon-m"),
    ("breizhchrono",
     "https://live.breizhchrono.com/external/live5/index.jsp?reference=1488071608761-688"),
    ("wiclax", "https://chronosmetron.wiclax-results.com/Triathlon%20de%20la%20Roche%202026/"),
    ("wiclax", "https://www.chronosmetron.com/resultats/"),
    ("wiclax", "https://chronowest.fr/trail-des-2-ponts-2026/"),
    ("wiclax", "https://x.wiclax.com/G-Live/g-live.html?f=../E/e.clax"),
    ("timepulse", "https://www.timepulse.fr/epreuves/resultats/3232"),
    ("prolivesport", "https://www.prolivesport.fr/result/1082/6"),
    ("sportinnovation", "https://sportinnovation.fr/Evenements/Resultats/7031"),
    ("raceresult", "https://my3.raceresult.com/393893/results"),
    ("raceresult", "https://my.raceresult.com:443/399938/results"),
    ("raceresult", "https://www.chronoconsult.fr/result/triathlon-de-roanne-villerest/"),
    ("raceresult", "https://www.espace-competition.com/result/x/"),
    ("chronoplace", "https://www.chronoplace.fr/classement/spaycific-races-2025/epreuve/494"),
]


@pytest.mark.parametrize("provider, url", _ROUTAGE_LEGITIME)
def test_routage_des_urls_legitimes_inchange(provider, url):
    """Non-régression : le passage au host ne doit perdre aucune façade servie."""
    assert registry.detect_provider(url) == provider


#: Tous les jetons de host qu'un provider reconnaît, et le provider visé.
_JETONS_PROVIDERS = [
    "klikego.com",
    "breizhchrono.com",
    "timepulse.fr",
    "prolivesport.fr",
    "sportinnovation.fr",
    "raceresult.com",
    "espace-competition.com",
    "chronoconsult.fr",
    "chronoplace.fr",
    "wiclax.com",
    "wiclax-results.com",
    "chronosmetron.com",
    "chronowest.fr",
]

#: Les quatre familles de contournement de l'issue #49, plus la confusion userinfo.
_GABARITS_CONTOURNEMENT = [
    "https://169.254.169.254/latest/meta-data/?x={jeton}",   # sous-chaîne en query
    "https://evil.example/{jeton}/resultats",                # sous-chaîne en path
    "https://evil.example/resultats#{jeton}",                # sous-chaîne en fragment
    "https://evil-{jeton}/resultats",                        # host sosie, suffixe sans point
    "https://{jeton}.attaquant.net/resultats",               # jeton en sous-domaine hostile
    "https://{jeton}@169.254.169.254/latest/meta-data/",     # confusion userinfo
]


@pytest.mark.parametrize("jeton", _JETONS_PROVIDERS)
@pytest.mark.parametrize("gabarit", _GABARITS_CONTOURNEMENT)
def test_aucun_contournement_ne_route_vers_un_provider(gabarit, jeton):
    """SSRF #49 : une URL dont le host n'est pas servi tombe sur le fallback,
    qui lève avant toute requête réseau — quelle que soit la sous-chaîne."""
    url = gabarit.format(jeton=jeton)
    assert registry.detect_provider(url) == "playwright", url


def test_url_klikego_portant_un_jeton_timepulse_reste_klikego():
    """Hors sécurité : le point 1 fiabilise aussi la détection (note de l'issue #49).
    Aujourd'hui cette URL part chez TimePulse, qui n'en fera rien."""
    url = (
        "https://www.klikego.com/resultats/triathlon-x/1674523163798-4"
        "?retour=https%3A%2F%2Fwww.timepulse.fr%2Fresultats%2F1"
    )
    assert registry.detect_provider(url) == "klikego"


def test_wiclax_matches_reste_total_sur_un_host_ipv6_malforme():
    """`WiclaxProvider.matches` fait son propre `urlparse` pour lire le chemin
    G-Live, en plus de la composition sur `_host_match` — un host IPv6
    malformé ne doit pas faire lever `detect_provider` (résidu du finding
    Important n°2 de la revue #49 : `GET /scrape/detect` n'a aucune garde en
    amont, contrairement aux chemins d'import)."""
    assert registry.detect_provider("https://[oops/x") == "playwright"


def test_wiclax_ne_capte_pas_le_site_vitrine_sans_chemin_g_live():
    """`wiclax.com` est le site de l'éditeur : seuls les chemins G-Live sont
    des pages de résultats. La condition de chemin doit survivre à la bascule."""
    assert registry.detect_provider("https://www.wiclax.com/tarifs") == "playwright"


@pytest.mark.parametrize("url", [
    "https://evil-wiclax.com/G-Live/g-live.html?f=../E/e.clax",
    "https://wiclax.com.attaquant.net/G-Live/g-live.html",
])
def test_wiclax_sosie_avec_chemin_g_live_non_capte(url):
    """Le seul contournement Wiclax réellement ouvert : `endswith("wiclax.com")`
    sans point suit `evil-wiclax.com`, et le chemin G-Live lève la seconde
    condition. Les gabarits génériques ne l'atteignent pas — leur path n'a pas
    de `G-Live` —, d'où ce cas dédié."""
    assert registry.detect_provider(url) == "playwright"


# ---------------------------------------------------------------------------
# Verrou : le fallback refuse AVANT le réseau (tient lieu du point 3 de #49)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("url", [
    "https://169.254.169.254/latest/meta-data/?x=timepulse.fr",
    "https://127.0.0.1:8001/api/v1/admin?x=prolivesport.fr",
    "https://evil.example/breizhchrono.com/resultats",
])
def test_host_non_reconnu_ne_declenche_aucune_requete(monkeypatch, url):
    """Le fallback Playwright lève avant tout réseau : c'est ce qui rend une
    whitelist explicite superflue. Si quelqu'un rebranche un scraper générique
    sur le fallback, ce test tombe."""
    import httpx

    def _interdit(*args, **kwargs):
        raise AssertionError(f"requête réseau émise pour un host non reconnu : {url}")

    monkeypatch.setattr(httpx.Client, "request", _interdit)
    monkeypatch.setattr(httpx.Client, "send", _interdit)

    with pytest.raises(ValueError, match="playwright"):
        registry.scrape_event_all(url)
