"""
Service d'import en masse d'une épreuve (tous les participants).

Inclut le cache TTL (court-circuite le re-scraping si la course est fraîche),
la déduplication par (course, dossard), un rollback explicite en cas d'erreur,
le calcul de l'indice de fiabilité de chaque course touchée (`services/quality.py`),
et un générateur de progression pour le streaming SSE.
"""
import logging
import queue
import threading
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.core.club import is_tcn
from app.core.config import Settings
from app.core.database import SessionLocal
from app.core.exceptions import InvalidUrlError, ProviderNotSupportedError, ScraperError
from app.core.time import utcnow
from app.models.athlete import Athlete
from app.models.course import Course
from app.models.course_source import CourseSource
from app.models.participation import Participation
from app.repositories import athlete_repository, course_repository, participation_repository
from app.scrapers import registry
from app.scrapers import scrape_event_all as registry_scrape_event_all
from app.scrapers.base import STATUS_DNF, STATUS_FINISHER, FanoutTrace, ScrapedResult
from app.services import cache, mapping, quality

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Reassignment:
    """Une identité réconciliée : ancienne graphie → nouvelle, et sa nature.

    `fusion` = True quand la cible corrigée préexistait (deux fiches en une),
    False quand elle vient d'être créée (simple renommage). Labels figés à la
    réassignation : ils survivent au rollback d'un dry-run.
    """
    ancien: str
    nouveau: str
    fusion: bool


@dataclass(frozen=True)
class PassiveSource:
    """Une URL enregistrée comme source **passive** d'une épreuve déjà connue (#283).

    Ni une erreur, ni un import : rien n'a échoué, et rien n'a été ajouté au
    classement. C'est un fait à rapporter — même forme que `BatchFailure` (url,
    libellé, message) pour qu'un seul objet serve le SSE, le `--json` et le
    bilan texte de la CLI.

    Le message est figé ici, à l'endroit qui connaît le nom de l'épreuve : plus
    haut, le bilan de batch n'aurait plus que des URLs à recoller entre elles.
    """
    url: str
    course_name: str
    message: str


def _identite(athlete) -> str:
    """Libellé d'identité pour le bilan : « NOM | Prénom »."""
    return f"{athlete.nom} | {athlete.prenom}"


def _validate_url(url: str) -> str:
    """Refuse tout ce qui n'est pas une URL http(s) nommant un host.

    Passage obligé de **tous** les chemins d'import — API, SSE, CLI
    `import-sheet` et `rescrape-db` — et donc la seule garde du batch, qui n'a
    aucun schéma Pydantic devant lui. L'ancien `startswith("http")` laissait
    passer `httpfoo://` comme une URL sans host (#49).

    Ne réécrit rien au-delà du strip : `source_url` est la clé du cache TTL.

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
    return url


def _merge_cached_courses(
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
    dans `_Persister.add`), puis les cachés (ordre `scraped_at` desc).
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


def _fanout_counters(trace) -> dict:
    """Construit les 5 clés de FR-008 depuis la `FanoutTrace` du provider.

    Invariant : `heats_enumerated = heats_imported + heats_cached + heats_failed`.
    `heats_imported` est **dérivé** ici (le scraper ne le connaît pas).

    Sur cache global frais (court-circuit `_cached_result`) ou résultat vide :
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
    cache global (`_cached_result`) mais au niveau du heat individuel.
    """
    def probe(heat_url: str) -> bool:
        course = course_repository.get_latest_by_source_url(db, heat_url)
        return course is not None and cache.is_fresh(db, course, settings)

    return probe


def _scrape_all(
    url: str, db: Session, settings: Settings, *, single_heat: bool = False,
    use_cache_probe: bool = True,
) -> tuple[list[ScrapedResult], FanoutTrace | None]:
    """Scrape l'URL et remonte optionnellement la `FanoutTrace` du provider.

    Passe par le dispatcher `registry.scrape_event_all(url, **kwargs)` — les
    kwargs sont propagés aux providers fan-out matchés (Klikego #156,
    RaceResult #217 reçoivent `cache_probe`, les autres l'ignorent via
    `**kwargs` du dispatcher). Après l'appel, lit `provider.last_trace` pour
    peupler les 5 compteurs de FR-008.

    Retour : `(results, trace)`. `trace` peut être `None` pour un provider qui
    n'expose pas de trace (comportement mono-heat implicite — `_fanout_counters`
    rend alors les 5 clés à 0/[]).

    Pas de progression par heat ici — le chemin SSE l'obtient via
    `_scrape_all_streaming`, qui est un générateur. Ce chemin non-streaming
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
                results = registry_scrape_event_all(url, single_heat=True)
            else:
                results = registry_scrape_event_all(url, cache_probe=cache_probe)
            trace = provider.last_trace
        else:
            # Autres providers, et URL non reconnue (`get_provider` → None, le
            # dispatcher lève) — pas de trace de fan-out.
            # Trace synthétique 1-heat pour maintenir l'invariant `enumerated = imported`.
            results = registry_scrape_event_all(url)
            trace = FanoutTrace(heats_enumerated=1)
    except ValueError as exc:  # provider non supporté pour l'import en masse
        raise ProviderNotSupportedError(str(exc)) from exc
    except Exception as exc:
        logger.warning("Échec import %s : %s", url, exc)
        raise ScraperError(f"Erreur lors de l'import : {exc}") from exc

    _require_event_name(url, results)
    return results, trace


