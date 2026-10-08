"""Le scrape d'un import : validation d'URL, dispatch vers le fournisseur, cache TTL (#1186).

`registry_scrape_event_all` est le point de substitution des tests : il est lu
ici, par `scrape_all` et `scrape_all_streaming`. Le cache TTL a deux
consommateurs, `cached_result` (court-circuit global par URL) et
`_make_cache_probe` (sonde par heat du fan-out, #156).
"""
import logging
import queue
import re
import threading
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import replace
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.core.club import is_tcn
from app.core.config import Settings
from app.core.database import SessionLocal
from app.core.exceptions import InvalidUrlError, ProviderNotSupportedError, ScraperError
from app.core.youth import is_youth
from app.repositories import course_repository, participation_repository
from app.scrapers import registry
from app.scrapers import scrape_event_all as registry_scrape_event_all
from app.scrapers.base import FanoutTrace, ScrapedResult
from app.services import cache

logger = logging.getLogger(__name__)

_DOUBLE_ENCODED = re.compile(r"%25([0-9A-Fa-f]{2})")


def validate_url(url: str) -> str:
    """Refuse tout ce qui n'est pas une URL http(s) nommant un host.

    Passage obligé de **tous** les chemins d'import — API, SSE, CLI
    `import-sheet` et `rescrape-db` — et donc la seule garde du batch, qui n'a
    aucun schéma Pydantic devant lui. L'ancien `startswith("http")` laissait
    passer `httpfoo://` comme une URL sans host (#49).

    Ne réécrit rien au-delà du strip et d'un chemin encodé deux fois (#1225) :
    `source_url` est la clé du cache TTL. Un `%25XX` dans le chemin vient d'un
    copier-coller d'URL déjà encodée et répond 404 ; seule cette couche en trop
    est retirée, `%20` ou `%C3%A9` restent tels quels.

    `urlparse` lève `ValueError` sur un host IPv6 malformé (ex. `https://[oops/x`) :
    à traiter comme une URL invalide parmi d'autres, pas comme un crash.
    """
    url = (url or "").strip()
    try:
        parsed = urlparse(url)
    except ValueError as exc:
        raise InvalidUrlError() from exc
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise InvalidUrlError()
    if "%25" in parsed.path:
        url = parsed._replace(path=_DOUBLE_ENCODED.sub(r"%\1", parsed.path)).geturl()
    return url


def merge_cached_courses(
    db: Session, persister_courses: list[dict], trace,
) -> list[dict]:
    """Étoffe le `courses` du SSE `done` avec les heats sautés par cache_probe.

    Sans ce complément, un ré-import Klikego où k heats sur N sont trouvés
    frais retomberait sur un `done` listant seulement les N-k courses
    effectivement re-scrapées : le sélecteur de fin d'import (front #135) ne
    proposerait qu'une partie des heats de l'événement. C'est un vrai bug de
    contrat SSE au regard de FR-008 (« le done reflète l'événement entier »).

    Les Course des heats cachés sont chargées en un seul `IN` — un événement
    à 20 heats cachés ne fait pas 20 requêtes. Dédup sur `id` : un heat qui
    aurait à la fois été re-scrapé **et** listé cached (cas théorique) ne
    remonte qu'une fois. Ordre : d'abord les re-scrapés (ordre de rencontre
    dans `import_persistence._Persister.add`), puis les cachés (ordre `scraped_at`
    desc).
    """
    if trace is None or not getattr(trace, "cached_urls", None):
        return persister_courses
    cached = course_repository.list_by_source_urls(db, trace.cached_urls)
    seen: set[int] = {c["id"] for c in persister_courses}
    merged = list(persister_courses)
    for course in cached:
        if course.id in seen:
            continue
        seen.add(course.id)
        merged.append({
            "id": course.id, "name": course.name,
            "event_type": course.event_type, "is_relay": bool(course.is_relay),
        })
    return merged


