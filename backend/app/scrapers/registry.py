"""
Registre des providers de chronométrage.

Chaque provider est une instance implémentant `ScraperProtocol`. La détection se
fait en parcourant la liste `PROVIDERS` (plus de chaîne de `if/else`). Ajouter un
provider = créer son adapter et l'ajouter à la liste, à un seul endroit.

Provider inconnu → `get_provider` rend `None`, et `scrape_event_all` lève. Il n'y
a **pas** de sentinelle attrape-tout : elle n'existait que pour qu'une fonction
rende toujours un objet, et son slug `playwright` mentait — la dépendance a été
supprimée en #102. Un futur fallback générique se **valide en amont sur une liste
blanche de hosts** ; il ne s'accroche pas à ce point d'entrée, sans quoi il
rouvrirait le SSRF de #49 en captant précisément les hosts non reconnus
(verrouillé par `test_host_non_reconnu_ne_declenche_aucune_requete`).

La détection se fait sur le **host** de l'URL, jamais sur une sous-chaîne de
l'URL entière : un jeton en query suffisait à router n'importe quelle URL vers
un scraper, qui la requêtait telle quelle (SSRF, issue #49). La règle est dans
`_host_match`, appliquée par défaut via `HostMatchedProvider`.

NOTE — La classification du type d'épreuve est centralisée dans
`scrapers/classify.py` (seule source de vérité) ; les scrapers l'appellent
directement. Le mapping des splits, lui, reste propre à chaque provider.
"""
import logging
from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable
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
from app.scrapers.base import FanoutTrace, ScrapedResult

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


class FanoutProvider(HostMatchedProvider):
    """Provider à fan-out : détection par host, sous-unités scrapées une à une.

    Le patron #156/#195, écrit une fois. Un provider n'a plus qu'à déclarer son
    `_module` — qui expose `scrape_event_fanout` pour le chemin nominal et
    `scrape_event_all` pour l'échappatoire — et ses `_HOSTS`. Ce qui lui est
    propre se surcharge, comme avant : la règle de match composée de Wiclax, le
    parsing d'URL de Klikego, la sémantique `single_heat` de ChronoWeb.

    `last_trace` est lue par `import_service` après le scrape pour peupler les
    5 compteurs de FR-008. C'est aussi ce type qui décide du dispatch :
    `isinstance(provider, FanoutProvider)` a remplacé un tuple de sept classes
    tenu à la main, qu'un huitième provider aurait pu ne jamais rejoindre.
    """

    #: Module du scraper (`scrape_event_fanout` + `scrape_event_all`).
    _module: Any = None
    #: Ce que porte `heat_slug` quand l'échappatoire échoue. RaceResult y met
    #: l'URL — c'est sa sous-unité —, les autres n'ont rien à nommer.
    _echec_slug_est_url = False

    def __init__(self) -> None:
        self.last_trace: FanoutTrace | None = None

    def scrape_event_all(
        self, url: str,
        *,
        cache_probe: Callable[[str], bool] | None = None,
        on_heat_start: Callable[[str, str, int, int], None] | None = None,
        single_heat: bool = False,
    ) -> list[ScrapedResult]:
        """Fan-out par défaut ; `single_heat=True` court-circuite sans cache_probe."""
        if single_heat:
            # Échappatoire `--single-heat` : aucun fan-out, mais une trace
            # synthétique 1-heat pour maintenir l'invariant
            # `enumerated = imported + cached + len(failures)`.
            self.last_trace = FanoutTrace(heats_enumerated=1)
            try:
                return self._module.scrape_event_all(url)
            except Exception as exc:
                self.last_trace.failures.append({
                    "heat_slug": url if self._echec_slug_est_url else "",
                    "reason": str(exc),
                })
                raise

        results, trace = self._module.scrape_event_fanout(
            url, cache_probe=cache_probe, on_heat_start=on_heat_start,
        )
        self.last_trace = trace
        return results


class ModuleProvider(HostMatchedProvider):
    """Provider sans particularité : détection par host, délégation au module.

    Cinq classes se réduisaient à ce squelette — `name`, `_HOSTS`, et un
    `scrape_event_all` qui appelle `<module>.scrape_event_all(url)`. Ajouter un
    chronométreur sans fan-out est désormais une ligne de `PROVIDERS`, pas une
    sixième recopie. Ce qui **n'entre pas** dans cette table reste une classe :
    le fan-out et sa `last_trace`, la double façade de Breizh Chrono, la règle de
    match composée de Wiclax, l'égalité stricte de T2Area.
    """

    def __init__(self, name: str, hosts: tuple[str, ...], module) -> None:
        self.name = name
        self._HOSTS = hosts
        self._module = module

    def scrape_event_all(self, url: str) -> list[ScrapedResult]:
        return self._module.scrape_event_all(url)


class KlikegoProvider(FanoutProvider):
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

    _module = klikego

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
            self.last_trace = FanoutTrace(heats_enumerated=1)
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