def _scrape_all_streaming(
    url: str, db: Session, settings: Settings, *, use_cache_probe: bool = True,
    single_heat: bool = False,
) -> Iterator[dict]:
    """Variante générateur de `_scrape_all`, pour le SSE.

    Yield des phases `scraping` avec `heat_index/heats_total/heat_slug/heat_label`
    au fur et à mesure que le fan-out Klikego (#156) attaque chaque heat.
    Retour du générateur (StopIteration.value) : `(results, trace)`, sur le
    même contrat que `_scrape_all`.

    Le fan-out Klikego peut prendre 30-40 s : sans progression intermédiaire,
    la phase `scraping` reste figée sur son message initial et l'opérateur croit
    que la requête est bloquée. Sur un provider non-Klikego (mono-course), on
    appelle directement `_scrape_all` — pas de yield intermédiaire.

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
    R2), même paramètre que `_scrape_all` — sans lui, un re-scrape demandé sur
    une épreuve fan-out fraîchement importée sauterait tous ses heats jugés
    frais, laissant le classement inchangé malgré la demande explicite.

    `single_heat=True` (#698) prend l'échappatoire mono-sous-unité **sans
    perdre la progression** : le générateur reste le même, seul le scrape
    change de chemin. Sur Klikego — le seul provider dont l'URL cible un heat
    *et* qui a une phase C par participant à rapporter —, `on_detail_progress`
    est passé au provider, qui notifie `1/1` plus l'avancement des détails du
    heat visé. Sur les autres, il n'y a rien à streamer : on retombe sur le
    chemin bloquant, qui rend exactement le même couple `(results, trace)`.
    Ce chemin n'appelle **jamais** `cache_probe`, comme `_scrape_all` : une
    sous-unité unique explicitement demandée ne se saute pas.

    `ponytail:` (#566, point 1) `cache_probe` referme originellement sur `db` et
    s'exécute sur le thread de travail — pas sur celui qui possède la Session.
    Sur déconnexion SSE, Starlette/asyncio finit par clore ce générateur (le
    plus souvent via le ramasse-miettes cyclique, pas un `close()` explicite
    immédiat — l'abandon n'est pas synchrone). Ce close relance `GeneratorExit`
    **sur le thread qui l'a déclenché**, quel qu'il soit : une première version
    de ce correctif ajoutait un `finally: thread.join()` autour de la boucle de
    drainage pour garantir que le thread ait fini d'utiliser `db` avant que
    `scrape.py::generate()` ne la ferme — mesuré à la main (`iterate_in_threadpool`
    + `asyncio`), ce close peut retomber sur le **thread de la boucle asyncio**
    elle-même, donc `thread.join()` y bloque tout le worker (toutes les requêtes
    concurrentes du même process) pour la durée du scrape, pas seulement ce flux
    SSE — pire que le défaut d'origine. Le correctif retenu ne joint donc pas :
    `scrape_in_thread` ouvre sa **propre** `Session` (`SessionLocal()`, patron de
    `scrape.py`) pour la sonde de cache, qu'il referme dans son propre `finally`
    — le thread ne touche plus jamais la Session de l'appelant, quelle que soit
    la vitesse à laquelle celui-ci la ferme. Coût accepté, même nature que le
    `ponytail:` d'`admin_actions._stream_rescrape` : une connexion tenue jusqu'à
    la fin du thread détaché, upgrade si mesuré en production.
    """
    provider = registry.get_provider(url)

    if not isinstance(provider, registry.FanoutProvider):
        # Chemin non-fan-out : bloquant unique, aucun yield intermédiaire.
        results, trace = _scrape_all(url, db, settings, use_cache_probe=use_cache_probe)
        return (results, trace)

    if single_heat and not isinstance(provider, registry.KlikegoProvider):
        # Mono-sous-unité sans phase C à rapporter : le thread et sa file
        # n'auraient aucun événement à porter. Chemin bloquant, même couple.
        results, trace = _scrape_all(url, db, settings, single_heat=True)
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
            results = registry_scrape_event_all(url, **kwargs)
            holder["results"] = results
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

    results = holder["results"]
    trace = provider.last_trace
    _require_event_name(url, results)
    return (results, trace)


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


#: Clés d'appariement / d'identité : jamais réécrites par la fusion prudente.
#: `athlete_id` en fait partie — la réconciliation d'identité (#66) est un axe
#: séparé, traité par `_Persister._reconcile_resolved`, pas par ce rafraîchissement de
#: valeurs : les deux s'appliquent à la suite sans jamais écrire les mêmes champs.
_CLES_APPARIEMENT = frozenset({"athlete_id", "course_id", "bib_number"})


def _is_empty(value: object) -> bool:
    """Vide au sens de la fusion prudente : `None`, chaîne vide, dict vide.

    `False` et `0` n'en sont **pas** : un `is_relay=False` est une affirmation du
    scraper, pas une absence, et doit pouvoir corriger un `True` erroné. Un test
    de vérité pythonien (`if value:`) confondrait les deux — d'où l'égalité
    explicite, qui distingue `False`/`0` de `""`/`{}` (`False == {}` est faux).
    """
    return value is None or value == "" or value == {}