def fanout_counters(trace) -> dict:
    """Construit les 5 clés de FR-008 depuis la `FanoutTrace` du provider.

    Invariant : `heats_enumerated = heats_imported + heats_cached + heats_failed`.
    `heats_imported` est **dérivé** ici (le scraper ne le connaît pas).

    Sur cache global frais (court-circuit `cached_result`) ou résultat vide :
    tous les compteurs valent 0 avec `failures=[]` — contrat sans branche
    conditionnelle côté consommateur.
    """
    if trace is None:
        return {
            "heats_enumerated": 0, "heats_imported": 0,
            "heats_cached": 0, "heats_failed": 0, "failures": [],
        }
    heats_failed = len(trace.failures)
    heats_imported = trace.heats_enumerated - trace.heats_cached - heats_failed
    return {
        "heats_enumerated": trace.heats_enumerated,
        "heats_imported": max(0, heats_imported),
        "heats_cached": trace.heats_cached,
        "heats_failed": heats_failed,
        "failures": list(trace.failures),
    }


def _make_cache_probe(db: Session, settings: Settings):
    """Construit un callback `cache_probe(heat_url) -> bool` — fan-out Klikego (#156).

    Le scraper Klikego l'invoque **avant** de scraper chaque heat : True signifie
    « déjà en base et frais côté cache TTL, à sauter ». Mirroir de la règle du
    cache global (`cached_result`) mais au niveau du heat individuel.
    """
    def probe(heat_url: str) -> bool:
        try:
            course = course_repository.get_latest_by_source_url(db, heat_url)
            return course is not None and cache.is_fresh(db, course, settings)
        finally:
            # Sans quoi la connexion reste « idle in transaction » tout le fan-out (#1015).
            db.rollback()

    return probe


def scrape_all(
    url: str, db: Session, settings: Settings, *, single_heat: bool = False,
    use_cache_probe: bool = True,
) -> tuple[list[ScrapedResult], FanoutTrace | None]:
    """Scrape l'URL et remonte optionnellement la `FanoutTrace` du provider.

    Passe par le dispatcher `registry.scrape_event_all(url, **kwargs)` — les
    kwargs sont propagés aux providers fan-out matchés (Klikego #156,
    RaceResult #217 reçoivent `cache_probe`, les autres l'ignorent via
    `**kwargs` du dispatcher). La trace qui peuple les 5 compteurs de FR-008 est
    rendue par l'appel lui-même (#1016).

    Retour : `(results, trace)`.

    Pas de progression par heat ici — le chemin SSE l'obtient via
    `scrape_all_streaming`, qui est un générateur. Ce chemin non-streaming
    reste utilisé par le CLI (`batch`) et le fallback `import_event`.

    `use_cache_probe=False` retire le cache TTL **par heat** (#285) : sans probe,
    un provider fan-out scrape toutes ses sous-unités. C'est ce que demande un
    remplacement total, où sauter un heat jugé frais laisserait l'épreuve vide
    de la moitié de son classement — l'épreuve visée par une bascule est
    précisément celle qu'on vient de scraper, donc la plus fraîche de la base.
    """

    cache_probe = _make_cache_probe(db, settings) if use_cache_probe else None
    provider = registry.get_provider(url)

    try:
        if isinstance(provider, registry.FanoutProvider):
            # Providers fan-out (patron #156/#195) : cache TTL par sous-unité.
            # `single_heat` n'a de sens que pour ceux dont l'URL le porte
            # (Klikego avec ?heat=…). Les autres retombent sur leur contrat
            # historique (événement entier en pot commun).
            if single_heat:
                outcome = registry_scrape_event_all(url, single_heat=True)
            else:
                outcome = registry_scrape_event_all(url, cache_probe=cache_probe)
        else:
            # Autres providers, et URL non reconnue (`get_provider` → None, le
            # dispatcher lève) : trace synthétique 1-heat du dispatcher.
            outcome = registry_scrape_event_all(url)
    except ValueError as exc:  # provider non supporté pour l'import en masse
        raise ProviderNotSupportedError(str(exc)) from exc
    except Exception as exc:
        logger.warning("Échec import %s : %s", url, exc)
        raise ScraperError(f"Erreur lors de l'import : {exc}") from exc

    # Déballé hors du `try` : un retour mal formé est un défaut de code, pas un
    # fournisseur non supporté (#1016).
    results, trace = outcome
    return _importable(url, results), trace


