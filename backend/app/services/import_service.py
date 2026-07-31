"""
Service d'import en masse d'une épreuve (tous les participants).

Inclut le cache TTL (court-circuite le re-scraping si la course est fraîche),
la déduplication par (course, dossard), un rollback explicite en cas d'erreur,
le calcul de l'indice de fiabilité de chaque course touchée (`services/quality.py`),
et un générateur de progression pour le streaming SSE.
"""
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import InvalidUrlError, ProviderNotSupportedError, ScraperError
from app.models.course import Course
from app.models.participation import Participation
from app.repositories import course_repository, participation_repository
from app.scrapers import registry
from app.scrapers import scrape_event_all as registry_scrape_event_all
from app.scrapers.base import STATUS_DNF, STATUS_FINISHER, ScrapedResult
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
) -> tuple[list[ScrapedResult], "registry.klikego.FanoutTrace | None"]:
    """Scrape l'URL et remonte optionnellement la `FanoutTrace` du provider.

    Passe par le dispatcher `registry.scrape_event_all(url, **kwargs)` — les
    kwargs sont propagés au provider matché (Klikego reçoit `cache_probe`, les
    autres l'ignorent via `**kwargs` du dispatcher). Après l'appel, lit
    `KlikegoProvider.last_trace` pour peupler les 5 compteurs de FR-008.

    Retour : `(results, trace)`. `trace` peut être `None` pour un provider qui
    n'expose pas de trace (comportement mono-heat implicite — `_fanout_counters`
    rend alors les 5 clés à 0/[]).
    """
    from app.scrapers import klikego  # circular-safe import

    cache_probe = _make_cache_probe(db, settings)
    provider = registry.get_provider(url)

    try:
        if isinstance(provider, registry.KlikegoProvider):
            if single_heat:
                # Échappatoire (--single-heat) : pas de fan-out, pas de cache_probe.
                # Le provider lit le ?heat= de l'URL et scrape ce seul heat.
                results = registry_scrape_event_all(url, single_heat=True)
            else:
                results = registry_scrape_event_all(url, cache_probe=cache_probe)
            trace = provider.last_trace
        else:
            # Autres providers + fallback Playwright — pas de trace de fan-out.
            # Trace synthétique 1-heat pour maintenir l'invariant `enumerated = imported`.
            results = registry_scrape_event_all(url)
            trace = klikego.FanoutTrace(heats_enumerated=1)
    except ValueError as exc:  # provider non supporté pour l'import en masse
        raise ProviderNotSupportedError(str(exc)) from exc
    except Exception as exc:
        logger.warning("Échec import %s : %s", url, exc)
        raise ScraperError(f"Erreur lors de l'import : {exc}") from exc

    _require_event_name(url, results)
    return results, trace


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
#: séparé, traité par `_Persister._reconcile`, pas par ce rafraîchissement de
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
        self._duplicate_bibs: dict[int, int] = {}
        self._without_bib: dict[int, dict[int, list[Participation]]] = {}
        self._credits: dict[int, dict[int, int]] = {}
        self._updated_single: dict[int, set[int]] = {}
        self._courses: dict[int, Course] = {}
        self.imported = 0
        self.updated = 0
        self.skipped = 0
        self.reconciled = 0
        self.reassignments: list[Reassignment] = []

    def courses_summary(self) -> list[dict]:
        """Résumé des courses touchées, dans l'ordre où elles ont été rencontrées
        (Python 3.7+ : ordre d'insertion du dict).

        Alimente le SSE `done` : le front en tire des liens « Voir les
        résultats » (#135). Ordre stable → boutons stables entre deux imports.
        """
        return [
            {"id": c.id, "name": c.name, "event_type": c.event_type}
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

    def add(self, scraped: ScrapedResult) -> None:
        course = mapping.get_or_create_course(self.db, scraped, self.event_url)
        self._courses[course.id] = course
        self._index_course(course.id)
        bib = scraped.bib_number or None

        if bib is not None:
            added = self._added_bibs[course.id]
            if bib in added:
                # La source se contredit dans ce scrape : deux lignes, même
                # dossard. La 2e est perdue — anomalie de fiabilité.
                self.skipped += 1
                self._duplicate_bibs[course.id] = self._duplicate_bibs.get(course.id, 0) + 1
                return
            existing = self._by_bib[course.id].get(bib)
            if existing is not None:
                added.add(bib)
                # Deux axes indépendants sur une ligne appariée : l'identité
                # (`athlete_id`, #66) puis les valeurs (#68). `_reconcile` ne
                # touche jamais aux valeurs, `_upsert` jamais à `athlete_id`.
                self._reconcile(scraped, existing)
                self._upsert(existing, scraped)
                return
            # Dossard neuf : on tombe sur la création commune plus bas.

        athlete = mapping.get_or_create_athlete(self.db, scraped)

        if bib is None:
            existing = self._match_without_bib(course.id, athlete.id)
            if existing is not None:
                self._upsert(existing, scraped)
                return
            if self._credits[course.id].get(athlete.id, 0) > 0:
                self._credits[course.id][athlete.id] -= 1
                self.skipped += 1
                return

        created = participation_repository.create(
            self.db,
            **mapping.participation_fields(
                scraped, athlete_id=athlete.id, course_id=course.id
            ),
        )
        if bib is not None:
            self._added_bibs[course.id].add(bib)
            self._by_bib[course.id][bib] = created
        self.imported += 1

    def _reconcile(self, scraped: ScrapedResult, participation: Participation) -> None:
        """Réassigne l'athlète d'une participation existante si sa graphie a divergé.

        Ne touche QUE `athlete_id` (via la relation, pour un déplacement propre
        entre fiches sans déclencher le cascade delete-orphan) : les valeurs de la
        ligne relèvent d'`_upsert`, appelé juste après. Compte « réconciliée »
        quand l'athlète change — jamais `skipped`, qui reste l'affaire d'`_upsert`
        pour ne pas compter deux fois la même ligne. Garde des ambigus : jamais
        une correction qui viderait le prénom.
        """
        ancien = participation.athlete
        if not (scraped.athlete_firstname or "").strip() and (ancien.prenom or "").strip():
            # « BERGE | LOLA » → « LOLA BERGE |  » : refusé *avant* de résoudre
            # l'athlète corrigé, sinon `resolve` créait une fiche orpheline que
            # le chemin web/SSE commite sans jamais la nettoyer (cf. #66).
            return
        athlete, cree = mapping.resolve_athlete(self.db, scraped)
        if athlete.id == participation.athlete_id:
            return
        reassignment = Reassignment(
            ancien=_identite(ancien), nouveau=_identite(athlete), fusion=not cree
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
        for course_id, course in self._courses.items():
            course_repository.touch_scraped_at(self.db, course)
            report = quality.analyze(
                participation_repository.list_for_course(self.db, course_id),
                duplicate_bibs=self._duplicate_bibs.get(course_id, 0),
            )
            course_repository.set_quality(
                self.db,
                course,
                is_reliable=report.is_reliable,
                quality_issues=report.anomalies,
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
        "courses": [
            {"id": c.id, "name": c.name, "event_type": c.event_type} for c in heats
        ],
    }


def import_event(
    db: Session, url: str, settings: Settings, force: bool = False, persist: bool = True,
    *, single_heat: bool = False,
) -> dict:
    """Import complet (bloquant). Renvoie {imported, updated, skipped, reconciled, [cached]}.

    Contrat stable : `updated` et `reconciled` (et `cached` à sa valeur par
    défaut) sont présents sur **tous** les chemins de retour — cache TTL frais et
    « aucun résultat » compris — pour éviter à l'appelant un accès conditionnel.

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
            "imported": 0, "updated": 0, "skipped": 0, "reconciled": 0, "courses": [],
            **_fanout_counters(trace),
        }

    persister = _Persister(db, url)
    try:
        for scraped in results:
            persister.add(scraped)
        persister.finalize()
        if persist:
            db.commit()
        else:
            db.rollback()  # dry-run : traverser la persistance, ne rien écrire
    except Exception:
        db.rollback()
        logger.exception("Rollback de l'import %s", url)
        raise ScraperError("Erreur lors de l'enregistrement des résultats.") from None

    return {
        "imported": persister.imported,
        "updated": persister.updated,
        "skipped": persister.skipped,
        "reconciled": persister.reconciled,
        "courses": persister.courses_summary(),
        **_fanout_counters(trace),
    }


def iter_import_event(
    db: Session, url: str, settings: Settings, force: bool = False, persist: bool = True,
    *, single_heat: bool = False,
) -> Iterator[dict]:
    """
    Générateur de progression pour le SSE. Émet des dicts de phase :
      {phase: scraping} → {phase: saving, progress, total, imported, updated, skipped}
      → {phase: done, …}   (ou {phase: error, message})

    La phase `done` porte un contrat stable — `imported`, `updated`, `skipped`,
    `reconciled`, `reassignments`, `total`, `courses` — sur **tous** les chemins, y
    compris les court-circuits (cache TTL frais, aucun résultat), pour que le
    consommateur SSE / batch n'ait aucun champ conditionnel à gérer. `courses`
    reste **vide** si aucun résultat n'a été scrapé (aucune `Course` touchée).

    force=True saute le cache TTL (`_cached_result`).
    persist=False traverse tout le chemin de persistance (scrape, add, finalize)
    puis annule la transaction (dry-run) : rien n'est écrit.
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
        results, trace = _scrape_all(url, db, settings, single_heat=single_heat)
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
            "total": 0,
            "courses": [],
            **_fanout_counters(trace),
        }
        return

    persister = _Persister(db, url)
    yield {"phase": "saving", "total": total, "imported": 0, "updated": 0, "skipped": 0, "progress": 0}
    try:
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
    except Exception:
        db.rollback()
        logger.exception("Rollback de l'import streaming %s", url)
        yield {"phase": "error", "message": "Erreur lors de l'enregistrement des résultats."}
        return

    yield {
        "phase": "done",
        "imported": persister.imported,
        "updated": persister.updated,
        "skipped": persister.skipped,
        "reconciled": persister.reconciled,
        "reassignments": persister.reassignments,
        "total": total,
        "courses": persister.courses_summary(),
        **_fanout_counters(trace),
    }
