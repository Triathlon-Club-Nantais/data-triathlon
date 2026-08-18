"""Les gestes correctifs d'un administrateur sur les données (#117, #285).

**Contrat commun à tous les gestes**, et il tient en trois règles :

1. *Aucune `Session` touchée directement* — tout passe par `repositories/`
   (Principe II).
2. *`flush`, jamais `commit`* — la route clôt la transaction. C'est ce qui rend
   l'action et sa trace **indissociables** (FR-015) : un refus lève avant, et
   rien n'est écrit, ni la donnée ni le journal.
3. *Le journal n'enregistre que ce qui a changé* — une demande sans effet n'est
   pas un geste (FR-012), et un journal rempli de non-événements est un journal
   qu'on cesse de lire.

**L'unicité se vérifie par lecture préalable**, jamais en s'en remettant à
l'`IntegrityError` de la contrainte : celle-ci rendrait un message technique
anglais, invaliderait la transaction — donc empêcherait d'écrire quoi que ce
soit ensuite — et ne permettrait pas de **nommer** la fiche en conflit, ce
qu'exigent FR-005 et FR-021.
"""
import logging
import queue
import threading
from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import DomainError, DuplicateError, NotFoundError, ScraperError
from app.models.athlete import Athlete
from app.models.course import Course
from app.models.course_source import CourseSource
from app.models.participation import Participation
from app.repositories import (
    admin_action_log_repository,
    athlete_repository,
    course_repository,
    course_source_repository,
    participation_repository,
)
from app.services import import_service

logger = logging.getLogger(__name__)


def _course_or_404(db: Session, course_id: int) -> Course:
    course = course_repository.get(db, course_id)
    if course is None:
        raise NotFoundError("Épreuve introuvable.")
    return course


def _athlete_or_404(db: Session, athlete_id: int) -> Athlete:
    athlete = athlete_repository.get(db, athlete_id)
    if athlete is None:
        raise NotFoundError("Coureur introuvable.")
    return athlete


def _participation_or_404(db: Session, participation_id: int) -> Participation:
    participation = participation_repository.get(db, participation_id)
    if participation is None:
        raise NotFoundError("Résultat introuvable.")
    return participation


def get_athlete(db: Session, *, athlete_id: int) -> Athlete:
    """La fiche complète d'un coureur, ou 404. Lecture pure."""
    return _athlete_or_404(db, athlete_id)


def course_deletion_impact(db: Session, *, course_id: int) -> dict:
    """Ce que la suppression de cette épreuve détruirait. **Ne modifie rien** (FR-026).

    Les deux comptes sont ceux que la modale de confirmation annonce (FR-017), et
    `athletes` sort de la **même** fonction que celle qui purge — c'est ce qui
    rend SC-007 structurel plutôt que surveillé : **à base constante**, l'annonce
    et l'acte ne peuvent pas diverger, puisqu'ils lisent la même définition.

    Entre le chiffrage et la suppression, en revanche, il s'écoule une seconde
    requête HTTP : un import concurrent peut ajouter des participations et faire
    mentir le nombre affiché. Inhérent au découpage en deux appels, et non
    corrigeable à coût raisonnable pour un geste d'administration.
    """
    course = _course_or_404(db, course_id)
    return {
        "course_id": course.id,
        "name": course.name,
        "participations": participation_repository.count_for_course(db, course.id),
        "athletes": len(athlete_repository.only_on_course(db, course.id)),
    }


def delete_course(db: Session, *, course_id: int, user_id: int) -> dict:
    """Supprime une épreuve, ses résultats, et les fiches coureur qu'elle laisse vides.

    **L'ordre n'est pas indifférent** : les candidats à la purge se relèvent
    *avant* la suppression. Après, leurs participations n'existent plus, la liste
    revient vide, et la purge devient un no-op qu'aucune erreur ne signale.
    """
    course = _course_or_404(db, course_id)
    resume = {
        "name": course.name,
        "event_date": course.event_date.isoformat() if course.event_date else None,
        "event_type": course.event_type,
        "is_relay": course.is_relay,
        "participations_deleted": participation_repository.count_for_course(db, course.id),
    }
    candidats = athlete_repository.only_on_course(db, course.id)

    course_repository.delete(db, course)
    db.flush()
    resume["athletes_purged"] = athlete_repository.delete_orphans_among(db, candidats)

    admin_action_log_repository.create(
        db,
        user_id=user_id,
        action="course.delete",
        entity_type="course",
        entity_id=course_id,
        payload=resume,
    )
    logger.info(
        "Admin %s deleted course %s (%s participations, %s athletes purged)",
        user_id,
        course_id,
        resume["participations_deleted"],
        len(resume["athletes_purged"]),
    )
    return resume