def _merge_fields(existing, fields: dict) -> dict:
    """Champs à écrire : source non vide ET différente de la base.

    `status` est exclu ici (traité par `_resolve_status`, car jamais vide) ; les
    clés d'appariement aussi. Comparer avant d'écrire évite des `UPDATE` inutiles
    sur des milliers de lignes inchangées et distingue `updated` de `skipped`.
    """
    changes = {}
    for key, value in fields.items():
        if key in _CLES_APPARIEMENT or key == "status":
            continue
        if _is_empty(value):
            continue
        if getattr(existing, key) != value:
            changes[key] = value
    return changes


def _resolve_status(existing, scraped: ScrapedResult, changes: dict) -> str:
    """Statut fusionné. Un statut explicite du scraper écrase ; sinon on le
    re-dérive du `total_time` **fusionné** (base + écrasement éventuel), jamais du
    scrapé seul : une source ayant perdu le temps ne doit pas basculer un
    finisher en DNF alors que le temps, lui, survit (vide n'écrase pas).
    """
    if scraped.status:
        return scraped.status
    merged_total = changes.get("total_time", existing.total_time)
    return STATUS_FINISHER if merged_total else STATUS_DNF


#: Taille de la tranche de résolution par lot (#706) : au-delà, une course
#: déclenche sa résolution d'athlètes avant la fin du scrape plutôt que
#: d'accumuler une file sans borne. Ordre de grandeur repris de l'audit
#: source (`research.md` de la feature #706) — un détail d'implémentation,
#: pas un critère d'acceptation.
_TRANCHE_SIZE = 500


def _identity_key(scraped: ScrapedResult) -> tuple[str, str]:
    """Clé d'identité normalisée d'une ligne scrapée — même formule que
    `athlete_repository.get_by_identities_batch`, côté nom/prénom stockés
    (déjà `.strip()`-és en base), pour que les deux se retrouvent."""
    return (
        (scraped.athlete_name or "").strip().lower(),
        (scraped.athlete_firstname or "").strip().lower(),
    )


@dataclass(frozen=True)
class _PendingResolution:
    """Une ligne en attente de résolution d'athlète par lot (#706), mise en
    file plutôt que résolue immédiatement par `add()`.

    `participation` porte la ligne déjà appariée par dossard à réconcilier
    (chemin `_reconcile`) ; `None` pour une participation neuve à créer
    (chemin dossard neuf ou sans dossard — `bib` distingue les deux, `None`
    valant « sans dossard », pour rejouer `_match_without_bib`/les crédits
    une fois l'athlète connu).
    """
    scraped: ScrapedResult
    bib: str | None
    participation: Participation | None