class WiclaxProvider(FanoutProvider):
    """Wiclax/G-Live — URL d'événement = tous les parcours (fan-out, issue #195).

    Sous-unité = **parcours** (attribut `p` du XML `.clax`). Le `.clax` étant
    partagé par tous les parcours, un seul GET couvre l'événement entier ;
    `cache_probe` ne peut donc pas économiser la requête, il économise la
    construction et la persistance des `ScrapedResult` du parcours frais.

    Le fan-out expose sa progression dans `self.last_trace` (5 compteurs) — lue
    par `import_service` pour peupler le SSE `done` et déduire `heats_imported`.

    `single_heat=True` renvoie ici l'**événement entier**, sans découpage par
    parcours : Wiclax n'expose pas de sélecteur d'URL ciblant un parcours
    particulier, l'échappatoire vaut donc « ne pas fan-outer » plutôt que
    « scraper un unique parcours ».
    """

    name = "wiclax"

    # Hosts servant un moteur G-Live. `chronowest.fr` : WordPress + iframe
    # G-Live (issue #35).
    _HOSTS = ("wiclax-results.com", "chronosmetron.com", "chronowest.fr")

    _module = wiclax

    def matches(self, url: str) -> bool:
        # `wiclax.com` est le site vitrine de l'éditeur : il n'est pas dans
        # `_HOSTS`, seuls ses chemins G-Live sont des pages de résultats. D'où
        # la composition sur `_host_match` — surtout pas une copie de la règle.
        # `_url_path` (et non un `urlparse` direct) : un host IPv6 malformé ne
        # doit pas faire lever `matches`, seulement produire un non-match.
        return super().matches(url) or (
            _host_match(url, ("wiclax.com",)) and "G-Live" in _url_path(url)
        )


class RaceResultProvider(FanoutProvider):
    """RaceResult — URL d'événement = tous les contests (fan-out, issue #217).

    Sous-unité = **contest** de `config["contests"]`. Le fan-out expose sa
    progression dans `self.last_trace` (compteurs `heats_enumerated`,
    `heats_cached`, `heats_imported`, `failures`, `cached_urls`) — lue par
    `import_service` pour peupler le SSE `done`.

    `Contest="0"` (« toutes catégories ») est réservé et exclu du fan-out :
    ses listes sont scrapées comme dans le contrat historique. L'échappatoire
    `--single-heat` (chemin `single_heat=True`) court-circuite le fan-out et
    n'appelle **aucun** `cache_probe` — utile aux tests et à un rescrape
    d'événement en pot commun.
    """

    name = "raceresult"

    # Trois façades d'un même produit RaceResult (issue #50), toutes servies
    # par la même API JSON publique.
    _HOSTS = ("raceresult.com", "espace-competition.com", "chronoconsult.fr")

    _module = raceresult
    #: Sa sous-unité est le contest, désigné par l'URL.
    _echec_slug_est_url = True


class ChronoplaceProvider(FanoutProvider):
    """Chronoplace — fan-out par épreuve (cache TTL par sous-unité, épique #195).

    Une URL pointe une épreuve, mais la page liste ses sœurs (onglets) : chaque
    onglet est une sous-unité, avec sa propre `source_url` canonique. Le
    fan-out expose sa progression dans `self.last_trace`.
    """
    name = "chronoplace"
    _HOSTS = ("chronoplace.fr",)

    _module = chronoplace

    # Pas d'échappatoire `single_heat` : la signature ne l'accepte pas, une URL
    # Chronoplace désigne toujours l'événement entier.
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


class OkTimeProvider(FanoutProvider):
    """ok-time — un GET rend l'événement entier ; fan-out par **course** (#221).

    Un seul appel API rapporte toutes les courses de l'événement (comme
    Chronoweb) : le gain n'est pas la requête économisée, mais l'intégrité du
    cache TTL — chaque course reçoit sa propre `source_url` canonique
    `classement.ok-time.fr/<id>/race/<epreuveId>`, donc son propre TTL.

    Le fan-out expose sa progression dans `self.last_trace` (compteurs
    `heats_enumerated`, `heats_cached`, `heats_imported`, `failures`) — lue par
    `import_service` pour peupler le SSE `done`.

    `single_heat=True` conserve l'entrée mono-course : il sert d'échappatoire
    (`rescrape-db --single-heat`) et aux tests unitaires du chemin historique.
    """

    name = "oktime"

    # `ok-time.fr` et ses sous-domaines : `classement.ok-time.fr` (la SPA de
    # classement) et l'apex (le site éditorial, qui sert l'API JSON). Allowlist
    # explicite, comme Wiclax et RaceResult. `_HOSTS` seul : `_host_match`
    # compare sur `hostname` — un port explicite ou des credentials ne font pas
    # rater le match — et exige un point avant le suffixe, sans quoi un host
    # sosie du type `evilok-time.fr` suivrait.
    _HOSTS = ("ok-time.fr",)

    _module = oktime


class SporthiveProvider(FanoutProvider):
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

    _module = sporthive


