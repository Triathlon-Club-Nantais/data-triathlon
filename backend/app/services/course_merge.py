"""Fusion de deux épreuves publiées deux fois — l'aperçu (#286) et l'acte (#287).

**Pourquoi un aperçu séparé du geste.** Absorber une épreuve supprime ses
résultats ; ceux qui n'ont pas de jumeau dans la cible disparaissent jusqu'au
prochain re-scrape, et il en existe — deux chronométreurs ne publient pas les
mêmes partants (#261 relève des nombres d'athlètes différents sur la même
épreuve). La perte est assumée par l'epic #275 ; ce qui ne l'est pas, c'est
qu'elle se découvre après.

Les deux vivent ici, et le partage n'est pas une commodité : `_pair_or_400` et
`_url_already_known` sont appelés par l'un **et** par l'autre, ce qui interdit à
l'annonce et à l'acte de diverger — le refus a un seul libellé, et « la fusion
n'ajoutera aucune source » a un seul prédicat.
"""
import logging

from sqlalchemy.orm import Session

from app.core.exceptions import DomainError, NotFoundError
from app.models.course import Course
from app.repositories import (
    admin_action_log_repository,
    athlete_repository,
    course_repository,
    course_source_repository,
    participation_repository,
)

logger = logging.getLogger(__name__)


def _course_or_404(db: Session, course_id: int) -> Course:
    course = course_repository.get(db, course_id)
    if course is None:
        raise NotFoundError("Épreuve introuvable.")
    return course


def _url_already_known(db: Session, *, target: Course, absorbed: Course) -> bool:
    """L'URL de l'absorbée est-elle **déjà** une source de la cible ?

    Toutes les sources de la cible, l'active comme les passives : la forme de la
    contrainte l'impose, `UNIQUE(course_id, url)` ignore `is_active`. Une URL
    déjà connue de la cible ne peut donc pas y être repointée — la fusion
    n'ajoute aucune source, elle supprime un doublon (cas Mesquer, ids 38 et 50
    en base de dev : même URL, même provider, deux `event_type`).

    Une absorbée **sans source** — saisie à la main — rend `""`, et la chaîne
    vide n'est l'URL de personne : sans ce garde, elle partirait quand même en
    recherche, et un jour où une source porterait une URL vide, deux épreuves
    saisies à la main passeraient pour des doublons l'une de l'autre.
    """
    url = absorbed.source_url
    if not url:
        return False
    return course_source_repository.find_by_url(db, course_id=target.id, url=url) is not None


def _pair_or_400(db: Session, *, course_id: int, absorbed_id: int) -> tuple[Course, Course]:
    """Les deux épreuves d'une fusion, ou le refus — **une seule fois pour les deux
    ressources**.

    L'aperçu et l'acte partagent ce préambule pour que le refus ne puisse pas
    diverger : deux formulations d'un même « on ne fusionne pas une épreuve avec
    elle-même » finiraient par se contredire, et l'écran afficherait un message
    selon qu'il a prévisualisé ou commis.

    **Le refus passe avant les deux lectures**, donc `?absorbed_id=` égal à un
    identifiant inexistant rend 400 et non 404 : la demande est incohérente en
    elle-même, avant même de savoir si l'épreuve existe.
    """
    if course_id == absorbed_id:
        # Rien à absorber, et la fusion supprimerait la cible qu'on croit garder.
        raise DomainError("Une épreuve ne peut pas être fusionnée avec elle-même.")
    return _course_or_404(db, course_id), _course_or_404(db, absorbed_id)


def _identity(db: Session, course: Course) -> dict:
    """Ce qui permet à un exploitant de reconnaître l'épreuve qu'il désigne.

    Les trois champs par lesquels les deux côtés diffèrent le plus souvent —
    `name`, `event_date`, `event_type` — sortent **tels quels**, sans
    rapprochement ni avertissement : deux libellés qui divergent sont le cas
    nominal d'une épreuve publiée deux fois, pas le signe d'une erreur de saisie.
    """
    return {
        "id": course.id,
        "name": course.name,
        "event_date": course.event_date,
        "event_type": course.event_type,
        "is_relay": course.is_relay,
        "provider": course.provider,
        "participations": participation_repository.count_for_course(db, course.id),
    }


def merge_impact(db: Session, *, course_id: int, absorbed_id: int) -> dict:
    """Ce que la fusion de `absorbed_id` dans `course_id` coûterait. **Ne modifie rien.**

    `athletes_orphaned` sort de la **même** fonction que la purge de #117
    (`athlete_repository.only_on_course`), donc de celle que #287 appellera :
    l'annonce et l'acte lisent une seule définition, et ne peuvent pas diverger à
    base constante. Entre l'aperçu et la fusion il s'écoule en revanche une
    seconde requête HTTP — un import concurrent peut faire mentir les chiffres,
    comme pour `deletion-impact`, et ce n'est pas corrigeable à coût raisonnable
    pour un geste d'administration.

    Le nombre de requêtes est **constant** : deux lectures d'épreuve, deux
    comptes, une agrégation à deux colonnes, une recherche d'URL. Rapprocher les
    deux classements en Python en coûterait 1811 sur la plus chargée des épreuves
    en base (#163).
    """
    target, absorbed = _pair_or_400(db, course_id=course_id, absorbed_id=absorbed_id)

    unmatched, unmatched_tcn = participation_repository.count_bibs_absent_from(
        db, course_id=absorbed.id, other_course_id=target.id
    )
    return {
        "target": _identity(db, target),
        "absorbed": _identity(db, absorbed),
        "participations_without_match": unmatched,
        "tcn_participations_without_match": unmatched_tcn,
        "athletes_orphaned": len(athlete_repository.only_on_course(db, absorbed.id)),
        "same_source_url": _url_already_known(db, target=target, absorbed=absorbed),
    }


