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

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import DuplicateError, NotFoundError, ScraperError
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
