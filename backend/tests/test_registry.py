"""Registre des providers : la liste des noms ciblables est la source de vérité de la CLI."""
import pytest

from app.scrapers import registry
from app.scrapers.base import FanoutTrace


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


def test_provider_names_ne_porte_aucun_nom_fantome():
    """La liste dérive de `PROVIDERS` : elle ne contient que des providers réels.

    `playwright` y figurait tant qu'une sentinelle attrape-tout existait — un
    slug ciblable en CLI qui ne désignait aucun scraper.
    """
    noms = registry.provider_names()

    assert "playwright" not in noms
    assert all(noms), "un provider sans nom n'est pas ciblable en CLI"
    assert len(noms) == len(set(noms)), "deux providers portent le même nom"


def test_is_supported_vrai_des_quun_provider_reconnait_lurl():
    assert registry.is_supported("https://www.ironman.com/races/im703-vichy/results") is True
    assert registry.is_supported("https://www.klikego.com/resultats/event/1") is True


def test_is_supported_faux_si_personne_ne_reconnait_lurl():
    """Aucun provider ne matche → non supportée, et `detect_provider` rend `""`."""
    assert registry.is_supported("https://chronopuce.test/x") is False


def test_is_supported_derive_de_la_liste_des_providers(monkeypatch):
    """Un provider ajouté à `PROVIDERS` est supporté sans toucher à `is_supported`."""

    class _Faux:
        name = "chronofictif"

        def matches(self, url: str) -> bool:
            return "chronofictif.test" in url

        def scrape_event_all(self, url: str):  # pragma: no cover - jamais appelé
            return []

    monkeypatch.setattr(registry, "PROVIDERS", [*registry.PROVIDERS, _Faux()])

    assert registry.is_supported("https://chronofictif.test/e/1") is True


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
    ("competitor", "https://www.ironman.com/races/im-france/results"),
    ("competitor", "https://labs-v2.competitor.com/results/event/x"),
    ("runnerbreizh",
     "https://www.runnerbreizh.fr/requetetriathlons.php?CourseFichierGpsNom=2025-09-0749quiberon"),
    # Apex sans `www` : la forme qu'un contributeur peut coller à la main.
    ("runnerbreizh", "https://runnerbreizh.fr/requetetriathlons.php?CourseFichierGpsNom=x"),
    # Fiche coureur : même host, donc bien routée ici — c'est le scraper qui la
    # refuse ensuite, avec un message nommant la forme attendue.
    ("runnerbreizh", "https://www.runnerbreizh.fr/triathlons.php?CoureurNom=X&CoureurPrenom=Y"),
    # Sporthive (#53) : la forme du Sheet (sous-domaine `results`), la cible de
    # la redirection 307 (apex + segment `s/`), et le préfixe de langue.
    ("sporthive", "https://results.sporthive.com/events/7237011278055708416/races/1/bib/426"),
    ("sporthive", "https://sporthive.com/events/s/7237011278055708416/races/1"),
    ("sporthive", "https://results.sporthive.com/en/events/7237011278055708416/races/1"),
    ("chronoweb", "https://chronoweb.com/resultats_evenement.php?event=323&epreuve=1147"),
    ("chronoweb", "https://www.chronoweb.com/resultats_evenement.php?event=323"),
    # Fiche individuelle : même host, tronquée vers son événement par le scraper.
    ("chronoweb", "https://chronoweb.com/resultats_participant.php?event=347&epreuve=1234&bib=599"),
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
    "fftri.t2area.com",
    "ironman.com",
    "competitor.com",
    "runnerbreizh.fr",
    "sporthive.com",
    "chronoweb.com",
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
    """SSRF #49 : une URL dont le host n'est pas servi n'est reconnue par aucun
    provider, et le dispatcher lève avant toute requête réseau — quelle que soit
    la sous-chaîne."""
    url = gabarit.format(jeton=jeton)
    assert registry.detect_provider(url) == "", url


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
    assert registry.detect_provider("https://[oops/x") == ""


def test_wiclax_ne_capte_pas_le_site_vitrine_sans_chemin_g_live():
    """`wiclax.com` est le site de l'éditeur : seuls les chemins G-Live sont
    des pages de résultats. La condition de chemin doit survivre à la bascule."""
    assert registry.detect_provider("https://www.wiclax.com/tarifs") == ""


