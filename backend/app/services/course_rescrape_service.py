"""Re-scrape d'une épreuve et bascule de sa source, depuis le back-office (#118, #285, #1186).

Deux gestes SSE qui réécrivent une épreuve depuis sa source : la garde (404,
409 par `course_locks`) est synchrone, puis un thread de travail
(`sse_relay.relay`) scrape par `import_dispatch` et persiste par
`import_persistence`. La suppression d'une source inactive (#739) vit ici avec
eux. Le verrou d'épreuve est en base (`lock_courses_or_409`).
"""
import logging
from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import DomainError, NotFoundError, ScraperError
from app.repositories import (
    admin_action_log_repository,
    athlete_repository,
    course_repository,
    course_source_repository,
    participation_repository,
)
from app.schemas.course import CourseSourceOut
from app.services import (
    admin_actions,
    import_dispatch,
    import_persistence,
    sse_relay,
)
from app.services.course_locks import lock_courses_or_409
from app.services.deadlock import deadlock_retries

logger = logging.getLogger(__name__)


def _source_dicts(db: Session, course_id: int) -> list[dict]:
    """La liste des sources d'une épreuve, dans la forme exacte de
    `GET /courses/{id}/sources` (#284) — même schéma que la route consomme,
    pour que l'écran (#291) se réaffiche sans second appel ni forme parallèle."""
    return [
        CourseSourceOut.model_validate(source).model_dump(mode="json")
        for source in course_source_repository.list_for_course(db, course_id)
    ]


def iter_switch_course_source(
    db: Session, *, course_id: int, source_id: int, user_id: int, settings: Settings
) -> Iterator[dict]:
    """Fait d'une source passive l'active de son épreuve, et **réécrit le
    classement** — en flux SSE (#624), même mécanisme que le re-scrape à la
    demande (#118) : #275 tranche que les deux « doivent partager le même
    mécanisme, pas en inventer deux », et la bascule bloquante dépassait le
    délai du proxy sur une épreuve fan-out (Klikego, 30-40 s), d'où un 502
    avant même le premier octet (#624).

    Décision D2 de #275 : le remplacement est **total**. Les participations de
    l'épreuve sont supprimées puis réimportées depuis le nouveau chronométreur, là
    où un upsert par dossard laisserait survivre les lignes de l'ancienne source
    absentes de la nouvelle — le classement resterait le mélange de deux
    chronométreurs que l'epic existe pour supprimer.

    **La garde d'existence est synchrone, hors du générateur** — même raison
    qu'`iter_rescrape_course` : `StreamingResponse` (Starlette) envoie le statut
    HTTP **avant** de tirer le premier élément du générateur, donc une exception
    levée depuis l'intérieur d'un générateur déjà en flux ne peut plus jamais
    devenir un 404, seulement une coupure à 200.

    Sans effet si la source visée est déjà active (double-clic, écran rechargé) :
    rend alors un flux d'un seul événement `done` à zéro, sans thread ni verrou —
    re-scraper par acquit de conscience détruirait un classement pour rien, et
    le journal se remplirait de non-événements (FR-012).

    **L'ordre des quatre étapes reste le contrat, pas un détail d'écriture**, à
    l'intérieur du thread de travail (`_stream_switch_course_source`) : on
    scrape, on valide, on détruit, on réimporte. Rien de destructeur n'est
    écrit avant qu'on tienne un classement utilisable — c'est ce qui rend
    impossible l'accident propre à ce geste, une épreuve vidée puis abandonnée
    à zéro résultat. Deux refus qu'aucun scraper ne signalerait, et qui
    coûteraient un classement : zéro résultat (banal sur le chemin d'import
    ordinaire, ici un classement effacé) et une autre épreuve
    (`mapping.get_or_create_course` apparie sur `(nom, date, type, relais)` à
    l'égalité stricte — un libellé différent chez le second chronométreur
    créerait une **nouvelle** épreuve et laisserait celle qu'on vient de vider
    à zéro résultat). Les deux lèvent depuis `_require_same_event`, dans le
    thread, et deviennent un événement `error` plutôt qu'un refus HTTP — même
    compromis que le re-scrape (`_stream_rescrape`), imposé par
    `StreamingResponse`.

    La purge des fiches coureur devenues vides relève les candidats **avant** la
    suppression et ne tranche qu'**après** le réimport : avant, il n'y aurait plus
    de participation pour les désigner ; après, les coureurs republiés par le
    nouveau chronométreur en portent une et survivent d'eux-mêmes.
    """
    course = admin_actions.course_or_404(db, course_id)
    source = course_source_repository.find_on_course(
        db, course_id=course_id, source_id=source_id
    )
    if source is None:
        raise NotFoundError("Source introuvable pour cette épreuve.")
    if source.is_active:
        return iter([
            {
                "phase": "done",
                "participations_deleted": 0,
                "participations_imported": 0,
                "athletes_purged": 0,
                "sources": _source_dicts(db, course_id),
            }
        ])

    sortante = course_source_repository.get_active(db, course_id)

    lock_courses_or_409(db, course_id)
    return _stream_switch_course_source(
        db,
        course_id=course_id,
        course_name=course.name,
        attendue=admin_actions.instantane(course, admin_actions.CHAMPS_COURSE),
        source_id=source_id,
        source_url=source.url,
        sortante_url=sortante.url if sortante is not None else None,
        user_id=user_id,
        settings=settings,
    )


