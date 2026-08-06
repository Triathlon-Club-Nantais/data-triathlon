"""
Registre des providers de chronométrage.

Chaque provider est une instance implémentant `ScraperProtocol`. La détection se
fait en parcourant la liste `PROVIDERS` (plus de chaîne de `if/else`). Ajouter un
provider = créer son adapter et l'ajouter à la liste, à un seul endroit.

Provider inconnu → `PlaywrightProvider`, sentinelle de refus et non un scraper
(voir sa docstring : le fallback navigateur a été supprimé avec sa dépendance).

La détection se fait sur le **host** de l'URL, jamais sur une sous-chaîne de
l'URL entière : un jeton en query suffisait à router n'importe quelle URL vers
un scraper, qui la requêtait telle quelle (SSRF, issue #49). La règle est dans
`_host_match`, appliquée par défaut via `HostMatchedProvider`.

NOTE — La factorisation des helpers internes communs (`_detect_event_type`,
mapping des splits) entre klikego/wiclax/timepulse reste un refacto à part : ces
fonctions ont des signatures divergentes et wiclax n'a pas de tests, donc on évite
de les fusionner ici au risque d'une régression silencieuse. Voir le design.
"""
import logging
from collections.abc import Callable
from typing import Protocol, runtime_checkable
from urllib.parse import parse_qs, urlparse

from app.scrapers import (
    breizhchrono,
    chronoplace,
    chronoweb,
    competitor,
    klikego,
    oktime,
    prolivesport,
    raceresult,
    runnerbreizh,
    sporthive,
    sportinnovation,
    t2area,
    timepulse,
    wiclax,
)
from app.scrapers.base import ScrapedResult

logger = logging.getLogger(__name__)


def _url_host(url: str) -> str:
    """Host de `url` en minuscules, chaîne vide si `urlparse` échoue.

    `hostname` et non `netloc` : sans lui, un port explicite
    (`my.raceresult.com:443`) ou des credentials feraient rater le match — et
    `hostname` est déjà en minuscules, il isole aussi le host réel d'une URL
    du type `https://timepulse.fr@169.254.169.254/`.

    Extraction seule — aucune règle de comparaison ici, elle reste dans
    `_host_match`. `urlparse` lève `ValueError` sur un host IPv6 malformé (ex.
    `https://[oops/x`) : **tout** accès au host passe par ce helper, y compris
    celui d'un provider dont la règle ne se réduit pas à `_host_match`
    (`T2AreaProvider`, égalité stricte). Une garde posée provider par provider
    laisse le maillon suivant lever, et `detect_provider` les parcourt tous.
    """
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def _host_match(url: str, hosts: tuple[str, ...]) -> bool:
    """Vrai si le host de `url` est l'un de `hosts`, ou un vrai sous-domaine.

    Le point compte : `endswith("timepulse.fr")` nu suivrait aussi
    `evil-timepulse.fr`. Ne **jamais** revenir à un test de sous-chaîne sur
    l'URL entière — c'était le SSRF de l'issue #49, le jeton suffisait en query.

    Une entrée dégradée reste un non-match, jamais une exception : c'est
    `_url_host` qui le garantit.
    """
    host = _url_host(url)
    return any(host == h or host.endswith(f".{h}") for h in hosts)


def _url_path(url: str) -> str:
    """Path de `url`, chaîne vide si `urlparse` échoue.

    Pendant de `_url_host` : un provider qui a besoin du path en plus du host
    (`WiclaxProvider`) passe par ce helper plutôt que par un `urlparse` direct,
    pour rester total lui aussi.
    """
    try:
        return urlparse(url).path or ""
    except ValueError:
        return ""


@runtime_checkable
class ScraperProtocol(Protocol):
    """Contrat que tout provider doit respecter."""

    name: str

    def matches(self, url: str) -> bool:
        """Vrai si ce provider sait traiter l'URL."""

    def scrape_event_all(self, url: str) -> list[ScrapedResult]:
        """Scrape tous les participants de l'épreuve (peut lever ValueError si non supporté)."""


class HostMatchedProvider:
    """Détection par host, comportement par défaut de tout provider.

    Un provider n'a plus qu'à déclarer `_HOSTS` : il n'y a pas de `matches` à
    écrire, donc pas de `in url` à réintroduire au prochain fournisseur ajouté.
    Un provider dont la condition ne se réduit pas à une liste de hosts
    (cf. `WiclaxProvider`) surcharge `matches` et compose sur `_host_match` —
    jamais sur une copie de la règle.
    """

    #: Hosts servis par ce provider. Allowlist explicite : détecter le moteur
    #: par le contenu obligerait à télécharger la page de toute URL inconnue
    #: avant de savoir la traiter.
    _HOSTS: tuple[str, ...] = ()

    def matches(self, url: str) -> bool:
        return _host_match(url, self._HOSTS)