def wipe_impact(db: Session) -> dict:
    """Ce qu'une purge totale des résultats détruirait. **Ne modifie rien** (#384).

    Même principe que `course_deletion_impact` : `athletes` vient de la
    **même** lecture que celle sur laquelle s'appuiera la purge (le compte
    total de la table), pour que l'annonce et l'acte ne puissent pas diverger
    à base constante.
    """
    return {
        "participations": participation_repository.count_all(db),
        "athletes": athlete_repository.count_all(db),
    }


def wipe_all_participations(db: Session, *, user_id: int) -> dict:
    """Vide `participations`, purge les fiches devenues vides, force un rescrape (#384).

    **`Course` et `course_sources` restent strictement intacts** — c'est ce
    qui permet de relancer un rescrape sans tout réimporter depuis les URLs
    sources. `scraped_at` est remis à `NULL` sur toute la base pour que le
    cache TTL ne masque pas ce rescrape immédiat.

    **Les comptes journalisés sont ceux que les `DELETE` rendent**, jamais un
    `COUNT(*)` préalable : ce dernier ferait un balayage de plus sur la plus
    grosse table de la base, et un import concurrent validé entre les deux
    requêtes serait supprimé sans être compté — la trace sous-estimerait un
    geste irréversible. Même raison côté athlètes, où c'est `delete_all` qui
    est appelé et non le balayage d'orphelins : après le premier `DELETE`, les
    deux ensembles coïncident, et un `DELETE` sans `WHERE` ne bute pas sur le
    plafond de paramètres liés de PostgreSQL.

    Contrairement à `delete_course`, le journal ne garde que des **comptes**,
    jamais la liste des ids purgés : à l'échelle de la base entière, cette
    liste peut porter des milliers d'entrées, et gonflerait le journal d'audit
    pour un geste qui n'a par nature qu'un seul lecteur (« combien la dernière
    purge a-t-elle emporté »).
    """
    resume = {"participations_deleted": participation_repository.delete_all(db)}
    resume["athletes_purged"] = athlete_repository.delete_all(db)
    resume["courses_reset"] = course_repository.reset_scraped_at_all(db)

    admin_action_log_repository.create(
        db,
        user_id=user_id,
        action="participations.wipe_all",
        entity_type="participations",
        entity_id=0,  # sentinelle « base entière » — aucune entité unique à désigner
        # Les deux compteurs annoncés par `wipe_impact` (#384) — pas
        # `courses_reset` : la spec de l'issue borne le payload à ce que la
        # confirmation a chiffré, et `resume` (la valeur de retour) le garde
        # pour l'appelant qui en aurait besoin.
        payload={
            "participations_deleted": resume["participations_deleted"],
            "athletes_purged": resume["athletes_purged"],
        },
    )
    logger.info(
        "Admin %s wiped all participations (%s deleted, %s athletes purged, %s courses reset)",
        user_id,
        resume["participations_deleted"],
        resume["athletes_purged"],
        resume["courses_reset"],
    )
    return resume


def courses_wipe_impact(db: Session) -> dict:
    """Ce qu'une purge totale des épreuves détruirait. **Ne modifie rien** (#384).

    Même principe que `wipe_impact` : chaque compte vient de la lecture sur
    laquelle s'appuiera la purge elle-même, pour que l'annonce et l'acte ne
    puissent pas diverger à base constante.
    """
    return {
        "courses": course_repository.count_all(db),
        "participations": participation_repository.count_all(db),
        "athletes": athlete_repository.count_all(db),
    }