def merge_courses(db: Session, *, course_id: int, absorbed_id: int, user_id: int) -> dict:
    """Absorbe `absorbed_id` dans `course_id` : l'URL rejoint la cible, la ligne meurt.

    **La fusion ne re-scrape rien, et c'est la décision qui la définit.** La cible
    garde son identité, sa source active et ses participations ; l'absorbée
    disparaît avec les siennes, et son URL rejoint la cible en **passive**. Prendre
    les données de l'autre chronométreur est un *second* geste, la bascule de #285
    — deux décisions distinctes, donc deux gestes distincts. Fondre les deux
    donnerait un geste dont personne ne pourrait prédire le classement obtenu.

    **Seule l'active de l'absorbée survit ; ses passives meurent avec elle.** Ce
    n'est pas une économie, c'est ce qui rend vraie la promesse de l'aperçu : quand
    `same_source_url` vaut vrai, l'écran annonce « aucune source ne sera ajoutée ».
    Faire suivre les passives ferait apparaître des sources non annoncées, et
    `same_source_url` — qui ne regarde que l'URL *active* de l'absorbée — deviendrait
    un prédicat faux. Les deux ressources appellent d'ailleurs le **même**
    `_url_already_known` : l'annonce et l'acte ne peuvent pas diverger à base
    constante. Une passive perdue reste rattrapable par le chemin ordinaire — la
    recoller recrée une épreuve, que #288 signale et qu'une seconde fusion rapproche.

    **L'ordre des lectures est le piège de cette fonction.** Le résumé, l'URL
    active, le compte de participations et les candidats à la purge se relèvent
    **avant** la suppression : après, l'épreuve n'a plus ni source ni résultat, la
    liste des candidats revient vide, et la purge devient un no-op qu'aucune erreur
    ne signale (même piège et même primitive qu'`admin_actions.delete_course`).

    `flush` sans `commit` : c'est la route qui clôt la transaction, ce qui rend le
    geste et sa trace indissociables — un refus n'écrit ni donnée ni entrée de
    journal (FR-015).
    """
    target, absorbed = _pair_or_400(db, course_id=course_id, absorbed_id=absorbed_id)

    resume = {
        "name": target.name,
        # L'identité complète de l'absorbée, et pas seulement son identifiant : sa
        # ligne est supprimée, cette entrée est la **seule** trace qui reste d'elle.
        # Un exploitant qui relit six mois plus tard doit pouvoir dire quelle
        # épreuve a disparu, et par quelle URL la retrouver.
        "absorbed": {
            "id": absorbed.id,
            "name": absorbed.name,
            "event_date": absorbed.event_date.isoformat() if absorbed.event_date else None,
            "event_type": absorbed.event_type,
            "is_relay": absorbed.is_relay,
            "source_url": absorbed.source_url,
        },
        "participations_deleted": participation_repository.count_for_course(db, absorbed.id),
    }
    a_deplacer = (
        None
        if _url_already_known(db, target=target, absorbed=absorbed)
        else course_source_repository.get_active(db, absorbed.id)
    )
    candidats = athlete_repository.only_on_course(db, absorbed.id)

    if a_deplacer is not None:
        course_source_repository.move_to(db, source=a_deplacer, course=target)
    course_repository.delete(db, absorbed)
    db.flush()
    resume["athletes_purged"] = len(athlete_repository.delete_orphans_among(db, candidats))
    resume["source_added"] = a_deplacer is not None

    admin_action_log_repository.create(
        db,
        user_id=user_id,
        action="course.merge",
        entity_type="course",
        # Rattachée à la **survivante** : c'est la seule des deux qu'on pourra
        # encore interroger, et l'historique d'une épreuve doit porter les fusions
        # qu'elle a absorbées.
        entity_id=course_id,
        payload=resume,
    )
    logger.info(
        "Admin %s merged course %s into %s (%s participations deleted, %s athletes purged)",
        user_id,
        absorbed_id,
        course_id,
        resume["participations_deleted"],
        resume["athletes_purged"],
    )
    return {
        "target_id": course_id,
        "absorbed_id": absorbed_id,
        "participations_deleted": resume["participations_deleted"],
        "athletes_purged": resume["athletes_purged"],
        "source_added": resume["source_added"],
        "sources": course_source_repository.list_for_course(db, course_id),
    }