class _Persister:
    """Persiste les résultats scrapés en **upsert**, avec déduplication.

    Point de persistance unique des trois entrées (rescrape-db, import-sheet, web
    SSE). Deux clés d'appariement, par course :
      - le dossard, quand il existe (`uq_participation_bib`) ;
      - sinon l'athlète, en **multiset** — mais la mise à jour ne s'applique que
        si l'athlète n'a qu'une seule participation sur la course (cf. `add`).

    Une ligne appariée est **fusionnée prudemment** (`_merge_fields`) : la source
    ne réécrit que ses valeurs non vides. `athlete_id` échappe à cette fusion —
    seule la **réconciliation d'identité** (`_reconcile`, sur le chemin dossard)
    le réassigne quand la graphie stockée a divergé de la graphie corrigée.
    """

    def __init__(self, db: Session, event_url: str):
        self.db = db
        self.event_url = event_url
        self._by_bib: dict[int, dict[str, Participation]] = {}
        self._added_bibs: dict[int, set[str]] = {}
        self._duplicate_bibs: Counter[int] = Counter()
        self._without_bib: dict[int, dict[int, list[Participation]]] = {}
        self._credits: dict[int, dict[int, int]] = {}
        self._updated_single: dict[int, set[int]] = {}
        self._courses: dict[int, Course] = {}
        # Cache de résolution de course par lot (#759) : sans lui, `add()`
        # rappelle `mapping.get_or_create_course` (3 requêtes DB minimum) à
        # chaque participation, même quand tout le lot appartient à la même
        # course — mesuré à ~7000 requêtes sur une course à 2396 participants.
        # Clé = les deux axes dont dépend la course résolue : la réconciliation
        # par URL (`provider`, `source_url`) et l'identité stricte
        # (`uq_course_identity` : nom, date, type, relais) — une seule URL peut
        # faire fan-out sur plusieurs heats au sein d'un même lot (#156), donc
        # `(provider, url)` seul collapserait des courses distinctes.
        self._course_resolutions: dict[tuple, mapping.CourseResolution] = {}
        # Résolution par lot (#706) : lignes en attente et participations
        # connues d'une course, par `course_id` — `_participations` remplace
        # le second `list_for_course` de `finalize()` (cf. `_index_course`).
        self._pending: dict[int, list[_PendingResolution]] = {}
        self._participations: dict[int, list[Participation]] = {}
        self.imported = 0
        self.updated = 0
        self.skipped = 0
        self.reconciled = 0
        self.reassignments: list[Reassignment] = []
        # Dédup par `id` de source, pas par ligne scrapée : `add` résout l'épreuve
        # une fois par participant, un classement de 250 lignes rendrait sinon
        # 250 fois la même phrase et ferait compter 250 sources pour une.
        self._passive: dict[int, PassiveSource] = {}

    @property
    def passive_sources(self) -> list[PassiveSource]:
        """Les sources passives rencontrées, dans l'ordre de première rencontre."""
        return list(self._passive.values())

    def courses_summary(self) -> list[dict]:
        """Résumé des courses touchées, dans l'ordre où elles ont été rencontrées
        (Python 3.7+ : ordre d'insertion du dict).

        Alimente le SSE `done` : le front en tire des liens « Voir les
        résultats » (#135). Ordre stable → boutons stables entre deux imports.
        """
        return [
            {
                "id": c.id, "name": c.name,
                "event_type": c.event_type, "is_relay": bool(c.is_relay),
            }
            for c in self._courses.values()
        ]

    def _index_course(self, course_id: int) -> None:
        """Charge et indexe une fois les participations de la course (une requête)."""
        if course_id in self._by_bib:
            return
        rows = participation_repository.list_for_course(self.db, course_id)
        by_bib: dict[str, Participation] = {}
        without: dict[int, list[Participation]] = {}
        for row in rows:
            if row.bib_number:
                by_bib[row.bib_number] = row
            else:
                without.setdefault(row.athlete_id, []).append(row)
        self._by_bib[course_id] = by_bib
        self._added_bibs[course_id] = set()
        self._without_bib[course_id] = without
        self._credits[course_id] = {aid: len(rs) for aid, rs in without.items()}
        self._updated_single[course_id] = set()
        # `finalize()` réutilise cette liste (#706) au lieu d'un second
        # `list_for_course` : les créations de ce scrape s'y ajoutent au fil de
        # `_resolve_pending`, les mises à jour mutent les objets déjà dedans.
        self._participations[course_id] = list(rows)

    def _upsert(self, existing: Participation, scraped: ScrapedResult) -> None:
        """Fusionne prudemment une ligne appariée. Compte `updated` ou `skipped`."""
        fields = mapping.participation_fields(
            scraped, athlete_id=existing.athlete_id, course_id=existing.course_id
        )
        changes = _merge_fields(existing, fields)
        status = _resolve_status(existing, scraped, changes)
        if status != existing.status:
            changes["status"] = status
        if changes:
            participation_repository.update(self.db, existing, **changes)
            self.updated += 1
        else:
            self.skipped += 1

    def _note_passive(self, course: Course, source: CourseSource) -> None:
        """Retient une source passive **une fois**, et rédige le message qui la nomme.

        Le message dit trois choses parce qu'il en faut trois pour être
        actionnable : l'épreuve qui a absorbé l'URL, la raison pour laquelle le
        classement affiché ne change pas, et qui peut décider l'inverse (#285).
        """
        if source.id in self._passive:
            return
        self._passive[source.id] = PassiveSource(
            url=source.url,
            course_name=course.name,
            message=(
                f"Cette URL est enregistrée comme source secondaire de "
                f"« {course.name} », dont les résultats affichés viennent d'un autre "
                f"chronométreur. Un administrateur peut la rendre principale."
            ),
        )

    def add(self, scraped: ScrapedResult) -> None:
        cache_key = (
            scraped.provider,
            scraped.source_url or self.event_url,
            scraped.event_name,
            scraped.event_date,
            scraped.event_type,
            scraped.is_relay,
        )
        resolution = self._course_resolutions.get(cache_key)
        if resolution is None:
            resolution = mapping.get_or_create_course(self.db, scraped, self.event_url)
            self._course_resolutions[cache_key] = resolution
        course = resolution.course
        if resolution.passive_source is not None:
            self._note_passive(course, resolution.passive_source)
        self._courses[course.id] = course
        self._index_course(course.id)
        bib = scraped.bib_number or None

        if bib is not None:
            added = self._added_bibs[course.id]
            if bib in added:
                # La source se contredit dans ce scrape : deux lignes, même
                # dossard. La 2e est perdue — anomalie de fiabilité.
                self.skipped += 1
                self._duplicate_bibs[course.id] += 1
                return
            existing = self._by_bib[course.id].get(bib)
            if existing is not None:
                added.add(bib)
                # Deux axes indépendants sur une ligne appariée : l'identité
                # (`athlete_id`, #66) puis les valeurs (#68). La réconciliation
                # ne touche jamais aux valeurs, `_upsert` jamais à `athlete_id` —
                # les deux se rejouent dans `_resolve_pending`, une fois
                # l'athlète connu (#706, résolution par lot).
                if self._reconcile_blocked(scraped, existing):
                    # « BERGE | LOLA » → « LOLA BERGE |  » : refusé *avant*
                    # toute résolution, sinon une identité `(nom, "")` neuve
                    # serait mise en attente et créerait une fiche orpheline
                    # que le chemin web/SSE ne nettoie jamais (#66) — la
                    # garde doit trancher ici, pas après coup dans le lot.
                    self._upsert(existing, scraped)
                else:
                    self._enqueue(course.id, scraped, bib=bib, participation=existing)
                return
            # Dossard neuf : réservé tout de suite, sinon deux lignes neuves
            # du même scrape avec le même dossard passeraient toutes les deux
            # ce test (la résolution est différée, `_by_bib` ne les connaît
            # pas encore) et heurteraient `uq_participation_bib` à la création.
            added.add(bib)

        self._enqueue(course.id, scraped, bib=bib, participation=None)

    def _enqueue(
        self, course_id: int, scraped: ScrapedResult, *, bib: str | None,
        participation: Participation | None,
    ) -> None:
        """Met une ligne en attente de résolution d'athlète (#706) au lieu de
        la résoudre immédiatement. Déclenche le lot dès que la tranche est
        pleine — le reliquat de chaque course se résout à `finalize()`."""
        pending = self._pending.setdefault(course_id, [])
        pending.append(_PendingResolution(scraped=scraped, bib=bib, participation=participation))
        if len(pending) >= _TRANCHE_SIZE:
            self._resolve_pending(course_id)

    def _resolve_pending(self, course_id: int) -> None:
        """Résout par lot toutes les lignes en attente d'une course (#706).

        Un seul aller-retour DB pour retrouver les athlètes déjà connus
        (`get_by_identities_batch`), un seul pour créer les manquants
        (`create_batch`, dédupliqué par identité — deux lignes du même scrape
        pour un même athlète neuf ne créent qu'une fiche), un seul pour les
        participations neuves. Rejoue ensuite, ligne par ligne mais sans
        requête, exactement la logique de `add`/`_reconcile` d'origine.
        """
        pending = self._pending.pop(course_id, [])
        if not pending:
            return

        pairs = [(item.scraped.athlete_name, item.scraped.athlete_firstname) for item in pending]
        found: dict[tuple[str, str], Athlete] = athlete_repository.get_by_identities_batch(
            self.db, pairs
        )

        to_create: dict[tuple[str, str], dict] = {}
        creation_order: list[tuple[str, str]] = []
        for item in pending:
            key = _identity_key(item.scraped)
            if key in found or key in to_create:
                continue
            to_create[key] = mapping.athlete_creation_fields(item.scraped)
            creation_order.append(key)
        if creation_order:
            created_athletes = athlete_repository.create_batch(
                self.db, [to_create[key] for key in creation_order]
            )
            found.update(zip(creation_order, created_athletes, strict=True))

        created_keys = set(to_create.keys())
        creation_consumed: set[tuple[str, str]] = set()
        new_participation_fields: list[dict] = []
        new_participation_items: list[_PendingResolution] = []

        for item in pending:
            key = _identity_key(item.scraped)
            athlete = found[key]
            club = item.scraped.club or None
            if club and athlete.club != club and not athlete.club_locked:
                # Même synchronisation que la branche « existant » de
                # `athlete_repository.resolve` — sans effet sur la ligne qui
                # vient de créer `athlete` (son club est déjà le sien).
                athlete.club = club

            is_creator = key in created_keys and key not in creation_consumed
            if is_creator:
                creation_consumed.add(key)

            if item.participation is not None:
                self._reconcile_resolved(
                    item.scraped, item.participation, athlete, cree=is_creator
                )
                self._upsert(item.participation, item.scraped)
                continue

            if item.bib is None:
                existing = self._match_without_bib(course_id, athlete.id)
                if existing is not None:
                    self._upsert(existing, item.scraped)
                    continue
                if self._credits[course_id].get(athlete.id, 0) > 0:
                    self._credits[course_id][athlete.id] -= 1
                    self.skipped += 1
                    continue

            new_participation_fields.append(
                mapping.participation_fields(
                    item.scraped, athlete_id=athlete.id, course_id=course_id
                )
            )
            new_participation_items.append(item)

        if new_participation_fields:
            created_participations = participation_repository.create_batch(
                self.db, new_participation_fields
            )
            self._participations[course_id].extend(created_participations)
            for item, participation in zip(
                new_participation_items, created_participations, strict=True
            ):
                # `_added_bibs` est déjà à jour depuis `add` (réservé dès
                # l'enfilement, cf. commentaire associé) — seul `_by_bib` a
                # besoin de l'objet créé, indisponible avant la création.
                if item.bib is not None:
                    self._by_bib[course_id][item.bib] = participation
                self.imported += 1

    def _reconcile_blocked(self, scraped: ScrapedResult, participation: Participation) -> bool:
        """Vrai si la réconciliation de cette ligne doit être refusée sans
        même résoudre d'athlète — jamais une correction qui viderait le
        prénom : « BERGE | LOLA » → « LOLA BERGE |  » créerait une identité
        `(nom, "")` neuve, orpheline, que le chemin web/SSE ne nettoie jamais
        (#66). Vérifié à l'enfilement (`add`), avant toute mise en attente de
        résolution — trancher après coup, une fois l'identité déjà mise en
        lot, serait trop tard pour éviter la création."""
        ancien = participation.athlete
        return not (scraped.athlete_firstname or "").strip() and (ancien.prenom or "").strip()

    def _reconcile_resolved(
        self, scraped: ScrapedResult, participation: Participation, athlete: Athlete,
        *, cree: bool,
    ) -> None:
        """Réassigne l'athlète d'une participation existante si sa graphie a
        divergé. `athlete`/`cree` sont déjà connus (résolus par lot dans
        `_resolve_pending`, `_reconcile_blocked` déjà écarté à l'enfilement) —
        c'est la seule différence avec l'ancien `_reconcile`, qui résolvait
        lui-même l'athlète par une requête. Ne touche QUE `athlete_id` (via la
        relation, pour un déplacement propre entre fiches sans déclencher le
        cascade delete-orphan) : les valeurs de la ligne relèvent d'`_upsert`,
        appelé juste après. Compte « réconciliée » quand l'athlète change —
        jamais `skipped`, qui reste l'affaire d'`_upsert` pour ne pas compter
        deux fois la même ligne.
        """
        if athlete.id == participation.athlete_id:
            return
        reassignment = Reassignment(
            ancien=_identite(participation.athlete), nouveau=_identite(athlete), fusion=not cree
        )
        participation.athlete = athlete
        self.reconciled += 1
        self.reassignments.append(reassignment)

    def _match_without_bib(self, course_id: int, athlete_id: int) -> Participation | None:
        """Ligne sans dossard à mettre à jour : seulement si l'athlète n'a qu'**une**
        participation sur la course, et pas déjà mise à jour dans ce scrape.

        Deux occurrences ou plus : on ne devine pas quelle ligne source correspond
        à quelle ligne en base, on conserve le skip multiset (cf. `add`).
        """
        rows = self._without_bib[course_id].get(athlete_id, [])
        if len(rows) != 1 or athlete_id in self._updated_single[course_id]:
            return None
        self._updated_single[course_id].add(athlete_id)
        self._credits[course_id][athlete_id] -= 1
        return rows[0]

    def finalize(self) -> None:
        # Reliquat de chaque course : ce qui n'a pas atteint une pleine
        # tranche pendant `add` se résout ici (#706).
        for course_id in list(self._pending.keys()):
            self._resolve_pending(course_id)
        for course_id, course in self._courses.items():
            course_repository.touch_scraped_at(self.db, course)
            # Réutilise la liste déjà chargée par `_index_course` (#706) —
            # tenue à jour par `_resolve_pending` — au lieu d'un second
            # `list_for_course`. `list_for_course` n'applique pas
            # `validated_clause` (#270) — c'est le chemin d'import, pas
            # d'affichage — donc filtrée ici pour les deux compteurs
            # dénormalisés (#623), sur la même définition que
            # `_apply_filters`/`validated_clause`.
            rows = self._participations[course_id]
            report = quality.analyze(rows, duplicate_bibs=self._duplicate_bibs[course_id])
            course_repository.set_quality(
                self.db,
                course,
                is_reliable_computed=report.is_reliable,
                quality_issues=report.anomalies,
            )
            validees = [row for row in rows if not row.is_pending_validation]
            course_repository.set_counts(
                self.db,
                course,
                participation_count=len(validees),
                tcn_count=sum(1 for row in validees if is_tcn(row.club)),
            )