def scrape_all_streaming(
    url: str, db: Session, settings: Settings, *, use_cache_probe: bool = True,
    single_heat: bool = False,
) -> Iterator[dict]:
    """Variante générateur de `scrape_all`, pour le SSE.

    Yield des phases `scraping` avec `heat_index/heats_total/heat_slug/heat_label`
    au fur et à mesure que le fan-out Klikego (#156) attaque chaque heat.
    Retour du générateur (StopIteration.value) : `(results, trace)`, sur le
    même contrat que `scrape_all`.

    Le fan-out Klikego peut prendre 30-40 s : sans progression intermédiaire,
    la phase `scraping` reste figée sur son message initial et l'opérateur croit
    que la requête est bloquée. Sur un provider non-Klikego (mono-course), on
    appelle directement `scrape_all` — pas de yield intermédiaire.

    Pour Klikego (seul fournisseur concerné, #583), les mêmes clés portent en
    plus `detail_done`/`detail_total` : la progression de la phase C **dans**
    le heat en cours, sans quoi un heat de 250 participants resterait figé
    plusieurs minutes entre deux events par heat.

    Implémentation : le scrape tourne dans un thread pour permettre au
    générateur de lire une file d'événements en parallèle. Le thread pousse
    dans `queue.Queue` à chaque `on_heat_start`/`on_detail_progress`, plus un
    sentinel en fin de scrape. Le générateur draine la file avec
    `get(timeout=…)` pour rester responsive tout en ne bufférisant pas.

    `use_cache_probe=False` retire le cache TTL **par heat** (#118, research.md
    R2), même paramètre que `scrape_all` — sans lui, un re-scrape demandé sur
    une épreuve fan-out fraîchement importée sauterait tous ses heats jugés
    frais, laissant le classement inchangé malgré la demande explicite.

    `single_heat=True` (#698) prend l'échappatoire mono-sous-unité **sans
    perdre la progression** : le générateur reste le même, seul le scrape
    change de chemin. Sur Klikego — le seul provider dont l'URL cible un heat
    *et* qui a une phase C par participant à rapporter —, `on_detail_progress`
    est passé au provider, qui notifie `1/1` plus l'avancement des détails du
    heat visé. Sur les autres, il n'y a rien à streamer : on retombe sur le
    chemin bloquant, qui rend exactement le même couple `(results, trace)`.
    Ce chemin n'appelle **jamais** `cache_probe`, comme `scrape_all` : une
    sous-unité unique explicitement demandée ne se saute pas.

    `ponytail:` (#566, point 1) `cache_probe` referme originellement sur `db` et
    s'exécute sur le thread de travail — pas sur celui qui possède la Session.
    Sur déconnexion SSE, Starlette/asyncio finit par clore ce générateur (le
    plus souvent via le ramasse-miettes cyclique, pas un `close()` explicite
    immédiat — l'abandon n'est pas synchrone). Ce close relance `GeneratorExit`
    **sur le thread qui l'a déclenché**, quel qu'il soit : une première version
    de ce correctif ajoutait un `finally: thread.join()` autour de la boucle de
    drainage pour garantir que le thread ait fini d'utiliser `db` avant que
    `scrape.py::produce()` ne la ferme — mesuré à la main (`iterate_in_threadpool`
    + `asyncio`), ce close peut retomber sur le **thread de la boucle asyncio**
    elle-même, donc `thread.join()` y bloque tout le worker (toutes les requêtes
    concurrentes du même process) pour la durée du scrape, pas seulement ce flux
    SSE — pire que le défaut d'origine. Le correctif retenu ne joint donc pas :
    `scrape_in_thread` ouvre sa **propre** `Session` (`SessionLocal()`, patron de
    `scrape.py`) pour la sonde de cache, qu'il referme dans son propre `finally`
    — le thread ne touche plus jamais la Session de l'appelant, quelle que soit
    la vitesse à laquelle celui-ci la ferme. Coût accepté, même nature que le
    `ponytail:` d'`course_rescrape_service._stream_rescrape` : une connexion tenue jusqu'à
    la fin du thread détaché, upgrade si mesuré en production.
    """
    provider = registry.get_provider(url)

    if not isinstance(provider, registry.FanoutProvider):
        # Chemin non-fan-out : bloquant unique, aucun yield intermédiaire.
        results, trace = scrape_all(url, db, settings, use_cache_probe=use_cache_probe)
        return (results, trace)

    if single_heat and not isinstance(provider, registry.KlikegoProvider):
        # Mono-sous-unité sans phase C à rapporter : le thread et sa file
        # n'auraient aucun événement à porter. Chemin bloquant, même couple.
        results, trace = scrape_all(url, db, settings, single_heat=True)
        return (results, trace)

    events: queue.Queue[dict | object] = queue.Queue()
    sentinel = object()
    holder: dict = {}

    def on_heat_start(heat_slug: str, heat_label: str, index: int, total: int) -> None:
        events.put({
            "phase": "scraping",
            "heat_slug": heat_slug,
            "heat_label": heat_label,
            "heat_index": index,
            "heats_total": total,
        })

    def on_detail_progress(
        heat_slug: str, heat_label: str, heat_index: int, heats_total: int,
        done: int, total: int,
    ) -> None:
        events.put({
            "phase": "scraping",
            "heat_slug": heat_slug,
            "heat_label": heat_label,
            "heat_index": heat_index,
            "heats_total": heats_total,
            "detail_done": done,
            "detail_total": total,
        })

    def scrape_in_thread() -> None:
        # `ponytail:` ci-dessus (#566, point 1) — Session dédiée au thread,
        # jamais celle de l'appelant (`db`). Construite **dans** le `try` : si
        # `SessionLocal()` elle-même levait, le `finally` doit quand même
        # poser le sentinel — sinon le générateur reste bloqué à attendre une
        # file qui ne recevra jamais rien.
        thread_db = None
        try:
            kwargs: dict
            if single_heat:
                # Ici, provider est forcément Klikego (filtré au-dessus) : pas
                # de `cache_probe`, donc pas de Session de thread à ouvrir, mais
                # la phase C du heat visé reste rapportée (#698).
                kwargs = {
                    "single_heat": True, "on_detail_progress": on_detail_progress,
                }
            else:
                thread_db = SessionLocal() if use_cache_probe else None
                cache_probe = (
                    _make_cache_probe(thread_db, settings) if thread_db is not None else None
                )
                # `on_detail_progress` (#583) : seul Klikego a une phase C par
                # participant à rapporter — les autres FanoutProvider ne
                # l'acceptent pas dans leur signature.
                kwargs = {"cache_probe": cache_probe, "on_heat_start": on_heat_start}
                if isinstance(provider, registry.KlikegoProvider):
                    kwargs["on_detail_progress"] = on_detail_progress
            # La trace voyage avec les résultats, propres à ce thread (#1016).
            # Déballée par le générateur, hors du relais d'erreur de scrape.
            holder["outcome"] = registry_scrape_event_all(url, **kwargs)
        except BaseException as exc:  # noqa: BLE001 — relayé au générateur
            holder["error"] = exc
        finally:
            if thread_db is not None:
                thread_db.close()
            events.put(sentinel)

    thread = threading.Thread(target=scrape_in_thread, daemon=True)
    thread.start()

    while True:
        # 0,5 s = compromis entre réactivité de la coupure côté client et coût
        # CPU. Le scrape émet un événement toutes les ~4 s, on ne va pas plus
        # vite. Le timeout permet aussi de laisser le thread mourir sans bloquer
        # le générateur si un heat n'appelle jamais le callback (cache_probe).
        try:
            item = events.get(timeout=0.5)
        except queue.Empty:
            continue
        if item is sentinel:
            break
        yield item

    thread.join()

    if "error" in holder:
        exc = holder["error"]
        if isinstance(exc, ValueError):
            raise ProviderNotSupportedError(str(exc)) from exc
        logger.warning("Échec import %s : %s", url, exc)
        raise ScraperError(f"Erreur lors de l'import : {exc}") from exc

    results, trace = holder["outcome"]
    return (_importable(url, results), trace)