def delete_course_source(
    db: Session, *, course_id: int, source_id: int, user_id: int
) -> None:
    """Supprime une source inactive (#739). N'affecte aucun résultat déjà
    importé : les participations sont portées par la `Course`, jamais par la
    source (`models/AGENTS.md`).

    Refuse l'active — même garde que `switch_course_source` sur `is_active`
    à `false` : l'index partiel autorise zéro active, mais une épreuve sans
    active n'est plus scrapée (#282) ni affichée avec sa source (#279).
    """
    admin_actions.course_or_404(db, course_id)
    # Une bascule en cours vers cette source la relirait disparue (#982).
    lock_courses_or_409(db, course_id)
    source = course_source_repository.find_on_course(
        db, course_id=course_id, source_id=source_id
    )
    if source is None:
        raise NotFoundError("Source introuvable pour cette épreuve.")
    if source.is_active:
        raise DomainError(
            "Impossible de supprimer la source active — basculez d'abord une "
            "autre source."
        )

    payload = {"course_id": course_id, "url": source.url, "provider": source.provider}
    course_source_repository.remove(db, source)
    admin_action_log_repository.create(
        db,
        user_id=user_id,
        action="course_source.delete",
        entity_type="course_source",
        entity_id=source_id,
        payload=payload,
    )
    logger.info(
        "Admin %s deleted source %s (%s) from course %s",
        user_id, source_id, payload["url"], course_id,
    )