def _cached_result(db: Session, url: str, settings: Settings) -> dict | None:
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
        "courses": [
            {
                "id": c.id, "name": c.name,
                "event_type": c.event_type, "is_relay": bool(c.is_relay),
            }
            for c in heats
        ],
    }


def _reclassify_heats(db: Session, event_url: str, results: list[ScrapedResult]) -> None:
    """Aligne la classification des épreuves déjà en base sur ce scrape-ci (#294).

    Le verdict de `classify_event_type` bouge d'un scrape à l'autre — heuristique
    affinée, contexte de nom différent. L'identité étant
    `(name, event_date, event_type, is_relay)`, l'épreuve ne se retrouvait plus :
    une **seconde** `Course` naissait, et la première gardait ses résultats sous
    un sport devenu faux, indiscernable de la neuve à l'écran (Mesquer 2026, 498
    finishers classés swimrun alors que c'était un triathlon).

    **Un rattrapage de lot, et pas de ligne**, parce que le signal qui distingue
    une reclassification d'un second heat n'existe qu'au niveau du lot : une même
    URL publie légitimement N épreuves du **même nom**, à la **même date**, que
    seuls `event_type` et `is_relay` séparent — les six heats TimePulse sous
    `/epreuves/resultats/live/3232` (mesuré, cf.
    `services/course_duplicates._same_source_url`). Ligne à ligne, le second heat
    est indistinguable d'un premier heat reclassé, et le rattraper reviendrait à
    fondre deux classements réels en un. Le lot, lui, tranche : si ce scrape ne
    publie **qu'une** classification pour une clé, il n'y a pas deux heats à
    confondre.

    Rien n'est écrit quand l'URL scrapée n'est pas la source **active** de
    l'épreuve : c'est D2 (#303), la source active fait foi sur le nom, la date, et
    donc aussi sur le sport. Une passive n'alimente aucun affichage, elle ne
    classe rien.

    Le coût est d'**une lecture indexée par heat** sur le chemin nominal — celui
    où l'identité n'a pas bougé, et où il n'y a donc rien à reclasser. La jointure
    sur `course_sources` n'est payée que quand elle a bougé, c'est-à-dire presque
    jamais.
    """
    classifications: dict[tuple[str, str, object, bool], set[str]] = {}
    for scraped in results:
        # Même priorité que `mapping.get_or_create_course` : le fan-out Klikego
        # (#156) donne à chaque heat sa propre URL, et c'est elle qui porte la
        # source active de l'épreuve, pas l'URL d'événement soumise.
        url = scraped.source_url or event_url
        if not url:
            continue
        cle = (url, scraped.event_name, scraped.event_date, bool(scraped.is_relay))
        classifications.setdefault(cle, set()).add(scraped.event_type)

    for (url, name, event_date, is_relay), types in classifications.items():
        if len(types) != 1:
            continue
        event_type = next(iter(types))
        if course_repository.get_by_identity(db, name, event_date, event_type, is_relay):
            # L'identité visée est déjà en base : ou bien c'est l'épreuve elle-même
            # et rien n'a bougé, ou bien c'en est une autre et `uq_course_identity`
            # interdirait l'écriture de toute façon.
            continue
        course = course_repository.get_by_active_source(
            db, source_url=url, name=name, event_date=event_date, is_relay=is_relay
        )
        if course is not None:
            course_repository.reclassify(db, course, event_type)