class KlikegoProvider(HostMatchedProvider):
    """Klikego — URL d'événement = tous les heats (fan-out, issue #156).

    Le paramètre `?heat=X` **éventuellement présent** dans l'URL est **ignoré**
    sur le chemin nominal. L'échappatoire pour cibler un heat unique est
    l'option CLI `rescrape-db --single-heat` (chemin `single_heat=True`).

    Le fan-out expose sa progression dans `self.last_trace` (compteurs
    `heats_enumerated`, `heats_cached`, `heats_imported`, `failures`) — lue par
    `import_service` pour peupler le SSE `done`.
    """
    name = "klikego"
    _HOSTS = ("klikego.com",)

    def __init__(self) -> None:
        self.last_trace: klikego.FanoutTrace | None = None

    def _parse_url(self, url: str) -> tuple[str, str, str, str]:
        """(event_id, heat_query, slug, event_name) — `heat_query` = ?heat= éventuel."""
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        path_parts = [p for p in parsed.path.strip("/").split("/") if p]
        event_id = path_parts[-1] if path_parts else ""
        heat = params.get("heat", [""])[0]
        slug = path_parts[-2] if len(path_parts) >= 2 else ""
        event_name = slug.replace("-", " ").title() if slug else ""
        return event_id, heat, slug, event_name

    def scrape_event_all(
        self, url: str,
        *,
        cache_probe: Callable[[str], bool] | None = None,
        on_heat_start: Callable[[str, str, int, int], None] | None = None,
        single_heat: bool = False,
    ) -> list[ScrapedResult]:
        """Fan-out par défaut ; `single_heat=True` cible le `?heat=X` de l'URL."""
        event_id, heat_query, slug, event_name = self._parse_url(url)

        if single_heat:
            # Chemin échappatoire (--single-heat) : nécessite ?heat=X dans l'URL.
            # La validation CLI (validators) doit refuser une URL nue avant d'arriver ici.
            self.last_trace = klikego.FanoutTrace(heats_enumerated=1)
            try:
                return klikego.scrape_event_all(event_id, heat_query, event_name, slug)
            except Exception as exc:
                self.last_trace.failures.append(
                    {"heat_slug": heat_query, "reason": str(exc)}
                )
                raise

        # Chemin nominal (fan-out) : ?heat=X ignoré, on énumère tous les heats.
        results, trace = klikego.scrape_event_fanout(
            event_id, event_name, slug,
            cache_probe=cache_probe, on_heat_start=on_heat_start,
        )
        self.last_trace = trace
        return results


class BreizhChronoProvider(HostMatchedProvider):
    name = "breizhchrono"
    _HOSTS = ("breizhchrono.com",)

    def scrape_event_all(self, url: str) -> list[ScrapedResult]:
        from app.scrapers.breizhchrono import (
            _parse_bc_url,
            _parse_live_url,
            scrape_live_event_all,
        )

        # live.breizhchrono.com = même plateforme Klikego (cf. #34), façade
        # différente : on route vers le moteur live plutôt que de rejeter.
        # netloc en minuscules → robuste à une URL copiée/collée avec majuscules.
        if "live.breizhchrono.com" in urlparse(url).netloc.lower():
            reference, heat = _parse_live_url(url)
            if not reference:
                raise ValueError(
                    "URL live.breizhchrono.com sans paramètre 'reference' exploitable."
                )
            return scrape_live_event_all(reference, heat)
        event_id, heat, slug = _parse_bc_url(url)
        event_name = slug.replace("-", " ").title() if slug else ""
        return breizhchrono.scrape_event_all(event_id, heat, event_name, slug)


class WiclaxProvider(HostMatchedProvider):
    name = "wiclax"

    # Hosts servant un moteur G-Live. `chronowest.fr` : WordPress + iframe
    # G-Live (issue #35).
    _HOSTS = ("wiclax-results.com", "chronosmetron.com", "chronowest.fr")

    def matches(self, url: str) -> bool:
        # `wiclax.com` est le site vitrine de l'éditeur : il n'est pas dans
        # `_HOSTS`, seuls ses chemins G-Live sont des pages de résultats. D'où
        # la composition sur `_host_match` — surtout pas une copie de la règle.
        # `_url_path` (et non un `urlparse` direct) : un host IPv6 malformé ne
        # doit pas faire lever `matches`, seulement produire un non-match.
        return super().matches(url) or (
            _host_match(url, ("wiclax.com",)) and "G-Live" in _url_path(url)
        )

    def scrape_event_all(self, url: str) -> list[ScrapedResult]:
        return wiclax.scrape_event_all(url)