def wipe_all_courses(db: Session, *, user_id: int) -> dict:
    """Vide le catalogue d'épreuves — sources et résultats compris (#384, suite).

    **Strictement plus destructeur que `wipe_all_participations`** : ici,
    `Course` et `course_sources` disparaissent aussi (`course_repository
    .delete_all` — `DELETE` de masse, enfants d'abord, pas la cascade ORM de
    la suppression d'une seule épreuve).

    Les participations disparaissent par ricochet, sans compte à journaliser :
    les compter à part reproduirait le `COUNT(*)` préalable évité dans
    `wipe_all_participations` (même risque de sous-estimation sous écriture
    concurrente), pour une valeur que personne ne relit — le geste se mesure
    en épreuves, pas en résultats.

    **`athletes_purged` rejoint `courses_deleted` dans le journal**, ce que
    `wipe_all_participations` ne fait pas pour `courses_reset` : la règle de
    ce dernier (« le payload est borné à ce que la confirmation a chiffré »)
    n'est pas contredite, elle ne s'applique juste pas de la même façon ici —
    `athletes_purged` vient de `delete_all`, sans le risque de sous-estimation
    qui exclut `participations` du payload, donc rien ne justifie de le taire.
    """
    resume = {"courses_deleted": course_repository.delete_all(db)}
    resume["athletes_purged"] = athlete_repository.delete_all(db)

    admin_action_log_repository.create(
        db,
        user_id=user_id,
        action="courses.wipe_all",
        entity_type="courses",
        entity_id=0,  # sentinelle « base entière », même patron que participations.wipe_all
        # Littéral et non `resume` : garder le payload journalisé visiblement
        # distinct de la valeur de retour, même s'ils coïncident aujourd'hui —
        # patron de `wipe_all_participations`, où les deux divergent déjà.
        payload={
            "courses_deleted": resume["courses_deleted"],
            "athletes_purged": resume["athletes_purged"],
        },
    )
    logger.info(
        "Admin %s wiped all courses (%s deleted, %s athletes purged)",
        user_id,
        resume["courses_deleted"],
        resume["athletes_purged"],
    )
    return resume


def switch_course_source(
    db: Session, *, course_id: int, source_id: int, user_id: int, settings: Settings
) -> list[CourseSource]:
    """Fait d'une source passive l'active de son épreuve, et **réécrit le classement**.

    Décision D2 de #275 : le remplacement est **total**. Les participations de
    l'épreuve sont supprimées puis réimportées depuis le nouveau chronométreur, là
    où un upsert par dossard laisserait survivre les lignes de l'ancienne source
    absentes de la nouvelle — le classement resterait le mélange de deux
    chronométreurs que l'epic existe pour supprimer.

    **L'ordre des quatre étapes est le contrat, pas un détail d'écriture.**
    On scrape, on valide, on détruit, on réimporte. Rien de destructeur n'est
    écrit avant qu'on tienne un classement utilisable, et c'est ce qui rend
    impossible l'accident que cette route pourrait provoquer : une épreuve vidée
    par un geste d'administration qui échoue ensuite à la remplir. Aucun rollback
    n'est aussi solide que de n'avoir rien écrit — et le refus, lui, lève avant le
    `commit` de la route, donc n'écrit ni donnée ni entrée de journal (FR-015).

    Deux refus qu'aucun scraper ne signalerait, et qui coûteraient un classement :

    - **Zéro résultat.** Sur le chemin d'import ordinaire c'est un succès à zéro
      compteur ; ici ce serait un classement effacé. Le cas est banal — une page
      de résultats retirée, une URL qui répond encore sans plus rien publier.
    - **Une autre épreuve.** `mapping.get_or_create_course` apparie sur
      `(nom, date, type, relais)` à l'égalité stricte : un libellé différent chez
      le second chronométreur ferait naître une **nouvelle** épreuve et laisserait
      celle qu'on vient de vider à zéro résultat, sans qu'aucune exception ne
      passe. Faire converger deux identités est le travail de #289, les rapprocher
      celui de #287 ; ici on refuse.

    La purge des fiches coureur devenues vides relève les candidats **avant** la
    suppression et ne tranche qu'**après** le réimport : avant, il n'y aurait plus
    de participation pour les désigner ; après, les coureurs republiés par le
    nouveau chronométreur en portent une et survivent d'eux-mêmes.
    """
    course = _course_or_404(db, course_id)
    source = course_source_repository.find_on_course(
        db, course_id=course_id, source_id=source_id
    )
    if source is None:
        raise NotFoundError("Source introuvable pour cette épreuve.")
    if source.is_active:
        # Un double-clic, un écran rechargé : l'état voulu est l'état atteint.
        # Re-scraper par acquit de conscience détruirait un classement pour rien,
        # et le journal se remplirait de non-événements (FR-012).
        return course_source_repository.list_for_course(db, course_id)

    sortante = course_source_repository.get_active(db, course_id)
    attendue = _instantane(course, _CHAMPS_COURSE)

    results, _trace = import_service.scrape_for_replacement(source.url, db, settings)
    _require_same_event(results, attendue)

    candidats = athlete_repository.only_on_course(db, course_id)
    supprimees = participation_repository.delete_for_course(db, course)
    course_source_repository.set_active(db, source)
    outcome = import_service.persist_results(db, source.url, results)
    purges = athlete_repository.delete_orphans_among(db, candidats)

    admin_action_log_repository.create(
        db,
        user_id=user_id,
        action="course.source.switch",
        entity_type="course",
        entity_id=course_id,
        payload={
            "name": course.name,
            # Les deux URLs, sans quoi l'entrée dirait « la source a changé » sans
            # dire depuis quoi — donc sans permettre de défaire le geste de tête.
            "previous_url": sortante.url if sortante is not None else None,
            "new_url": source.url,
            "participations_deleted": supprimees,
            "participations_imported": outcome["imported"],
            "athletes_purged": len(purges),
        },
    )
    logger.info(
        "Admin %s switched course %s source to %s (%s deleted, %s imported)",
        user_id,
        course_id,
        source.url,
        supprimees,
        outcome["imported"],
    )
    return course_source_repository.list_for_course(db, course_id)