def _renumber_relay_split_ranks(results: list[ScrapedResult]) -> None:
    """Renumérote `rank_overall` en 1..N quand la scission par `is_relay` a lieu (#672).

    L'identité `Course` (`name, event_date, event_type, is_relay`) scinde en
    deux épreuves une source qui n'en publie qu'une (solo + relais/duo mêlés
    dans un même « heat »). Le `rank_overall` scrapé porte alors le rang dans
    le **champ combiné** de la source — inchangé après la scission, le petit
    lot hérite d'un rang très écarté (ex. 597 pour 3 relayeurs), ce qui casse
    l'hypothèse de `services/quality.py::_rank_anomalies` (classement local
    1..N sans trou, cf. `ANOMALY_RANK_GAP`) et affiche un « trou » de
    centaines de rangs sur une fiche de 1 à 16 participants — déroutant côté
    site. Constaté sur ProLiveSport et Chronoplace, deux scrapers sans code
    partagé : la cause commune est l'identité `Course`, pas un fournisseur.

    Renuméroté ici, au point précis où le lot scrapé se répartit par
    `is_relay` — pas dans les scrapers, puisque le bug ne dépend d'aucun
    d'eux. Ne touche que les groupes réellement scindés dans **ce** lot (plus
    d'une valeur `is_relay` pour un même `(event_name, event_date,
    event_type)`) : une épreuve dont la source publie déjà un classement
    local par heat n'est pas concernée, et y toucher serait sans effet — tri
    stable sur le rang d'origine, donc déjà 1..N ne change pas.
    """
    groups: dict[tuple[str, object, str], dict[bool, list[ScrapedResult]]] = {}
    for scraped in results:
        key = (scraped.event_name, scraped.event_date, scraped.event_type)
        groups.setdefault(key, {}).setdefault(bool(scraped.is_relay), []).append(scraped)

    for by_relay in groups.values():
        if len(by_relay) < 2:
            continue  # pas de scission is_relay pour cette épreuve dans ce lot
        for subgroup in by_relay.values():
            ranked = sorted(
                (r for r in subgroup if r.rank_overall is not None),
                key=lambda r: r.rank_overall,
            )
            for local_rank, scraped in enumerate(ranked, start=1):
                scraped.rank_overall = local_rank