class ChronoWebProvider(FanoutProvider):
    """Chronoweb — une URL désigne un événement, fan-out par race (issue #220).

    Une seule requête HTML rend l'événement entier ; l'énumération des races
    se fait en mémoire. Le gain du fan-out n'est **pas** la requête économisée
    mais l'intégrité du cache TTL, par race — voir `base.FanoutTrace`.

    L'échappatoire `--single-heat` n'a pas de sens ici (impossible de cibler
    une race à la source, la vue publie l'événement entier). Le mode nominal
    délègue à `scrape_event_fanout` ; sans `cache_probe` c'est équivalent à
    l'ancien `scrape_event_all`, sauf que `source_url` porte désormais le
    `&race=<race_id>` de la sous-unité.
    """

    name = "chronoweb"
    _HOSTS = ("chronoweb.com",)

    _module = chronoweb

    def scrape_event_all(
        self, url: str,
        *,
        cache_probe: Callable[[str], bool] | None = None,
        on_heat_start: Callable[[str, str, int, int], None] | None = None,
        single_heat: bool = False,
    ) -> list[ScrapedResult]:
        """Fan-out par race — l'échappatoire `single_heat` retombe sur le fan-out."""
        if single_heat:
            # Pas de vraie sémantique --single-heat côté source : on rend le
            # chemin non-fanout historique (multi-race, source_url par race).
            self.last_trace = FanoutTrace()
            return chronoweb.scrape_event_all(url)
        results, trace = chronoweb.scrape_event_fanout(
            url, cache_probe=cache_probe, on_heat_start=on_heat_start,
        )
        self.last_trace = trace
        return results


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


# Ordre important : breizhchrono et wiclax avant klikego (conditions plus spécifiques).
PROVIDERS: list[ScraperProtocol] = [
    BreizhChronoProvider(),
    WiclaxProvider(),
    KlikegoProvider(),
    ModuleProvider("timepulse", ("timepulse.fr",), timepulse),
    ModuleProvider("prolivesport", ("prolivesport.fr",), prolivesport),
    ModuleProvider("sportinnovation", ("sportinnovation.fr",), sportinnovation),
    RaceResultProvider(),
    ChronoplaceProvider(),
    OkTimeProvider(),
    # `ironman.com` n'est qu'une vitrine : le moteur est Competitor/WTC, d'où le
    # nom du provider (issue #54). `competitor.com` couvre par sous-domaine la
    # façade réelle `labs-v2.competitor.com`, et les suivantes s'il y en a.
    ModuleProvider("competitor", ("ironman.com", "competitor.com"), competitor),
    ModuleProvider("runnerbreizh", ("runnerbreizh.fr",), runnerbreizh),
    SporthiveProvider(),
    ChronoWebProvider(),
    T2AreaProvider(),
]

def provider_names() -> list[str]:
    """Noms des providers **ciblables**, dans l'ordre de détection.

    Source de vérité unique pour valider un `--provider` / `--only-provider` :
    dérivée de `PROVIDERS`, elle ne peut pas se désynchroniser au prochain
    provider ajouté.
    """
    return [provider.name for provider in PROVIDERS]


def detect_provider(url: str) -> str:
    """Slug du provider qui reconnaît l'URL, **chaîne vide** si aucun ne la
    reconnaît. Rendait `"playwright"` avant #102 — un slug qui désignait une
    dépendance disparue et un scraper qui n'a jamais existé."""
    provider = get_provider(url)
    return provider.name if provider else ""


def get_provider(url: str) -> ScraperProtocol | None:
    """Retourne l'instance de provider qui reconnaît l'URL, ou None.

    Distinct de `detect_provider` (qui rend le slug) : cette fonction expose
    l'instance elle-même, nécessaire à `import_service.iter_import_event` pour
    lire des attributs post-scrape comme `KlikegoProvider.last_trace`.
    Une URL non reconnue → None.
    """
    for provider in PROVIDERS:
        if provider.matches(url):
            return provider
    return None


def is_supported(url: str) -> bool:
    """Vrai si un provider du registre reconnaît l'URL.

    Source de vérité unique du « supporté ou non », partagée par l'import de
    masse (`bulk_import_service`) et par l'API `/scrape/detect` — donc par le
    badge du front. Ce dernier portait sa propre liste, figée à six providers :
    toute URL Competitor, RaceResult ou Chronoplace s'affichait « Non supporté »
    alors que l'import fonctionnait (même piège de définition dupliquée que #76).
    """
    return get_provider(url) is not None


def scrape_event_all(url: str, **kwargs) -> list[ScrapedResult]:
    """Dispatch vers le provider matché.

    `**kwargs` propage les options optionnelles (`cache_probe`, `on_heat_start`,
    `single_heat`) aux providers qui les acceptent — les autres, qui ne les
    connaissent pas dans leur signature, sont appelés sans kwargs.
    """
    provider = get_provider(url)
    if provider is None:
        raise ValueError(f"Aucun provider ne reconnaît cette URL : {url}")
    logger.info("Import épreuve via %s : %s", provider.name, url)
    if isinstance(provider, FanoutProvider):
        return provider.scrape_event_all(url, **kwargs)
    return provider.scrape_event_all(url)