@pytest.mark.parametrize("url", [
    "https://evil-wiclax.com/G-Live/g-live.html?f=../E/e.clax",
    "https://wiclax.com.attaquant.net/G-Live/g-live.html",
])
def test_wiclax_sosie_avec_chemin_g_live_non_capte(url):
    """Le seul contournement Wiclax réellement ouvert : `endswith("wiclax.com")`
    sans point suit `evil-wiclax.com`, et le chemin G-Live lève la seconde
    condition. Les gabarits génériques ne l'atteignent pas — leur path n'a pas
    de `G-Live` —, d'où ce cas dédié."""
    assert registry.detect_provider(url) == ""


def test_t2area_matches_reste_total_sur_un_host_ipv6_malforme():
    """`T2AreaProvider` garde sa propre règle (égalité stricte, pas la règle
    « host ou vrai sous-domaine »), donc son propre accès au host : elle doit
    être aussi totale que `_host_match`.

    Ce n'est pas un doublon de la garde Wiclax : dernier provider avant le
    fallback, T2Area est traversé par **toute** URL non reconnue. Une garde
    posée en amont seulement se fait contourner par ce maillon-là."""
    assert registry.T2AreaProvider().matches("https://[oops/x") is False


def test_t2area_n_accepte_que_le_host_fftri_exact():
    """Verrou de l'égalité stricte : router T2Area via `_host_match`
    l'élargirait aux sous-domaines de `fftri.t2area.com`, alors que
    l'allowlist ne vise que le host FFTRI lui-même (périmètre de #51)."""
    provider = registry.T2AreaProvider()

    assert provider.matches("https://fftri.t2area.com/calendrier/x/y/2025.html") is True
    assert provider.matches("https://x.fftri.t2area.com/calendrier/x/y/2025.html") is False


# ---------------------------------------------------------------------------
# Verrou : le fallback refuse AVANT le réseau (tient lieu du point 3 de #49)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("url", [
    "https://169.254.169.254/latest/meta-data/?x=timepulse.fr",
    "https://127.0.0.1:8001/api/v1/admin?x=prolivesport.fr",
    "https://evil.example/breizhchrono.com/resultats",
])
def test_host_non_reconnu_ne_declenche_aucune_requete(monkeypatch, url):
    """Le dispatcher lève avant tout réseau sur une URL que personne ne reconnaît :
    c'est ce qui rend une whitelist explicite superflue. Si quelqu'un rebranche un
    scraper générique en attrape-tout, ce test tombe."""
    import httpx

    def _interdit(*args, **kwargs):
        raise AssertionError(f"requête réseau émise pour un host non reconnu : {url}")

    monkeypatch.setattr(httpx.Client, "request", _interdit)
    monkeypatch.setattr(httpx.Client, "send", _interdit)

    with pytest.raises(ValueError, match="Aucun provider"):
        registry.scrape_event_all(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://classement.ok-time.fr/48555",
        "https://classement.ok-time.fr/48555/race/59697",
        "https://ok-time.fr/evenement/triathlon-de-lacanau-2026/",
        "https://www.ok-time.fr/evenement/triathlon-de-lacanau-2026/",
        "https://classement.ok-time.fr:443/48555",
    ],
)
def test_detect_provider_oktime(url):
    """Domaine exact, vrais sous-domaines, port explicite."""
    assert registry.detect_provider(url) == "oktime"


def test_detect_provider_rejette_un_host_sosie():
    """`hostname` et non `netloc`, et suffixe précédé d'un point : sans cette
    garde, `evilok-time.fr` matcherait (cf. la garde RaceResultProvider)."""
    assert registry.detect_provider("https://evilok-time.fr/48555") != "oktime"


def test_provider_names_contient_oktime():
    assert "oktime" in registry.provider_names()


# ---------------------------------------------------------------------------
# Sporthive (#53) — un host, et surtout pas celui de l'API
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("url", [
    "https://sporthive.com/events/s/7237011278055708416",
    "https://results.sporthive.com/events/7237011278055708416",
    "https://results.sporthive.com:443/events/7237011278055708416",
    "https://timepulse.fr@results.sporthive.com/events/1",
])
def test_detect_provider_sporthive(url):
    """Hôte exact, vrai sous-domaine, port explicite, et host réel derrière des
    credentials : l'entrée unique `sporthive.com` suffit (D2)."""
    assert registry.detect_provider(url) == "sporthive"