def _row_is_youth(r: ScrapedResult) -> bool:
    return is_youth(r.event_name, r.category, event_year=r.event_date.year if r.event_date else None)


def _importable(url: str, results: list[ScrapedResult]) -> list[ScrapedResult]:
    """Les résultats scrapés que l'import écrit : l'épreuve doit avoir un nom, et
    les épreuves jeunes (jusqu'à Minime) sont écartées (#881, RGPD), sauf dans
    un heat qui porte au moins un jeune TCN : celui-ci est gardé entier (#1221).

    Ici et non dans chaque scraper : les deux chemins de scrape (bloquant et
    SSE) aboutissent là, et tout chemin d'écriture, import comme re-scrape
    admin, passe par l'un d'eux.
    """
    _require_event_name(url, results)
    heats_with_tcn_youth = {
        _heat(r)
        for r in results
        if _row_is_youth(r) and is_tcn(r.club)
    }
    retenus: list[ScrapedResult] = []
    excluded_ranks: dict[tuple, set[int]] = defaultdict(set)
    for r in results:
        heat = _heat(r)
        if not _row_is_youth(r) or heat in heats_with_tcn_youth:
            retenus.append(r)
        elif r.rank_overall:
            excluded_ranks[heat].add(r.rank_overall)
    if excluded_ranks:
        retenus = [
            replace(r, excluded_ranks=frozenset(excluded_ranks[_heat(r)]))
            if _heat(r) in excluded_ranks else r
            for r in retenus
        ]
    if len(retenus) < len(results):
        logger.info("Import %s : %d ligne(s) d'épreuve jeune écartée(s)", url, len(results) - len(retenus))
    return retenus