class TimePulseProvider(HostMatchedProvider):
    name = "timepulse"
    _HOSTS = ("timepulse.fr",)

    def scrape_event_all(self, url: str) -> list[ScrapedResult]:
        return timepulse.scrape_event_all(url)


class ProLiveSportProvider(HostMatchedProvider):
    name = "prolivesport"
    _HOSTS = ("prolivesport.fr",)

    def scrape_event_all(self, url: str) -> list[ScrapedResult]:
        return prolivesport.scrape_event_all(url)


class SportInnovationProvider(HostMatchedProvider):
    name = "sportinnovation"
    _HOSTS = ("sportinnovation.fr",)

    def scrape_event_all(self, url: str) -> list[ScrapedResult]:
        return sportinnovation.scrape_event_all(url)


class RaceResultProvider(HostMatchedProvider):
    """RaceResult — URL d'événement = tous les contests (fan-out, issue #217).

    Sous-unité = **contest** de `config["contests"]`. Le fan-out expose sa
    progression dans `self.last_trace` (compteurs `heats_enumerated`,
    `heats_cached`, `heats_imported`, `failures`, `cached_urls`) — lue par
    `import_service` pour peupler le SSE `done`.

    `Contest="0"` (« toutes catégories ») est réservé et exclu du fan-out :
    ses listes sont scrapées comme dans le contrat historique. L'échappatoire
    `--single-heat` (chemin `single_heat=True`) court-circuite le fan-out et
    n'appelle **aucun** `cache_probe`.
    """

    name = "raceresult"

    # Trois façades d'un même produit RaceResult (issue #50), toutes servies
    # par la même API JSON publique.
    _HOSTS = ("raceresult.com", "espace-competition.com", "chronoconsult.fr")

    def __init__(self) -> None:
        self.last_trace: raceresult.FanoutTrace | None = None

    def scrape_event_all(
        self, url: str,
        *,
        cache_probe: Callable[[str], bool] | None = None,
        on_heat_start: Callable[[str, str, int, int], None] | None = None,
        single_heat: bool = False,
    ) -> list[ScrapedResult]:
        """Fan-out par contest ; `single_heat=True` cible l'URL sans fan-out."""
        if single_heat:
            # Chemin échappatoire (--single-heat) : aucun fan-out, pas de trace.
            # Utile aux tests et à un rescrape d'événement en pot commun.
            self.last_trace = raceresult.FanoutTrace(heats_enumerated=1)
            try:
                return raceresult.scrape_event_all(url)
            except Exception as exc:
                self.last_trace.failures.append(
                    {"heat_slug": url, "reason": str(exc)}
                )
                raise

        results, trace = raceresult.scrape_event_fanout(
            url, cache_probe=cache_probe, on_heat_start=on_heat_start,
        )
        self.last_trace = trace
        return results


class ChronoplaceProvider(HostMatchedProvider):
    """Chronoplace — fan-out par épreuve (cache TTL par sous-unité, épique #195).

    Une URL pointe une épreuve, mais la page liste ses sœurs (onglets) : chaque
    onglet est une sous-unité, avec sa propre `source_url` canonique. Le
    fan-out expose sa progression dans `self.last_trace`.
    """
    name = "chronoplace"
    _HOSTS = ("chronoplace.fr",)

    def __init__(self) -> None:
        self.last_trace: chronoplace.FanoutTrace | None = None

    def scrape_event_all(
        self, url: str,
        *,
        cache_probe: Callable[[str], bool] | None = None,
        on_heat_start: Callable[[str, str, int, int], None] | None = None,
    ) -> list[ScrapedResult]:
        results, trace = chronoplace.scrape_event_fanout(
            url, cache_probe=cache_probe, on_heat_start=on_heat_start,
        )
        self.last_trace = trace
        return results


class OkTimeProvider(HostMatchedProvider):
    name = "oktime"

    # `ok-time.fr` et ses sous-domaines : `classement.ok-time.fr` (la SPA de
    # classement) et l'apex (le site éditorial, qui sert l'API JSON). Allowlist
    # explicite, comme Wiclax et RaceResult. `_HOSTS` seul : `_host_match`
    # compare sur `hostname` — un port explicite ou des credentials ne font pas
    # rater le match — et exige un point avant le suffixe, sans quoi un host
    # sosie du type `evilok-time.fr` suivrait.
    _HOSTS = ("ok-time.fr",)

    def scrape_event_all(self, url: str) -> list[ScrapedResult]:
        return oktime.scrape_event_all(url)