def _require_same_event(results: list, attendue: dict) -> None:
    """Refuse un scrape qui n'alimenterait pas **cette** épreuve.

    Lit l'identité sur les résultats en mémoire, avec `_CHAMPS_COURSE` — la même
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


class CourseRescrapeAlreadyRunningError(DomainError):
    """Un re-scrape est déjà en cours sur cette course (FR-007, #118)."""

    status_code = 409
    message = "Un re-scrape est déjà en cours sur cette épreuve."


#: Verrou de concurrence par course (research.md R5) : un `dict[int, bool]` en
#: mémoire, process unique. `ponytail:` verrou process unique — migrer vers un
#: verrou DB (`SELECT … FOR UPDATE`, ou colonne `rescrape_lock_at`) si le
#: service passe un jour multi-instance.
_rescrape_locks: dict[int, bool] = {}
_rescrape_locks_guard = threading.Lock()


def _acquire_rescrape_lock(course_id: int) -> None:
    with _rescrape_locks_guard:
        if _rescrape_locks.get(course_id):
            raise CourseRescrapeAlreadyRunningError()
        _rescrape_locks[course_id] = True


def _release_rescrape_lock(course_id: int) -> None:
    with _rescrape_locks_guard:
        _rescrape_locks.pop(course_id, None)


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
    re-scraper. Refuse (409) si un re-scrape est déjà en cours sur cette
    course (FR-007) ; le verrou est relâché en fin d'opération, y compris en
    échec.

    `ponytail:` le verrou n'est relâché que dans le `finally` du thread de
    travail (`_stream_rescrape`), lui-même démarré seulement à la première
    itération du générateur rendu ici. Si l'appelant ASGI n'itérait jamais ce
    générateur après la garde (déconnexion dans la fenêtre étroite entre la
    réponse acceptée et le premier `next()` de Starlette), le verrou resterait
    tenu jusqu'au redémarrage du process — même propriété acceptée que le
    verrou lui-même (research.md R5, data-model.md : « un redémarrage le
    réinitialise silencieusement »). Upgrade si mesuré en production.

    Le générateur rendu **ne survit pas à la garde** : le scrape et la
    persistance tournent dans un thread dédié, indépendant de la consommation
    du flux SSE (FR-011, research.md R7) — si l'administrateur perd sa
    connexion, Starlette cesse d'appeler `next()` sur ce générateur, mais le
    thread, lui, continue jusqu'à son terme et commite normalement.
    """
    course = _course_or_404(db, course_id)
    source = course_source_repository.get_active(db, course_id)
    if source is None:
        raise NotFoundError("Cette épreuve n'a aucune source active à re-scraper.")

    _acquire_rescrape_lock(course_id)
    return _stream_rescrape(
        db,
        course_id=course_id,
        course_name=course.name,
        attendue=_instantane(course, _CHAMPS_COURSE),
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
    events: queue.Queue[dict | object] = queue.Queue()
    sentinel = object()
    holder: dict = {}

    def worker() -> None:
        try:
            candidats = athlete_repository.only_on_course(db, course_id)
            events.put({"phase": "scraping", "message": "Récupération des participants…"})

            # `_scrape_all_streaming` yield déjà ses propres events `scraping`
            # par heat (fan-out Klikego, #156) — relayés tels quels par
            # `_drain_scrape`, aucun callback à brancher ici.
            results, _trace = _drain_scrape(
                import_service._scrape_all_streaming(
                    source_url, db, settings, use_cache_probe=False
                ),
                events,
            )
            _require_same_event(results, attendue)

            total = len(results)
            persister = import_service._Persister(db, source_url)
            events.put({
                "phase": "saving", "total": total,
                "imported": 0, "updated": 0, "skipped": 0, "progress": 0,
            })
            for i, scraped in enumerate(results):
                persister.add(scraped)
                if (i + 1) % 20 == 0 or i == total - 1:
                    events.put({
                        "phase": "saving", "total": total,
                        "imported": persister.imported, "updated": persister.updated,
                        "skipped": persister.skipped, "progress": i + 1,
                    })
            persister.finalize()
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
            holder["done"] = {
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
            holder["error"] = exc.message
        except Exception:
            db.rollback()
            logger.exception("Rollback du re-scrape de la course %s", course_id)
            holder["error"] = "Erreur lors de l'enregistrement des résultats."
        finally:
            events.put(sentinel)
            _release_rescrape_lock(course_id)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    while True:
        # Même compromis que `_scrape_all_streaming` : 0,5 s entre réactivité de
        # la coupure côté client et coût CPU.
        try:
            item = events.get(timeout=0.5)
        except queue.Empty:
            continue
        if item is sentinel:
            break
        yield item

    if "error" in holder:
        yield {"phase": "error", "message": holder["error"]}
    else:
        yield {"phase": "done", **holder["done"]}


def _drain_scrape(gen: Iterator[dict], events: "queue.Queue[dict | object]") -> tuple:
    """Pousse chaque event intermédiaire de `gen` dans `events`, rend `(results, trace)`.

    `gen` est le générateur de `_scrape_all_streaming` — appelé ici depuis un
    thread ordinaire (pas via `yield from`, réservé aux corps de générateur),
    d'où ce relais manuel par `next()`/`StopIteration`.
    """
    while True:
        try:
            events.put(next(gen))
        except StopIteration as stop:
            return stop.value


def reassign_participation(
    db: Session, *, participation_id: int, athlete_id: int, user_id: int
) -> Participation:
    """Rattache un résultat à un autre coureur, et purge la fiche qu'il vide.

    **Un rattachement vers le coureur qui porte déjà le résultat réussit sans
    rien consigner** : l'état voulu est l'état atteint, mais une demande sans
    effet n'est pas un geste (FR-012). Le journal ne se remplit pas de
    non-événements — sans quoi on cesse de le lire.
    """
    participation = _participation_or_404(db, participation_id)
    cible = _athlete_or_404(db, athlete_id)
    source_id = participation.athlete_id

    if source_id == cible.id:
        return participation

    if participation_repository.exists_for_athlete_on_course(
        db, athlete_id=cible.id, course_id=participation.course_id
    ):
        raise DuplicateError("Ce coureur a déjà un résultat sur cette épreuve.")

    course_id = participation.course_id
    participation_repository.reassign(db, participation, athlete_id=cible.id)
    purges = athlete_repository.delete_orphans_among(db, [source_id])

    admin_action_log_repository.create(
        db,
        user_id=user_id,
        action="participation.reassign",
        entity_type="participation",
        entity_id=participation_id,
        payload={
            "course_id": course_id,
            "from_athlete_id": source_id,
            "to_athlete_id": cible.id,
            "athletes_purged": purges,
        },
    )
    logger.info(
        "Admin %s reassigned participation %s from athlete %s to %s",
        user_id,
        participation_id,
        source_id,
        cible.id,
    )
    return participation


#: Les champs d'identité éditables d'un coureur. Le triplet, et rien d'autre.
_CHAMPS_ATHLETE = ("nom", "prenom", "birth_date")

#: Ceux d'une épreuve — exactement la clé `uq_course_identity`.
_CHAMPS_COURSE = ("name", "event_date", "event_type", "is_relay")

#: Les quatre champs qu'un bénévole peut corriger sur un résultat en attente (#437).
_CHAMPS_PARTICIPATION = ("bib_number", "rank_overall", "club", "category")


def _instantane(entite, champs: tuple[str, ...]) -> dict:
    """Les champs surveillés, sérialisables pour le journal."""
    valeurs = {}
    for champ in champs:
        valeur = getattr(entite, champ)
        valeurs[champ] = valeur.isoformat() if hasattr(valeur, "isoformat") else valeur
    return valeurs


def update_athlete(db: Session, *, athlete_id: int, champs: dict, user_id: int) -> Athlete:
    """Corrige l'identité d'un coureur — nom, prénom, date de naissance (FR-004).

    **Le doublon se détecte par lecture préalable**, jamais par l'`IntegrityError`
    de `uq_athlete_identity` : celle-ci invaliderait la transaction et rendrait un
    message technique, là où AC2 demande de **nommer** la fiche en conflit.
    """
    athlete = _athlete_or_404(db, athlete_id)
    avant = _instantane(athlete, _CHAMPS_ATHLETE)
    demande = {champ: champs[champ] for champ in _CHAMPS_ATHLETE if champ in champs}

    vise = {**{champ: getattr(athlete, champ) for champ in _CHAMPS_ATHLETE}, **demande}
    conflit = athlete_repository.get_by_identity(
        db, nom=vise["nom"], prenom=vise["prenom"], birth_date=vise["birth_date"]
    )
    if conflit is not None and conflit.id != athlete.id:
        raise DuplicateError(
            f"Un coureur porte déjà cette identité (fiche #{conflit.id})."
        )

    athlete_repository.update_identity(db, athlete, **demande)
    apres = _instantane(athlete, _CHAMPS_ATHLETE)
    if apres == avant:
        return athlete

    admin_action_log_repository.create(
        db,
        user_id=user_id,
        action="athlete.update",
        entity_type="athlete",
        entity_id=athlete_id,
        payload={"before": avant, "after": apres},
    )
    logger.info("Admin %s updated athlete %s", user_id, athlete_id)
    return athlete


def validate_participation(db: Session, *, participation_id: int, user_id: int) -> Participation:
    """Lève l'état d'attente d'un résultat déclaré manuellement (#271, US1).

    **Idempotent** (FR-012, même patron que `reassign_participation`) : un
    résultat déjà validé rend l'état voulu sans écrire un second geste au
    journal — une demande sans effet n'est pas un geste.
    """
    participation = _participation_or_404(db, participation_id)
    if not participation.is_pending_validation:
        return participation

    participation_repository.update(db, participation, is_pending_validation=False)

    admin_action_log_repository.create(
        db,
        user_id=user_id,
        action="participation.validate",
        entity_type="participation",
        entity_id=participation_id,
        payload={"course_id": participation.course_id, "athlete_id": participation.athlete_id},
    )
    logger.info("Admin %s validated participation %s", user_id, participation_id)
    return participation


def reject_participation(db: Session, *, participation_id: int, user_id: int) -> Participation:
    """Signale un résultat en attente comme non conforme (#437).

    **Ne touche jamais `is_pending_validation`** : une entrée rejetée n'a
    jamais été *validée*, elle reste en attente pour toujours — c'est cet
    invariant qui la fait profiter gratuitement des cinq exclusions déjà
    posées sur `is_pending_validation` (`app/core/validation.py`).

    **Idempotent**, même patron que `validate_participation`.
    """
    participation = _participation_or_404(db, participation_id)
    if participation.is_rejected:
        return participation

    participation_repository.update(db, participation, is_rejected=True)

    admin_action_log_repository.create(
        db,
        user_id=user_id,
        action="participation.reject",
        entity_type="participation",
        entity_id=participation_id,
        payload={"course_id": participation.course_id, "athlete_id": participation.athlete_id},
    )
    logger.info("Admin %s rejected participation %s", user_id, participation_id)
    return participation


def unreject_participation(db: Session, *, participation_id: int, user_id: int) -> Participation:
    """Annule un rejet — l'entrée réapparaît dans la file bénévoles (#437).

    Idempotent : une entrée qui n'est pas rejetée rend l'état voulu sans
    écrire un second geste.
    """
    participation = _participation_or_404(db, participation_id)
    if not participation.is_rejected:
        return participation

    participation_repository.update(db, participation, is_rejected=False)

    admin_action_log_repository.create(
        db,
        user_id=user_id,
        action="participation.unreject",
        entity_type="participation",
        entity_id=participation_id,
        payload={"course_id": participation.course_id, "athlete_id": participation.athlete_id},
    )
    logger.info("Admin %s unrejected participation %s", user_id, participation_id)
    return participation


def update_participation_fields(
    db: Session, *, participation_id: int, champs: dict, user_id: int
) -> Participation:
    """Corrige dossard, place au général, club et catégorie d'un résultat en
    attente (#437).

    **Le conflit de dossard se détecte par lecture préalable**
    (`exists_for_bib`), jamais par l'`IntegrityError` de `uq_participation_bib`
    — même règle que `update_athlete` pour les doublons d'identité. Le dossard
    inchangé ne déclenche jamais ce contrôle : `exists_for_bib` trouverait la
    ligne elle-même et rendrait un faux conflit.

    **Un dossard vide ou blanc est normalisé en `None` avant toute autre
    étape** (revue finale, #437) : sinon `if nouveau_dossard and ...` — faux
    sur une chaîne vide — laisserait passer `""` sans contrôle de conflit, et
    deux résultats corrigés vers `""` collisionneraient sur
    `uq_participation_bib`, exactement l'`IntegrityError` non maîtrisée que ce
    module s'interdit ailleurs. La colonne est nullable ; `""` doit se
    comporter comme « pas de dossard », au même titre que `None`.
    """
    participation = _participation_or_404(db, participation_id)
    demande = {champ: champs[champ] for champ in _CHAMPS_PARTICIPATION if champ in champs}
    if "bib_number" in demande and isinstance(demande["bib_number"], str) and not demande["bib_number"].strip():
        demande["bib_number"] = None

    nouveau_dossard = demande.get("bib_number")
    if nouveau_dossard and nouveau_dossard != participation.bib_number:
        if participation_repository.exists_for_bib(db, participation.course_id, nouveau_dossard):
            raise DuplicateError(
                "Ce dossard est déjà attribué à un autre participant de cette épreuve."
            )

    avant = _instantane(participation, _CHAMPS_PARTICIPATION)
    participation_repository.update(db, participation, **demande)
    apres = _instantane(participation, _CHAMPS_PARTICIPATION)
    if apres == avant:
        return participation

    admin_action_log_repository.create(
        db,
        user_id=user_id,
        action="participation.correct_fields",
        entity_type="participation",
        entity_id=participation_id,
        payload={"before": avant, "after": apres},
    )
    logger.info("Admin %s corrected fields of participation %s", user_id, participation_id)
    return participation


def update_course(db: Session, *, course_id: int, champs: dict, user_id: int) -> Course:
    """Corrige le libellé d'une épreuve — nom, date, type, relais (FR-020).

    **Aucun résultat n'est touché** (FR-023) : ces quatre colonnes vivent sur
    `Course`, et rien ici ne descend vers `Participation`.
    """
    course = _course_or_404(db, course_id)
    avant = _instantane(course, _CHAMPS_COURSE)
    demande = {champ: champs[champ] for champ in _CHAMPS_COURSE if champ in champs}

    vise = {**{champ: getattr(course, champ) for champ in _CHAMPS_COURSE}, **demande}
    conflit = course_repository.get_by_identity(
        db,
        name=vise["name"],
        event_date=vise["event_date"],
        event_type=vise["event_type"],
        is_relay=vise["is_relay"],
    )
    if conflit is not None and conflit.id != course.id:
        raise DuplicateError(
            f"Une épreuve porte déjà ce nom à cette date (fiche #{conflit.id})."
        )

    course_repository.update_identity(db, course, **demande)
    apres = _instantane(course, _CHAMPS_COURSE)
    if apres == avant:
        return course

    admin_action_log_repository.create(
        db,
        user_id=user_id,
        action="course.update",
        entity_type="course",
        entity_id=course_id,
        payload={"before": avant, "after": apres},
    )
    logger.info("Admin %s updated course %s", user_id, course_id)
    return course