def _heat(result: ScrapedResult) -> tuple:
    return (result.source_url, result.event_name, result.event_date)


def _require_event_name(url: str, results: list[ScrapedResult]) -> None:
    """Refuse un scrape dont l'épreuve n'a pas de nom : la course serait illisible.

    Une `Course` sans nom n'est ni lisible dans l'UI ni retrouvable à la
    recherche, et son identité `(nom, date, type)` entre en collision avec
    toute autre course anonyme du même jour. On échoue avant d'écrire : le
    batch la compte en erreur et l'opérateur la voit dans son bilan.
    """
    if any(not (r.event_name or "").strip() for r in results):
        raise ScraperError(
            f"Nom d'épreuve introuvable pour {url} — import refusé "
            "(une course sans nom serait inexploitable)."
        )


def cached_result(db: Session, url: str, settings: Settings) -> dict | None:
    """Si une course fraîche existe pour cette URL, renvoie le résultat sans re-scraper.

    Une URL peut porter plusieurs `Course` (heats Klikego, catégories Wiclax…) :
    la fraîcheur est jugée sur la plus récente (`get_latest_by_source_url`) —
    dans une même URL toutes sont scrapées ensemble, donc leur `scraped_at`
    diverge de peu et la garde `is_fresh` reste homogène. En revanche `skipped`
    et `courses` doivent porter **toutes** les heats : sans quoi le compteur
    du bandeau doublon mentirait (6 heats × 250 participants → 250) et le
    sélecteur du front (#135) n'offrirait qu'une des courses accessibles.
    """
    latest = course_repository.get_latest_by_source_url(db, url)
    if not (latest and cache.is_fresh(db, latest, settings)):
        return None
    heats = course_repository.list_by_source_url(db, url)
    total = sum(participation_repository.count_for_course(db, c.id) for c in heats)
    logger.info("Cache TTL frais pour %s — re-scraping court-circuité", url)
    return {
        "imported": 0,
        "updated": 0,
        "skipped": total,
        "reconciled": 0,
        "cached": True,
        # Rien n'a été scrapé, donc rien n'a pu être rattaché — mais la clé est là
        # sur les trois chemins de `done`, pour que le consommateur n'ait aucun
        # accès conditionnel à gérer.
        "passive_sources": [],
        "ambiguous_identities": [], "homonyms_created": [],
        "courses": [
            {
                "id": c.id, "name": c.name,
                "event_type": c.event_type, "is_relay": bool(c.is_relay),
            }
            for c in heats
        ],
    }