class CompetitorProvider(HostMatchedProvider):
    name = "competitor"

    # `ironman.com` n'est qu'une vitrine : le moteur est Competitor/WTC, d'où le
    # nom du provider (issue #54). `competitor.com` couvre par sous-domaine la
    # façade réelle `labs-v2.competitor.com`, et les suivantes s'il y en a.
    _HOSTS = ("ironman.com", "competitor.com")

    def scrape_event_all(self, url: str) -> list[ScrapedResult]:
        return competitor.scrape_event_all(url)


class RunnerBreizhProvider(HostMatchedProvider):
    name = "runnerbreizh"
    _HOSTS = ("runnerbreizh.fr",)

    def scrape_event_all(self, url: str) -> list[ScrapedResult]:
        return runnerbreizh.scrape_event_all(url)


class SporthiveProvider(HostMatchedProvider):
    """Sporthive — URL d'événement = toutes les races (fan-out, issue #216).

    Une race est identifiée par son `race.id` snowflake (pas l'ordinal du path,
    trap n°1 du sondage). Le fan-out expose sa progression dans
    `self.last_trace` (compteurs `heats_enumerated`, `heats_cached`,
    `heats_imported`, `failures`) — lue par `import_service` pour peupler le
    SSE `done`. `single_heat=True` n'a pas d'échappatoire par-race documentée
    ici : Sporthive n'a pas de `?heat=` dans l'URL, on retombe sur le contrat
    historique event-scoped de `scrape_event_all`.
    """
    name = "sporthive"

    # `sporthive.com` seul (issue #53) : `_host_match` accepte l'hôte exact
    # **et** tout vrai sous-domaine, donc cette entrée couvre à la fois
    # `results.sporthive.com` (la forme du Sheet) et l'apex, cible de la
    # redirection 307 — donc la forme qu'un membre copie depuis son navigateur.
    # L'hôte de l'API, `eventresults-api.speedhive.com`, n'est délibérément
    # **pas** listé : c'est celui que le scraper appelle, pas une page de
    # résultats à reconnaître.
    _HOSTS = ("sporthive.com",)

    def __init__(self) -> None:
        self.last_trace: klikego.FanoutTrace | None = None

    def scrape_event_all(
        self, url: str,
        *,
        cache_probe: Callable[[str], bool] | None = None,
        on_heat_start: Callable[[str, str, int, int], None] | None = None,
        single_heat: bool = False,
    ) -> list[ScrapedResult]:
        """Fan-out par défaut ; `single_heat=True` retombe sur le chemin event-scoped.

        Sporthive n'a pas de sous-unité identifiée dans l'URL (pas de `?heat=`
        comme Klikego), donc l'échappatoire `--single-heat` retombe sur
        `scrape_event_all` du module — l'événement entier, sans cache par-race.
        """
        if single_heat:
            self.last_trace = klikego.FanoutTrace(heats_enumerated=1)
            try:
                return sporthive.scrape_event_all(url)
            except Exception as exc:
                self.last_trace.failures.append({"heat_slug": "", "reason": str(exc)})
                raise

        results, trace = sporthive.scrape_event_fanout(
            url, cache_probe=cache_probe, on_heat_start=on_heat_start,
        )
        self.last_trace = trace
        return results


class ChronoWebProvider(HostMatchedProvider):
    name = "chronoweb"
    _HOSTS = ("chronoweb.com",)

    def scrape_event_all(self, url: str) -> list[ScrapedResult]:
        return chronoweb.scrape_event_all(url)


class T2AreaProvider:
    name = "t2area"

    def matches(self, url: str) -> bool:
        # Allowlist **explicite** du seul host FFTRI : T2Area sert d'autres
        # fédérations sur d'autres sous-domaines, hors périmètre de #51. D'où
        # l'égalité stricte, et non `_host_match`, qui accepterait aussi les
        # sous-domaines de `fftri.t2area.com`.
        # `_url_host` (et non un `urlparse` direct) : dernier provider avant le
        # fallback, celui-ci est traversé par toute URL non reconnue — un host
        # IPv6 malformé y ferait lever `detect_provider`.
        return _url_host(url) == "fftri.t2area.com"

    def scrape_event_all(self, url: str) -> list[ScrapedResult]:
        return t2area.scrape_event_all(url)


