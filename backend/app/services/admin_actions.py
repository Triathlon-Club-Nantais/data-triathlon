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
from typing import NamedTuple

import psycopg.errors
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.athlete_identity import athlete_identity_keys
from app.core.exceptions import DomainError, DuplicateError, NotFoundError
from app.core.time import utcnow
from app.models.athlete import Athlete
from app.models.course import Course
from app.models.participation import Participation
from app.repositories import (
    admin_action_log_repository,
    athlete_alias_repository,
    athlete_repository,
    challenge_repository,
    course_repository,
    lock_repository,
    participation_repository,
    season_validation_repository,
    tcn_count_repository,
    volunteer_action_repository,
)
from app.scrapers.base import STATUS_FINISHER
from app.scrapers.utils import MAX_RELAY_TEAMMATES, MIN_RELAY_TEAMMATES
from app.services import (
    opposition_service,
)
from app.services.course_locks import (
    lock_all_courses_or_409,
    lock_courses_or_409,
)

logger = logging.getLogger(__name__)


def course_or_404(db: Session, course_id: int) -> Course:
    course = course_repository.get(db, course_id)
    if course is None:
        raise NotFoundError("Épreuve introuvable.")
    return course


def _athlete_or_404(db: Session, athlete_id: int) -> Athlete:
    athlete = athlete_repository.get(db, athlete_id)
    if athlete is None:
        raise NotFoundError("Athlète introuvable.")
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
    course = course_or_404(db, course_id)
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
    course = course_or_404(db, course_id)
    lock_courses_or_409(db, course_id)
    resume = {
        "name": course.name,
        "event_date": course.event_date.isoformat() if course.event_date else None,
        "event_type": course.event_type,
        "is_relay": course.is_relay,
        "participations_deleted": participation_repository.count_for_course(db, course.id),
    }
    candidats = athlete_repository.only_on_course(db, course.id)
    athlete_ids = participation_repository.athlete_ids_on_course(db, course.id)

    course_repository.delete(db, course)
    db.flush()
    tcn_count_repository.recompute_counts_for_tcn(db, athlete_ids=athlete_ids)
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
    **même** prédicat que celui sur lequel s'appuiera la purge (les fiches que
    rien ne référence hors des résultats, #994), pour que l'annonce et l'acte ne puissent pas diverger
    à base constante.
    """
    return {
        "participations": participation_repository.count_all(db),
        "athletes": athlete_repository.count_unreferenced(db),
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
    geste irréversible. Même raison côté athlètes, où c'est
    `delete_unreferenced` qui est appelé et non le balayage d'orphelins : après
    le premier `DELETE`, les deux ensembles coïncident, et un `DELETE`
    ensembliste sans liste d'ids ne bute pas sur le plafond de paramètres liés
    de PostgreSQL. Une fiche encore référencée par un bénévolat, une validation
    de saison ou un compte survit à la purge (#994).

    Contrairement à `delete_course`, le journal ne garde que des **comptes**,
    jamais la liste des ids purgés : à l'échelle de la base entière, cette
    liste peut porter des milliers d'entrées, et gonflerait le journal d'audit
    pour un geste qui n'a par nature qu'un seul lecteur (« combien la dernière
    purge a-t-elle emporté »).
    """
    lock_all_courses_or_409(db)
    resume = {"participations_deleted": participation_repository.delete_all(db)}
    # Les cumuls Challenge dérivent des résultats purgés (#1008).
    challenge_repository.delete_all(db)
    resume["athletes_purged"] = athlete_repository.delete_unreferenced(db)
    resume["courses_reset"] = course_repository.reset_scraped_at_all(db)
    # Compteurs dénormalisés (#623) : toutes les participations disparaissent,
    # même patron bulk que la ligne au-dessus.
    course_repository.zero_counts_all(db)

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
        "athletes": athlete_repository.count_unreferenced(db),
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
    `athletes_purged` vient de `delete_unreferenced`, sans le risque de sous-estimation
    qui exclut `participations` du payload, donc rien ne justifie de le taire.
    """
    lock_all_courses_or_409(db)
    resume = {"courses_deleted": course_repository.delete_all(db)}
    # Les cumuls Challenge dérivent des résultats purgés (#1008).
    challenge_repository.delete_all(db)
    resume["athletes_purged"] = athlete_repository.delete_unreferenced(db)

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
    lock_courses_or_409(db, participation.course_id)
    cible = _athlete_or_404(db, athlete_id)
    source_id = participation.athlete_id
    # Un relais attribué (#894) redevient un résultat à un seul coureur, même
    # vers l'un de ses équipiers (FR-008) : ses anciens équipiers sont
    # candidats à la purge au même titre que la source.
    anciens_equipiers = participation_repository.teammate_athlete_ids(db, participation.id)

    if source_id == cible.id and not anciens_equipiers:
        return participation

    if participation_repository.exists_for_athlete_on_course(
        db,
        athlete_id=cible.id,
        course_id=participation.course_id,
        exclude_participation_id=participation.id,
    ):
        raise DuplicateError("Cet athlète a déjà un résultat sur cette épreuve.")

    course_id = participation.course_id
    participation_repository.replace_teammates(db, participation, [])
    participation_repository.reassign(db, participation, athlete_id=cible.id, lock=True)
    purges = athlete_repository.delete_orphans_among(
        db, [i for i in dict.fromkeys([source_id, *anciens_equipiers]) if i != cible.id]
    )
    tcn_count_repository.recompute_counts_for_tcn(
        db, athlete_ids=[source_id, cible.id, *anciens_equipiers], course_ids=[course_id]
    )

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


class NewTeammate(NamedTuple):
    """Un équipier sans fiche connue, désigné par son nom (#894, US2)."""

    athlete_name: str
    athlete_firstname: str


def set_teammates(
    db: Session,
    *,
    participation_id: int,
    teammates: list[int | NewTeammate],
    user_id: int,
) -> Participation:
    """Attribue un résultat de relais à ses équipiers, en un seul geste (#894).

    `teammates` est la composition voulue, dans l'ordre : le premier devient le
    porteur (`athlete_id`). Un équipier est une fiche (`int`) ou un nom
    (`NewTeammate`), qui réutilise la fiche de même nom et prénom si elle existe
    et n'est créée qu'après tous les refus possibles : tout ou rien. Une
    composition identique à l'actuelle réussit sans rien consigner, comme
    `reassign_participation`.
    """
    participation = _participation_or_404(db, participation_id)
    lock_courses_or_409(db, participation.course_id)
    if not (participation.is_relay or participation.course.is_relay):
        raise DomainError("Seul un résultat de relais peut être attribué à des équipiers.")
    if not MIN_RELAY_TEAMMATES <= len(teammates) <= MAX_RELAY_TEAMMATES:
        raise DomainError(
            f"Un relais s'attribue à {MIN_RELAY_TEAMMATES} à {MAX_RELAY_TEAMMATES} équipiers."
        )
    for ref in teammates:
        if isinstance(ref, NewTeammate):
            opposition_service.ensure_not_opposed(db, ref.athlete_name, ref.athlete_firstname)
    equipiers: list[Athlete | NewTeammate] = [
        _athlete_or_404(db, ref)
        if isinstance(ref, int)
        else athlete_repository.get_by_identity_keys(db, ref.athlete_name, ref.athlete_firstname)
        or ref
        for ref in teammates
    ]
    connus = [e.id for e in equipiers if isinstance(e, Athlete)]
    # Deux graphies d'une même identité (#907) désignent une seule personne, et
    # `get_or_create` les résoudrait vers la même fiche.
    inconnus = [
        athlete_identity_keys(e.athlete_name, e.athlete_firstname)
        for e in equipiers
        if isinstance(e, NewTeammate)
    ]
    if len(set(connus)) != len(connus) or len(set(inconnus)) != len(inconnus):
        raise DomainError("Un même athlète figure deux fois dans l'équipe.")

    actuels = participation_repository.teammate_athlete_ids(db, participation.id)
    if len(connus) == len(equipiers) and actuels == connus:
        return participation

    course_id = participation.course_id
    for equipier in equipiers:
        if not isinstance(equipier, Athlete):
            continue
        if equipier.id in actuels or equipier.id == participation.athlete_id:
            continue
        if participation_repository.exists_for_athlete_on_course(
            db, athlete_id=equipier.id, course_id=course_id
        ):
            nom = " ".join(filter(None, [equipier.nom, equipier.prenom]))
            raise DuplicateError(f"{nom} a déjà un résultat sur cette épreuve.")

    crees: list[int] = []
    ids: list[int] = []
    for equipier in equipiers:
        if isinstance(equipier, NewTeammate):
            equipier = athlete_repository.get_or_create(
                db, nom=equipier.athlete_name, prenom=equipier.athlete_firstname
            )
            crees.append(equipier.id)
        ids.append(equipier.id)

    source = participation.athlete
    source_id = source.id
    if not participation.team_name and not actuels:
        participation.team_name = " ".join(filter(None, [source.nom, source.prenom]))
    participation_repository.replace_teammates(db, participation, ids)
    participation_repository.reassign(db, participation, athlete_id=ids[0])
    candidats = [source_id, *actuels]
    purges = athlete_repository.delete_orphans_among(
        db, [i for i in dict.fromkeys(candidats) if i not in ids]
    )
    tcn_count_repository.recompute_counts_for_tcn(
        db, athlete_ids=[source_id, *actuels, *ids], course_ids=[course_id]
    )

    admin_action_log_repository.create(
        db,
        user_id=user_id,
        action="participation.set_teammates",
        entity_type="participation",
        entity_id=participation_id,
        payload={
            "course_id": course_id,
            "from_athlete_id": source_id,
            "teammate_ids": ids,
            "athletes_created": crees,
            "athletes_purged": purges,
        },
    )
    logger.info(
        "Admin %s set teammates %s on participation %s", user_id, ids, participation_id
    )
    return participation


def delete_participation(db: Session, *, participation_id: int, user_id: int) -> dict:
    """Supprime un résultat, et en garde la mémoire (#439).

    **Le `payload` se construit avant la suppression** : après, il n'y a plus rien
    à lire, et le journal est la seule trace de ce que portait la ligne.

    **Aucune purge de fiche coureur**, contrairement à `reassign_participation`
    (D5). Là, la fiche source n'a jamais rien couru — elle est le résidu d'une
    erreur de rattachement, et la purger achève le geste. Ici, la fiche est celle
    d'un coureur réel dont on retire un résultat erroné : la supprimer parce
    qu'elle devient vide dépasserait ce qui a été demandé.
    """
    participation = _participation_or_404(db, participation_id)
    lock_courses_or_409(db, participation.course_id)
    resume = {
        "athlete_id": participation.athlete_id,
        "athlete_name": f"{participation.athlete.prenom} {participation.athlete.nom}".strip(),
        "course_id": participation.course_id,
        "course_name": participation.course.name,
        "event_date": (
            participation.course.event_date.isoformat()
            if participation.course.event_date
            else None
        ),
        "bib_number": participation.bib_number,
        "rank_overall": participation.rank_overall,
        "total_time": participation.total_time,
        "status": participation.status,
        "was_pending_validation": participation.is_pending_validation,
    }

    admin_action_log_repository.create(
        db,
        user_id=user_id,
        action="participation.delete",
        entity_type="participation",
        entity_id=participation_id,
        payload=resume,
    )
    athlete_id = participation.athlete_id
    course_id = participation.course_id
    # Compteurs dénormalisés (#623) : ajustés seulement si la ligne comptait
    # déjà (#270) — une participation en attente n'entrait dans aucun agrégat
    # public, la supprimer n'en retire donc aucun. Le compte du club, lui, se
    # recalcule après la suppression : la ligne retirée pouvait rattacher au
    # club d'autres résultats de l'athlète (#1206).
    if not participation.is_pending_validation:
        course_repository.adjust_counts(
            db, participation.course, participation_delta=-1, tcn_delta=0
        )
    participation_repository.delete(db, participation)
    tcn_count_repository.recompute_counts_for_tcn(
        db, athlete_ids=[athlete_id], course_ids=[course_id]
    )
    logger.info("Admin %s deleted participation %s", user_id, participation_id)
    return resume


#: Les champs éditables d'un coureur : le triplet d'identité, plus le club actuel
#: (#439). Le club **n'entre pas** dans la clé d'unicité — deux homonymes de clubs
#: différents restent la même personne pour `uq_athlete_identity`.
_CHAMPS_ATHLETE = ("nom", "prenom", "birth_date", "club")

#: Ceux d'une épreuve — exactement la clé `uq_course_identity`.
CHAMPS_COURSE = ("name", "event_date", "event_type", "is_relay")

#: Les quatre champs qu'un bénévole peut corriger sur un résultat en attente (#437).
_CHAMPS_PARTICIPATION = ("bib_number", "rank_overall", "club", "category")


def instantane(entite, champs: tuple[str, ...]) -> dict:
    """Les champs surveillés, sérialisables pour le journal."""
    valeurs = {}
    for champ in champs:
        valeur = getattr(entite, champ)
        valeurs[champ] = valeur.isoformat() if hasattr(valeur, "isoformat") else valeur
    return valeurs


class AthleteBusyError(DomainError):
    """Un import tient la fiche : un renommage attendrait sa fin (#981)."""

    status_code = 409
    message = "Cette fiche est en cours d'import. Réessayez dans un instant."


def update_athlete(db: Session, *, athlete_id: int, champs: dict, user_id: int) -> Athlete:
    """Corrige la fiche d'un coureur — nom, prénom, date de naissance, club (FR-004).

    **Le doublon se détecte par lecture préalable**, jamais par l'`IntegrityError`
    de `uq_athlete_identity` : celle-ci invaliderait la transaction et rendrait un
    message technique, là où AC2 demande de **nommer** la fiche en conflit.

    Le club corrigé ici cesse de suivre les imports (`club_locked`, US3-AC4) ; les
    clubs portés par les **résultats** ne bougent pas — chacun garde celui de
    l'époque de sa course (FR-013).
    """
    athlete = _athlete_or_404(db, athlete_id)
    avant = instantane(athlete, _CHAMPS_ATHLETE)
    demande = {champ: champs[champ] for champ in _CHAMPS_ATHLETE if champ in champs}

    vise = {**{champ: getattr(athlete, champ) for champ in _CHAMPS_ATHLETE}, **demande}
    if "nom" in demande or "prenom" in demande:
        opposition_service.ensure_not_opposed(db, vise["nom"], vise["prenom"])
    # L'identité est la clé normalisée du nom et du prénom ; la date de naissance
    # n'y entre plus (#900). Une fiche renommée vers une clé neuve en devient la
    # fiche principale.
    if athlete_identity_keys(vise["nom"], vise["prenom"]) != (athlete.last_name_key, athlete.first_name_key):
        # Une variante mémorisée par une fusion vaut l'identité de sa fiche (#908).
        cle = athlete_identity_keys(vise["nom"], vise["prenom"])
        conflit = athlete_repository.get_by_identity_keys(
            db, vise["nom"], vise["prenom"]
        ) or athlete_alias_repository.get_by_keys_batch(db, [cle]).get(cle)
        if conflit is not None and conflit.id != athlete.id:
            raise DuplicateError(
                f"Un athlète porte déjà cette identité (fiche n° {conflit.id}).",
                extra={"conflicting_athlete_id": conflit.id},
            )
        # Renommée vers l'une de ses propres variantes : la graphie redevient son
        # identité, la variante n'a plus d'objet.
        athlete_alias_repository.delete_key(db, cle)
        demande["homonym_rank"] = 0

    # Le verrou se pose sur le **geste**, pas sur la présence du champ : le
    # formulaire renvoie le club prérempli à chaque enregistrement, et verrouiller
    # là gèlerait contre tous les imports à venir un libellé que personne n'a
    # corrigé.
    if "club" in demande and demande["club"] != athlete.club:
        demande["club_locked"] = True

    # Un import qui vient de résoudre la fiche la tient en `FOR KEY SHARE`, que
    # changer ses clés d'identité attendrait jusqu'à la fin du rescrape.
    lock_repository.bound_lock_waits(db, "5s")
    try:
        athlete_repository.update_identity(db, athlete, **demande)
    except OperationalError as exc:
        if isinstance(exc.orig, psycopg.errors.LockNotAvailable):
            raise AthleteBusyError() from exc
        raise
    apres = instantane(athlete, _CHAMPS_ATHLETE)
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
    lock_courses_or_409(db, participation.course_id)
    if not participation.is_pending_validation:
        return participation

    participation_repository.update(
        db, participation, is_pending_validation=False, validated_at=utcnow()
    )
    # Compteurs dénormalisés (#623) : c'est le seul geste hors import qui fait
    # entrer une participation dans les agrégats publics après coup (#270).
    course_repository.adjust_counts(
        db,
        participation.course,
        participation_delta=1,
        tcn_delta=0,
    )
    tcn_count_repository.recompute_counts_for_tcn(
        db, athlete_ids=[participation.athlete_id], course_ids=[participation.course_id]
    )

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
    lock_courses_or_409(db, participation.course_id)
    if participation.is_rejected:
        return participation

    participation_repository.update(db, participation, is_rejected=True, rejected_at=utcnow())

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
    lock_courses_or_409(db, participation.course_id)
    if not participation.is_rejected:
        return participation

    participation_repository.update(db, participation, is_rejected=False, rejected_at=None)

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

    avant = instantane(participation, _CHAMPS_PARTICIPATION)
    participation_repository.update(db, participation, **demande)
    apres = instantane(participation, _CHAMPS_PARTICIPATION)
    if apres == avant:
        return participation
    if avant["club"] != apres["club"]:
        tcn_count_repository.recompute_counts_for_tcn(db, athlete_ids=[participation.athlete_id])

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
    course = course_or_404(db, course_id)
    lock_courses_or_409(db, course_id)
    avant = instantane(course, CHAMPS_COURSE)
    demande = {champ: champs[champ] for champ in CHAMPS_COURSE if champ in champs}

    vise = {**{champ: getattr(course, champ) for champ in CHAMPS_COURSE}, **demande}
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
    apres = instantane(course, CHAMPS_COURSE)
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


def validate_season(db: Session, *, athlete_id: int, season: int, user_id: int):
    """Valide la saison d'un athlète (#709, FR-009 à FR-013).

    **L'unicité se vérifie par lecture préalable** (même règle que
    `update_athlete`), pas par l'`IntegrityError` de `uq_season_validation_athlete_season`.
    """
    _athlete_or_404(db, athlete_id)
    if season_validation_repository.get_for_athlete_season(db, athlete_id=athlete_id, season=season):
        raise DuplicateError("La saison de cet athlète est déjà validée.")

    validation = season_validation_repository.create(
        db, athlete_id=athlete_id, season=season, validated_by_user_id=user_id
    )
    admin_action_log_repository.create(
        db,
        user_id=user_id,
        action="athlete.season_validation.create",
        entity_type="athlete",
        entity_id=athlete_id,
        payload={"season": season},
    )
    logger.info("Admin %s validated season %s for athlete %s", user_id, season, athlete_id)
    return validation


def unvalidate_season(db: Session, *, athlete_id: int, season: int, user_id: int) -> None:
    """Dévalide la saison d'un athlète (#709, FR-013) — geste symétrique de `validate_season`."""
    _athlete_or_404(db, athlete_id)
    validation = season_validation_repository.get_for_athlete_season(
        db, athlete_id=athlete_id, season=season
    )
    if validation is None:
        raise NotFoundError("La saison de cet athlète n'est pas validée.")

    season_validation_repository.delete(db, validation)
    admin_action_log_repository.create(
        db,
        user_id=user_id,
        action="athlete.season_validation.delete",
        entity_type="athlete",
        entity_id=athlete_id,
        payload={"season": season},
    )
    logger.info("Admin %s unvalidated season %s for athlete %s", user_id, season, athlete_id)


def season_quota(db: Session, *, athlete_id: int, season: int) -> dict:
    """Les trois signaux du barème de validation (#709, FR-012) — ne modifie rien.

    `validated_count` recompte en Python plutôt que de réutiliser l'agrégat SQL
    d'`athlete_repository.list_with_season_participation_count` : un seul
    athlète, un coût négligeable à l'échelle du club. Même sémantique que là-bas
    (`not is_pending_validation`, `federal_only`, statut `finisher`) — à garder
    synchronisée si l'une des deux change (#845 : un DNS ou une discipline hors
    FFTRI ne doit pas compter dans les 3 épreuves requises).
    """
    # Comme `validate_season` : un quota « vide » masquait un identifiant faux (#1054).
    _athlete_or_404(db, athlete_id)
    participations = participation_repository.list_for_athlete(
        db, athlete_id, seasons=[season], federal_only=True
    )
    validated_count = sum(
        1
        for p in participations
        if not p.is_pending_validation and p.status.lower() == STATUS_FINISHER
    )
    return {
        "validated_count": validated_count,
        "has_volunteer_action": volunteer_action_repository.exists_for_athlete_season(
            db, athlete_id=athlete_id, season=season
        ),
        # Champ ajouté plutôt que `has_volunteer_action` modifié (Principe IV) :
        # une déclaration en attente n'est pas « aucune déclaration » (#1044).
        "has_pending_volunteer_action": volunteer_action_repository.pending_exists_for_athlete_season(
            db, athlete_id=athlete_id, season=season
        ),
        "season_validated": season_validation_repository.get_for_athlete_season(
            db, athlete_id=athlete_id, season=season
        )
        is not None,
    }