def _stream_switch_course_source(
    db: Session,
    *,
    course_id: int,
    course_name: str,
    attendue: dict,
    source_id: int,
    source_url: str,
    sortante_url: str | None,
    user_id: int,
    settings: Settings,
) -> Iterator[dict]:
    """Le générateur SSE de la bascule — scrape, détruit, réimporte, dans un
    thread dédié indépendant de la consommation du flux (FR-011, patron exact
    de `_stream_rescrape`, dont la docstring détaille pourquoi la `Session`
    n'est ni close ici ni ailleurs)."""
    def worker(emit: sse_relay.Emit) -> dict:
        try:
            candidats = athlete_repository.only_on_course(db, course_id)
            emit({"phase": "scraping", "message": "Récupération des participants…"})

            results, _trace = _drain_scrape(
                import_dispatch.scrape_all_streaming(
                    source_url, db, settings, use_cache_probe=False
                ),
                emit,
            )
            _require_same_event(results, attendue)
            for attempt in deadlock_retries(db, label=f"bascule de source de l'épreuve {course_id}"):
                with attempt:
                    if attempt.number > 1:
                        # Le rollback du rejeu a relâché le verrou d'épreuve (#980).
                        lock_courses_or_409(db, course_id)
                    _require_course_unchanged(db, course_id, attendue)

                    course = admin_actions.course_or_404(db, course_id)
                    source = course_source_repository.find_on_course(
                        db, course_id=course_id, source_id=source_id
                    )
                    if source is None:
                        raise NotFoundError("Source introuvable pour cette épreuve.")

                    supprimees = participation_repository.delete_for_course(db, course)
                    course_source_repository.set_active(db, source)

                    emit({"phase": "saving", "total": len(results)})
                    outcome = import_persistence.persist_results(db, source_url, results)
                    purges = athlete_repository.delete_orphans_among(db, candidats)

                    admin_action_log_repository.create(
                        db,
                        user_id=user_id,
                        action="course.source.switch",
                        entity_type="course",
                        entity_id=course_id,
                        payload={
                            "name": course_name,
                            # Les deux URLs, sans quoi l'entrée dirait « la source a
                            # changé » sans dire depuis quoi — donc sans permettre de
                            # défaire le geste de tête.
                            "previous_url": sortante_url,
                            "new_url": source_url,
                            "participations_deleted": supprimees,
                            "participations_imported": outcome["imported"],
                            "athletes_purged": len(purges),
                        },
                    )
                    db.commit()
            final = {"phase": "done",
                "participations_deleted": supprimees,
                "participations_imported": outcome["imported"],
                "athletes_purged": len(purges),
                "sources": _source_dicts(db, course_id),
            }
            logger.info(
                "Admin %s switched course %s source to %s (%s deleted, %s imported)",
                user_id,
                course_id,
                source_url,
                supprimees,
                outcome["imported"],
            )
        except DomainError as exc:
            db.rollback()
            final = {"phase": "error", "message": exc.message}
        except Exception:
            db.rollback()
            logger.exception("Rollback de la bascule de source de la course %s", course_id)
            final = {"phase": "error", "message": "Erreur lors de l'enregistrement des résultats."}
        # Le verrou d'épreuve tombe avec la transaction, au commit ou au rollback.
        return final

    return sse_relay.relay(worker)


def _require_course_unchanged(db: Session, course_id: int, attendue: dict) -> None:
    """Relit l'épreuve après un scrape de 30 à 40 s (#982).

    Sous PostgreSQL, le verrou d'épreuve empêche déjà toute écriture concurrente ;
    cette relecture ferme le reste, un geste qui aurait supprimé ou renommé
    l'épreuve entre l'instantané de la garde et la persistance.
    """
    course = course_repository.get_fresh(db, course_id)
    if course is None:
        raise DomainError("Cette épreuve n'existe plus : rien n'a été enregistré.")
    if admin_actions.instantane(course, admin_actions.CHAMPS_COURSE) != attendue:
        raise DomainError(
            "Cette épreuve a été modifiée pendant la récupération des résultats : "
            "rien n'a été enregistré. Relancez l'opération."
        )


def _require_same_event(results: list, attendue: dict) -> None:
    """Refuse un scrape qui n'alimenterait pas **cette** épreuve.

    Lit l'identité sur les résultats en mémoire, avec `admin_actions.CHAMPS_COURSE` — la même
    définition que celle de la correction d'identité, et la même que celle sur
    laquelle `course_repository.get_by_identity` apparie. Un seul résultat à la
    bonne identité suffit : une URL fan-out publie légitimement plusieurs
    épreuves, les autres suivent leur chemin habituel.
    """
    if not results:
        raise ScraperError(
            "Le chronométreur n'a publié aucun résultat à cette adresse. "
            "Les résultats affichés n'ont pas été touchés."
        )
    for scraped in results:
        identite = {
            "name": scraped.event_name,
            "event_date": (
                scraped.event_date.isoformat() if scraped.event_date else None
            ),
            "event_type": scraped.event_type,
            "is_relay": scraped.is_relay,
        }
        if identite == attendue:
            return
    publiee = results[0]
    raise ScraperError(
        f"Cette adresse publie une autre épreuve (« {publiee.event_name} »), "
        f"pas « {attendue['name']} ». Rapprochez d'abord les deux épreuves : "
        "une bascule laisserait celle-ci sans aucun résultat."
    )