class PlaywrightProvider:
    """Sentinelle « aucun provider ne reconnaît cette URL » — pas un scraper.

    Le nom est historique : il désignait un fallback générique pour les sites
    JS-heavy. Ce module (`scrapers/playwright_fallback.py`) était du code mort et
    a été supprimé avec la dépendance `playwright` (#102), car il restait **le
    seul du dépôt capable de naviguer vers une URL arbitraire** : le rebrancher
    ici rouvrirait le SSRF de #49, et sans qu'aucune détection de host ne
    s'interpose, puisque ce fallback est précisément ce qui capte les hosts non
    reconnus.

    D'où le refus explicite ci-dessous, verrouillé par
    `test_host_non_reconnu_ne_declenche_aucune_requete`. Un futur fallback
    générique se **valide en amont sur une liste blanche de hosts** ; il ne
    s'accroche pas à ce point d'entrée.
    """

    name = "playwright"

    def matches(self, url: str) -> bool:
        return True  # capte tout ce qui n'a pas été reconnu avant

    def scrape_event_all(self, url: str) -> list[ScrapedResult]:
        raise ValueError(
            "Import de tous les participants non supporté pour ce provider : playwright"
        )


# Ordre important : breizhchrono et wiclax avant klikego (conditions plus spécifiques).
PROVIDERS: list[ScraperProtocol] = [
    BreizhChronoProvider(),
    WiclaxProvider(),
    KlikegoProvider(),
    TimePulseProvider(),
    ProLiveSportProvider(),
    SportInnovationProvider(),
    RaceResultProvider(),
    ChronoplaceProvider(),
    OkTimeProvider(),
    CompetitorProvider(),
    RunnerBreizhProvider(),
    SporthiveProvider(),
    ChronoWebProvider(),
    T2AreaProvider(),
]
_FALLBACK: ScraperProtocol = PlaywrightProvider()


def _find_provider(url: str) -> ScraperProtocol:
    for provider in PROVIDERS:
        if provider.matches(url):
            return provider
    return _FALLBACK


def provider_names() -> list[str]:
    """Noms des providers **ciblables**, dans l'ordre de détection.

    Source de vérité unique pour valider un `--provider` / `--only-provider` :
    dérivée de `PROVIDERS`, elle ne peut pas se désynchroniser au prochain
    provider ajouté.

    `playwright` en est absent volontairement : c'est le fallback des URLs non
    reconnues, pas un provider qu'on peut cibler. `sheet_source.is_supported`
    l'exclut déjà de l'import de masse, et aucune course en base ne peut porter
    ce nom (son `scrape_event_all` lève).
    """
    return [provider.name for provider in PROVIDERS]


def detect_provider(url: str) -> str:
    return _find_provider(url).name


def get_provider(url: str) -> ScraperProtocol | None:
    """Retourne l'instance de provider qui reconnaît l'URL, ou None.

    Distinct de `detect_provider` (qui rend le slug) : cette fonction expose
    l'instance elle-même, nécessaire à `import_service.iter_import_event` pour
    lire des attributs post-scrape comme `KlikegoProvider.last_trace`.
    Ignore le fallback (Playwright) : une URL non reconnue → None.
    """
    for provider in PROVIDERS:
        if provider.matches(url):
            return provider
    return None


def is_supported(url: str) -> bool:
    """Vrai si un provider du registre reconnaît l'URL (fallback playwright exclu).

    Source de vérité unique du « supporté ou non », partagée par l'import de
    masse (`sheet_source`) et par l'API `/scrape/detect` — donc par le badge du
    front. Ce dernier portait sa propre liste, figée à six providers : toute URL
    Competitor, RaceResult ou Chronoplace s'affichait « Non supporté » alors que
    l'import fonctionnait (même piège de définition dupliquée que #76).
    """
    return detect_provider(url) in provider_names()


#: Providers qui exposent le fan-out (patron #195/#156) : ils acceptent
#: `cache_probe` et `on_heat_start` en kwargs. Les autres sont appelés sans
#: kwargs pour rester rétro-compatibles.
_FANOUT_PROVIDERS: tuple[type, ...] = (
    KlikegoProvider,
    ChronoplaceProvider,
    SporthiveProvider,
    RaceResultProvider,
)


def scrape_event_all(url: str, **kwargs) -> list[ScrapedResult]:
    """Dispatch vers le provider matché.

    `**kwargs` propage les options optionnelles (`cache_probe`, `on_heat_start`,
    `single_heat`) aux providers qui les acceptent — les autres, qui ne les
    connaissent pas dans leur signature, sont appelés sans kwargs.
    """
    provider = _find_provider(url)
    logger.info("Import épreuve via %s : %s", provider.name, url)
    if isinstance(provider, _FANOUT_PROVIDERS):
        return provider.scrape_event_all(url, **kwargs)
    return provider.scrape_event_all(url)