def persist_results(db: Session, url: str, results: list[ScrapedResult]) -> dict:
    """Écrit des résultats déjà scrapés. **Ne clôt pas la transaction.**

    Le cœur d'`import_event`, extrait pour qu'un appelant qui gère lui-même sa
    transaction puisse l'utiliser (#285) : ni `commit`, ni `rollback`, ni
    `try/except` — l'appelant a des écritures à lui dans la même transaction, et
    c'est à lui de la clore, sur le patron « le service `flush`, la route
    `commit` » du reste du dépôt.

    `courses` est le résumé **brut** du persister : le repli sur les heats
    cachés (`_merge_cached_courses`) appartient au compte rendu d'import, pas à
    l'écriture.
    """
    _reclassify_heats(db, url, results)
    _renumber_relay_split_ranks(results)
    persister = _Persister(db, url)
    for scraped in results:
        persister.add(scraped)
    persister.finalize()
    return {
        "imported": persister.imported,
        "updated": persister.updated,
        "skipped": persister.skipped,
        "reconciled": persister.reconciled,
        "passive_sources": persister.passive_sources,
        "courses": persister.courses_summary(),
    }


def import_event(
    db: Session, url: str, settings: Settings, force: bool = False, persist: bool = True,
    *, single_heat: bool = False,
) -> dict:
    """Import complet (bloquant). Renvoie {imported, updated, skipped, reconciled, [cached]}.

    Contrat stable : `updated`, `reconciled` et `passive_sources` (et `cached` à
    sa valeur par défaut) sont présents sur **tous** les chemins de retour — cache
    TTL frais et « aucun résultat » compris — pour éviter à l'appelant un accès
    conditionnel. `passive_sources` reste hors du schéma public `ImportResult`,
    même parti pris que `reconciled` : le front consomme le SSE.

    force=True saute le cache TTL (`_cached_result`) → le scraping a toujours lieu.
    persist=False traverse tout le chemin de persistance (scrape, add, finalize)
    puis annule la transaction (dry-run) : rien n'est écrit.
    """
    url = _validate_url(url)

    if not force:
        cached = _cached_result(db, url, settings)
        if cached is not None:
            return {**cached, **_fanout_counters(None)}

    results, trace = _scrape_all(url, db, settings, single_heat=single_heat)
    if not results:
        return {
            "imported": 0, "updated": 0, "skipped": 0, "reconciled": 0,
            "passive_sources": [],
            "courses": _merge_cached_courses(db, [], trace),
            **_fanout_counters(trace),
        }

    try:
        outcome = persist_results(db, url, results)
        if persist:
            db.commit()
        else:
            db.rollback()  # dry-run : traverser la persistance, ne rien écrire
    except Exception:
        db.rollback()
        logger.exception("Rollback de l'import %s", url)
        raise ScraperError("Erreur lors de l'enregistrement des résultats.") from None

    return {
        **outcome,
        "courses": _merge_cached_courses(db, outcome["courses"], trace),
        **_fanout_counters(trace),
    }