def test_detect_provider_ne_capte_pas_lhote_dapi_speedhive():
    """`eventresults-api.speedhive.com` est l'hôte que le scraper **appelle**,
    pas un hôte de résultats : une URL Speedhive collée par un utilisateur n'est
    pas une page Sporthive et ne doit pas router ici (note de D2)."""
    url = "https://eventresults-api.speedhive.com/sporthive/events/1"

    assert registry.detect_provider(url) == ""


def test_detect_provider_sporthive_rejette_un_host_sosie():
    """Non-régression SSRF #49 : le point avant le suffixe compte."""
    assert registry.detect_provider("https://evil-sporthive.com/events/1") != "sporthive"


def test_provider_names_contient_sporthive():
    assert "sporthive" in registry.provider_names()


# ---------------------------------------------------------------------------
# ChronoWeb (#55)
# ---------------------------------------------------------------------------


def test_chronoweb_est_supporte():
    """`is_supported` est la **seule** définition de « supporté » : le front la lit,
    il ne tient aucune liste de son côté."""
    assert registry.is_supported("https://chronoweb.com/resultats_evenement.php?event=323")
    assert "chronoweb" in registry.provider_names()


def test_chronoweb_capte_le_host_reel_derriere_un_userinfo():
    """Contre-épreuve des gabarits de contournement : ici le host **est**
    `chronoweb.com`, le jeton avant le `@` n'étant que du userinfo. `_url_host`
    lit `hostname` et non `netloc`, donc l'URL est légitimement routée chez
    chronoweb — à ne pas confondre avec `chronoweb.com@169.254.169.254`, que le
    gabarit générique vérifie et qui, lui, n'est reconnu par personne."""
    assert registry.detect_provider("https://timepulse.fr@chronoweb.com/x") == "chronoweb"


def test_chronoweb_rejette_un_host_sosie():
    assert registry.detect_provider("https://evil-chronoweb.com/resultats") == ""


# ---------------------------------------------------------------------------
# get_provider — accès à l'instance provider (issue #156)
# ---------------------------------------------------------------------------

def test_get_provider_returns_instance_for_klikego():
    from app.scrapers.registry import KlikegoProvider, get_provider
    provider = get_provider("https://www.klikego.com/resultats/mesquer/1677015306084-12")
    assert isinstance(provider, KlikegoProvider)


def test_get_provider_returns_instance_for_breizhchrono():
    from app.scrapers.registry import BreizhChronoProvider, get_provider
    provider = get_provider("https://resultats.breizhchrono.com/resultats-courses/foo-1234")
    assert isinstance(provider, BreizhChronoProvider)


def test_get_provider_returns_instance_for_breizhchrono_live():
    """live.breizhchrono.com est la même façade Klikego mais géré par BreizhChronoProvider."""
    from app.scrapers.registry import BreizhChronoProvider, get_provider
    url = "https://live.breizhchrono.com/external/live5/index.jsp?reference=1488071608761-688"
    provider = get_provider(url)
    assert isinstance(provider, BreizhChronoProvider)


def test_get_provider_returns_none_for_unknown_url():
    from app.scrapers.registry import get_provider
    assert get_provider("https://github.com/foo/bar") is None


def test_get_provider_returns_none_for_malformed_url():
    """Une URL avec un host IPv6 non fermé ne doit pas lever."""
    from app.scrapers.registry import get_provider
    # Ne doit pas lever — retourne None si aucun provider ne matche
    result = get_provider("https://[oops/x")
    assert result is None


# ---------------------------------------------------------------------------
# KlikegoProvider fan-out (issue #156)
# ---------------------------------------------------------------------------


def _patch_klikego_fanout(monkeypatch, results_by_heat: dict[str, list], failures: list[str] | None = None):
    """Monkeypatch klikego.scrape_event_fanout pour retourner un couple prédéfini."""
    from app.scrapers import klikego

    failures = failures or []

    def fake_fanout(event_id, event_name, slug, *, cache_probe=None, on_heat_start=None):
        all_results = []
        trace = FanoutTrace()
        trace.heats_enumerated = len(results_by_heat) + len(failures)
        for heat_slug, rs in results_by_heat.items():
            heat_url = klikego._heat_source_url(event_id, slug, heat_slug)
            if cache_probe is not None and cache_probe(heat_url):
                trace.heats_cached += 1
                continue
            all_results.extend(rs)
        for slug_failed in failures:
            trace.failures.append({"heat_slug": slug_failed, "reason": "boom"})
        return all_results, trace

    monkeypatch.setattr(klikego, "scrape_event_fanout", fake_fanout)


