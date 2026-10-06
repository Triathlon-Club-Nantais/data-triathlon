"""Orchestration de l'import d'une épreuve entière (#1186).

`import_event` (bloquant) et `iter_import_event` (générateur SSE) enchaînent le
cache TTL et le scrape (`import_dispatch`), le verrou d'URL (#1024), puis la
persistance (`import_persistence`) dans une transaction qu'ils commitent ou
annulent, avec reprise sur deadlock.
"""
import logging
from collections.abc import Iterator
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import InvalidUrlError, ProviderNotSupportedError, ScraperError
from app.core.time import utcnow
from app.repositories import (
    course_repository,
    lock_repository,
)
from app.services import import_dispatch, import_persistence
from app.services.deadlock import deadlock_retries

logger = logging.getLogger(__name__)


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

    force=True saute le cache TTL (`import_dispatch.cached_result`) **et** `cache_probe` (#810) :
    le fan-out (Klikego, Wiclax, RaceResult…) sauterait sinon en silence tout
    heat scrapé il y a moins de 30 j, malgré le rescrape explicitement demandé.
    persist=False traverse tout le chemin de persistance (scrape, add, finalize)
    puis annule la transaction (dry-run) : rien n'est écrit.
    """
    url = import_dispatch.validate_url(url)

    if not force:
        cached = import_dispatch.cached_result(db, url, settings)
        if cached is not None:
            return {**cached, **import_dispatch.fanout_counters(None)}
        # Relâche la lecture du cache : le scrape peut durer des minutes (#1015).
        db.rollback()

    results, trace = import_dispatch.scrape_all(
        url, db, settings, single_heat=single_heat, use_cache_probe=not force,
    )
    if not results:
        return {
            "imported": 0, "updated": 0, "skipped": 0, "reconciled": 0,
            "passive_sources": [], "ambiguous_identities": [], "homonyms_created": [],
            "courses": import_dispatch.merge_cached_courses(db, [], trace),
            **import_dispatch.fanout_counters(trace),
        }

    try:
        for attempt in deadlock_retries(db, label=url):
            with attempt:
                cached = _lock_url_and_recheck_cache(db, url, settings, force=force)
                if cached is not None:
                    db.rollback()
                    return {**cached, **import_dispatch.fanout_counters(trace)}
                outcome = import_persistence.persist_results(db, url, results)
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
        "courses": import_dispatch.merge_cached_courses(db, outcome["courses"], trace),
        **import_dispatch.fanout_counters(trace),
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


def _lock_url_and_recheck_cache(
    db: Session, url: str, settings: Settings, *, force: bool
) -> dict | None:
    """Sérialise les imports d'une même URL, entre processus (#1024).

    Rien ne les sérialisait : un import public (SSE) et `rescrape-db` (GitHub
    Actions) pouvaient écrire la même épreuve en même temps, en doublons ou en
    phase `error`. Le verrou consultatif est pris au début de la transaction de
    persistance, puis le cache TTL est **relu sous le verrou** : l'import qui
    attendait voit le commit de celui qui le précédait, et rend son résultat au
    lieu de réécrire. `force=True` ne relit pas : il demande de réécrire.

    La clé est l'URL **soumise**, même pour un fan-out (Klikego, #156) : deux
    imports du même événement s'excluent, ce qui est le cas mesuré.
    """
    lock_repository.lock_import_url(db, url)
    if force:
        return None
    return import_dispatch.cached_result(db, url, settings)


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

    force=True saute le cache TTL (`import_dispatch.cached_result`) **et** `cache_probe` (#810) :
    `rescrape-db` (`batch.run_batch` → ce générateur) attend d'un rescrape forcé
    qu'il retraite vraiment un heat fan-out scrapé il y a moins de 30 j, pas
    qu'il le saute en silence.
    persist=False traverse tout le chemin de persistance (scrape, add, finalize)
    puis annule la transaction (dry-run) : rien n'est écrit.
    """
    try:
        url = import_dispatch.validate_url(url)
    except InvalidUrlError as exc:
        yield {"phase": "error", "message": exc.message}
        return

    if not force:
        cached = import_dispatch.cached_result(db, url, settings)
        if cached is not None:
            yield {
                "phase": "done", "total": cached["skipped"], "reassignments": [],
                **cached, **import_dispatch.fanout_counters(None),
            }
            return
        # Relâche la lecture du cache : le scrape peut durer des minutes (#1015).
        db.rollback()

    yield {"phase": "scraping", "message": "Récupération des participants…"}
    try:
        # Un seul chemin, fan-out comme mono-heat : `yield from` relaie les
        # événements intermédiaires et récupère `(results, trace)` en fin de
        # générateur. L'ancienne branche mono-heat appelait `import_dispatch.scrape_all`
        # directement et laissait donc le flux **muet** pendant tout le scrape,
        # y compris sur un heat Klikego de 250 finishers (revue finale #698).
        results, trace = yield from import_dispatch.scrape_all_streaming(
            url, db, settings, single_heat=single_heat, use_cache_probe=not force,
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
            "ambiguous_identities": [], "homonyms_created": [],
            "total": 0,
            "courses": import_dispatch.merge_cached_courses(db, [], trace),
            **import_dispatch.fanout_counters(trace),
        }
        return

    attempt_started_at = utcnow()
    persister = None
    try:
        for attempt in deadlock_retries(db, label=url):
            with attempt:
                persister = None
                yield {"phase": "saving", "total": total, "imported": 0, "updated": 0, "skipped": 0, "progress": 0}
                cached = _lock_url_and_recheck_cache(db, url, settings, force=force)
                if cached is not None:
                    db.rollback()
                    yield {
                        "phase": "done", "total": cached["skipped"], "reassignments": [],
                        **cached, **import_dispatch.fanout_counters(trace),
                    }
                    return
                for done, persister in import_persistence.persist_steps(db, url, results):
                    if done and (done % 20 == 0 or done == total):
                        yield {
                            "phase": "saving",
                            "total": total,
                            "imported": persister.imported,
                            "updated": persister.updated,
                            "skipped": persister.skipped,
                            "progress": done,
                        }
                if persist:
                    db.commit()
                else:
                    db.rollback()  # dry-run : traverser la persistance, ne rien écrire
    except Exception as exc:
        db.rollback()
        confirmed = False
        if persist:
            try:
                confirmed = persister is not None and _confirm_committed(
                    db, persister.courses_summary(), attempt_started_at
                )
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
        "challenges": persister.challenges,
        "reassignments": persister.reassignments,
        "passive_sources": persister.passive_sources,
        "ambiguous_identities": persister.ambiguous_identities,
        "homonyms_created": persister.homonyms_created,
        "total": total,
        "courses": import_dispatch.merge_cached_courses(db, persister.courses_summary(), trace),
        **import_dispatch.fanout_counters(trace),
    }