def _confirm_committed(db: Session, courses: list[dict], since: datetime) -> bool:
    """Distingue un rollback réel d'un accusé de `commit()` perdu (#704).

    Un `db.rollback()` après un `COMMIT` qui a abouti côté serveur est sans
    effet : les données restent écrites. Re-vérifier en base — plutôt que se
    fier à l'exception seule — sépare ce cas de celui d'un commit qui a
    vraiment échoué, où `scraped_at` n'a jamais bougé.
    """
    if not courses:
        return False
    for c in courses:
        course = course_repository.get(db, c["id"])
        if course is None or course.scraped_at is None or course.scraped_at < since:
            return False
    return True


def iter_import_event(
    db: Session, url: str, settings: Settings, force: bool = False, persist: bool = True,
    *, single_heat: bool = False,
) -> Iterator[dict]:
    """
    Générateur de progression pour le SSE. Émet des dicts de phase :
      {phase: scraping} → {phase: saving, progress, total, imported, updated, skipped}
      → {phase: done, …}   (ou {phase: error, message})

    La phase `done` porte un contrat stable — `imported`, `updated`, `skipped`,
    `reconciled`, `reassignments`, `passive_sources`, `total`, `courses` — sur
    **tous** les chemins, y
    compris les court-circuits (cache TTL frais, aucun résultat), pour que le
    consommateur SSE / batch n'ait aucun champ conditionnel à gérer. `courses`
    reste **vide** si aucun résultat n'a été scrapé (aucune `Course` touchée).

    force=True saute le cache TTL (`_cached_result`).
    persist=False traverse tout le chemin de persistance (scrape, add, finalize)
    puis annule la transaction (dry-run) : rien n'est écrit.

    Pas de `use_cache_probe` ici : #118 (re-scrape admin) appelle
    `_scrape_all_streaming` **directement**, pas ce générateur — l'ajouter ici
    aurait été un paramètre sans appelant (revue de code, retiré).
    """
    try:
        url = _validate_url(url)
    except InvalidUrlError as exc:
        yield {"phase": "error", "message": exc.message}
        return

    if not force:
        cached = _cached_result(db, url, settings)
        if cached is not None:
            yield {
                "phase": "done", "total": cached["skipped"], "reassignments": [],
                **cached, **_fanout_counters(None),
            }
            return

    yield {"phase": "scraping", "message": "Récupération des participants…"}
    try:
        # Un seul chemin, fan-out comme mono-heat : `yield from` relaie les
        # événements intermédiaires et récupère `(results, trace)` en fin de
        # générateur. L'ancienne branche mono-heat appelait `_scrape_all`
        # directement et laissait donc le flux **muet** pendant tout le scrape,
        # y compris sur un heat Klikego de 250 finishers (revue finale #698).
        results, trace = yield from _scrape_all_streaming(
            url, db, settings, single_heat=single_heat,
        )
    except (ProviderNotSupportedError, ScraperError) as exc:
        yield {"phase": "error", "message": exc.message}
        return

    total = len(results)
    if total == 0:
        yield {
            "phase": "done",
            "imported": 0,
            "updated": 0,
            "skipped": 0,
            "reconciled": 0,
            "reassignments": [],
            "passive_sources": [],
            "total": 0,
            "courses": _merge_cached_courses(db, [], trace),
            **_fanout_counters(trace),
        }
        return

    persister = _Persister(db, url)
    yield {"phase": "saving", "total": total, "imported": 0, "updated": 0, "skipped": 0, "progress": 0}
    attempt_started_at = utcnow()
    try:
        # Le chemin SSE ré-implémente la boucle de `persist_results` pour émettre
        # sa progression : le rattrapage de classification (#294) et la
        # renumérotation solo/relais (#672) doivent donc y être posés eux
        # aussi, et **avant** la première ligne, sinon la seconde `Course`
        # est déjà née — ou déjà écrite avec son rang combiné — quand on la
        # cherche.
        _reclassify_heats(db, url, results)
        _renumber_relay_split_ranks(results)
        for i, scraped in enumerate(results):
            persister.add(scraped)
            if (i + 1) % 20 == 0 or i == total - 1:
                yield {
                    "phase": "saving",
                    "total": total,
                    "imported": persister.imported,
                    "updated": persister.updated,
                    "skipped": persister.skipped,
                    "progress": i + 1,
                }
        persister.finalize()
        if persist:
            db.commit()
        else:
            db.rollback()  # dry-run : traverser la persistance, ne rien écrire
    except Exception as exc:
        db.rollback()
        confirmed = False
        if persist:
            try:
                confirmed = _confirm_committed(db, persister.courses_summary(), attempt_started_at)
            except Exception:
                # La re-vérification elle-même peut échouer (connexion vraiment
                # perdue, pas seulement un accusé égaré) : on ne laisse jamais
                # cette panne secondaire faire disparaître la phase `error` que
                # le flux SSE doit toujours émettre.
                logger.exception("Échec de la re-vérification post-commit pour %s", url)
        if not confirmed:
            logger.error("Rollback de l'import streaming %s", url, exc_info=exc)
            yield {"phase": "error", "message": "Erreur lors de l'enregistrement des résultats."}
            return
        logger.warning(
            "Accusé de commit perdu mais écriture confirmée en base pour %s", url, exc_info=exc
        )

    yield {
        "phase": "done",
        "imported": persister.imported,
        "updated": persister.updated,
        "skipped": persister.skipped,
        "reconciled": persister.reconciled,
        "reassignments": persister.reassignments,
        "passive_sources": persister.passive_sources,
        "total": total,
        "courses": _merge_cached_courses(db, persister.courses_summary(), trace),
        **_fanout_counters(trace),
    }