def test_klikego_provider_ignores_query_heat(monkeypatch):
    """Une URL portant ?heat=triathlon-s-indiv n'est PAS traitée en single-heat :
    le fan-out énumère et scrape tous les heats de l'événement (arbitrage A1)."""
    from app.scrapers.base import ScrapedResult
    from app.scrapers.registry import KlikegoProvider

    # 8 heats mockés, 1 ScrapedResult chacun
    results_by_heat = {
        f"heat-{i}": [ScrapedResult(source_url=f"u{i}", provider="klikego")]
        for i in range(8)
    }
    _patch_klikego_fanout(monkeypatch, results_by_heat)

    provider = KlikegoProvider()
    url_with_heat = "https://www.klikego.com/resultats/mesquer/1677015306084-12?heat=triathlon-s-indiv"
    results = provider.scrape_event_all(url_with_heat)

    assert len(results) == 8, "?heat=… doit être ignoré (fan-out complet)"
    assert provider.last_trace is not None
    assert provider.last_trace.heats_enumerated == 8


def test_klikego_provider_stores_last_trace(monkeypatch):
    """last_trace remonte l'état complet après un appel — enumerated + failures."""
    from app.scrapers.base import ScrapedResult
    from app.scrapers.registry import KlikegoProvider

    results_by_heat = {
        f"heat-{i}": [ScrapedResult(source_url=f"u{i}", provider="klikego")]
        for i in range(7)
    }
    _patch_klikego_fanout(monkeypatch, results_by_heat, failures=["heat-broken"])

    provider = KlikegoProvider()
    provider.scrape_event_all("https://www.klikego.com/resultats/foo/1234-5")

    assert provider.last_trace is not None
    assert provider.last_trace.heats_enumerated == 8  # 7 ok + 1 en échec
    assert len(provider.last_trace.failures) == 1
    assert provider.last_trace.failures[0]["heat_slug"] == "heat-broken"


def test_klikego_provider_last_trace_resets_between_calls(monkeypatch):
    """Deux appels successifs → trace du deuxième, pas cumul."""
    from app.scrapers.base import ScrapedResult
    from app.scrapers.registry import KlikegoProvider

    provider = KlikegoProvider()

    _patch_klikego_fanout(
        monkeypatch,
        {"heat-a": [ScrapedResult(source_url="ua", provider="klikego")]},
        failures=["heat-broken"],
    )
    provider.scrape_event_all("https://www.klikego.com/resultats/foo/1")
    assert provider.last_trace.heats_enumerated == 2
    assert len(provider.last_trace.failures) == 1

    _patch_klikego_fanout(
        monkeypatch,
        {"heat-b": [ScrapedResult(source_url="ub", provider="klikego")]},
    )
    provider.scrape_event_all("https://www.klikego.com/resultats/foo/2")
    assert provider.last_trace.heats_enumerated == 1
    assert provider.last_trace.failures == []


def test_klikego_provider_forwards_cache_probe(monkeypatch):
    """Le provider passe cache_probe à klikego.scrape_event_fanout, qui l'exploite."""
    from app.scrapers.base import ScrapedResult
    from app.scrapers.registry import KlikegoProvider

    _patch_klikego_fanout(monkeypatch, {
        "heat-a": [ScrapedResult(source_url="ua", provider="klikego")],
        "heat-b": [ScrapedResult(source_url="ub", provider="klikego")],
    })

    provider = KlikegoProvider()
    def probe(url: str) -> bool:  # heat-a cachée
        return "heat-a" in url
    results = provider.scrape_event_all(
        "https://www.klikego.com/resultats/foo/1",
        cache_probe=probe,
    )
    assert len(results) == 1  # seul heat-b scrapé
    assert provider.last_trace.heats_cached == 1
    assert provider.last_trace.heats_enumerated == 2