def iter_rescrape_course(
    db: Session, *, course_id: int, user_id: int, settings: Settings
) -> Iterator[dict]:
    """Re-scrape la source **active** d'une course déjà en base, en upsert (#118).

    **Fonction ordinaire, pas un générateur** — c'est ce qui rend le refus
    synchrone. `iter_import_event` n'a jamais eu à le faire : ses seuls refus
    (URL invalide, zéro résultat) sont acceptables en événement `phase: error`
    dans un flux déjà ouvert. Ici FR-007 exige un vrai **409** *avant* le
    premier octet du flux, or `StreamingResponse` (Starlette) envoie ses
    en-têtes — donc le code HTTP — **avant** de tirer le premier élément du
    générateur : une exception levée depuis l'intérieur d'un générateur ne
    peut plus jamais devenir un 404/409, seulement une coupure de flux à 200.
    En restant une fonction normale, l'appel lève *tout de suite* — la route
    peut l'exécuter avant de construire le `StreamingResponse` — et ne rend un
    générateur (celui qui scrape et persiste) qu'une fois la garde passée.

    Refuse (404) si la course n'existe pas ou n'a aucune source active (saisie
    manuelle, ou épreuve dont on n'a rattaché que des passives) — rien à
    re-scraper. Refuse (409) si une autre opération écrit déjà cette épreuve
    (FR-007, `course_locks`, #982). Le verrou est celui de la transaction de
    `db` : pris ici, il tient jusqu'au `commit` ou au `rollback` du thread de
    travail, scrape compris, et tombe aussi avec la session si le flux n'est
    jamais itéré.

    Le générateur rendu **ne survit pas à la garde** : le scrape et la
    persistance tournent dans un thread dédié, indépendant de la consommation
    du flux SSE (FR-011, research.md R7) — si l'administrateur perd sa
    connexion, Starlette cesse d'appeler `next()` sur ce générateur, mais le
    thread, lui, continue jusqu'à son terme et commite normalement.
    """
    course = admin_actions.course_or_404(db, course_id)
    source = course_source_repository.get_active(db, course_id)
    if source is None:
        raise NotFoundError("Cette épreuve n'a aucune source active à re-scraper.")

    lock_courses_or_409(db, course_id)
    return _stream_rescrape(
        db,
        course_id=course_id,
        course_name=course.name,
        attendue=admin_actions.instantane(course, admin_actions.CHAMPS_COURSE),
        source_url=source.url,
        user_id=user_id,
        settings=settings,
    )


def _stream_rescrape(
    db: Session,
    *,
    course_id: int,
    course_name: str,
    attendue: dict,
    source_url: str,
    user_id: int,
    settings: Settings,
) -> Iterator[dict]:
    """Le générateur SSE proprement dit — scrape et persiste dans un thread dédié.

    **Ne clôt pas la `Session`** — même convention que le reste du fichier,
    l'appelant la possède. `ponytail:` la route qui pilote ce générateur en
    production lui passe une session dédiée (`SessionLocal()`, patron de
    `scrape.py`) qu'elle ne referme jamais explicitement non plus : la fermer
    depuis ce thread casserait FR-011 dès qu'un objet chargé par le générateur
    appelant (attributs différés, `Course` de la garde) est relu après une
    déconnexion, et la fermer depuis le générateur appelant reproduirait le
    bug que FR-011 existe pour éviter — le thread continuerait d'écrire dans
    une session fermée. Une connexion tenue jusqu'au ramasse-miettes après
    chaque re-scrape est le coût accepté ; upgrade si le volume de re-scrapes
    concurrents en fait un jour un problème mesuré (pool de connexions dédié).
    """
    def worker(emit: sse_relay.Emit) -> dict:
        try:
            candidats = athlete_repository.only_on_course(db, course_id)
            emit({"phase": "scraping", "message": "Récupération des participants…"})

            # `scrape_all_streaming` yield déjà ses propres events `scraping`
            # par heat (fan-out Klikego, #156) — relayés tels quels par
            # `_drain_scrape`, aucun callback à brancher ici.
            results, _trace = _drain_scrape(
                import_dispatch.scrape_all_streaming(
                    source_url, db, settings, use_cache_probe=False
                ),
                emit,
            )
            _require_same_event(results, attendue)
            for attempt in deadlock_retries(db, label=f"re-scrape de l'épreuve {course_id}"):
                with attempt:
                    if attempt.number > 1:
                        # Le rollback du rejeu a relâché le verrou d'épreuve (#980).
                        lock_courses_or_409(db, course_id)
                    _require_course_unchanged(db, course_id, attendue)

                    total = len(results)
                    emit({
                        "phase": "saving", "total": total,
                        "imported": 0, "updated": 0, "skipped": 0, "progress": 0,
                    })
                    # Les rattrapages de lot (#294, #672, #757) passent avec la boucle :
                    # le re-scrape les sautait et défaisait les rangs renumérotés (#914).
                    for done, persister in import_persistence.persist_steps(db, source_url, results):
                        if done and (done % 20 == 0 or done == total):
                            emit({
                                "phase": "saving", "total": total,
                                "imported": persister.imported, "updated": persister.updated,
                                "skipped": persister.skipped, "progress": done,
                            })
                    purges = athlete_repository.delete_orphans_among(db, candidats)

                    admin_action_log_repository.create(
                        db,
                        user_id=user_id,
                        action="course.rescrape",
                        entity_type="course",
                        entity_id=course_id,
                        payload={
                            "name": course_name,
                            "source_url": source_url,
                            "imported": persister.imported,
                            "updated": persister.updated,
                            "skipped": persister.skipped,
                            "reconciled": persister.reconciled,
                            "athletes_purged": len(purges),
                        },
                    )
                    db.commit()
            final = {"phase": "done",
                "imported": persister.imported,
                "updated": persister.updated,
                "skipped": persister.skipped,
                "reconciled": persister.reconciled,
                "total": total,
                "orphans_removed": len(purges),
            }
            logger.info(
                "Admin %s rescraped course %s (%s imported, %s updated, %s purged)",
                user_id, course_id, persister.imported, persister.updated, len(purges),
            )
        except DomainError as exc:
            db.rollback()
            final = {"phase": "error", "message": exc.message}
        except Exception:
            db.rollback()
            logger.exception("Rollback du re-scrape de la course %s", course_id)
            final = {"phase": "error", "message": "Erreur lors de l'enregistrement des résultats."}
        # Le verrou d'épreuve tombe avec la transaction, au commit ou au rollback.
        return final

    return sse_relay.relay(worker)


def _drain_scrape(gen: Iterator[dict], emit: sse_relay.Emit) -> tuple:
    """Émet chaque event intermédiaire de `gen`, rend `(results, trace)`.

    `gen` est le générateur de `scrape_all_streaming` — appelé ici depuis un
    thread ordinaire (pas via `yield from`, réservé aux corps de générateur),
    d'où ce relais manuel par `next()`/`StopIteration`.
    """
    while True:
        try:
            emit(next(gen))
        except StopIteration as stop:
            return stop.value
