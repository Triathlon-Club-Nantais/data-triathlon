"""Fusion de deux épreuves publiées deux fois — l'aperçu d'impact (#286).

**Pourquoi un aperçu séparé du geste.** Absorber une épreuve supprime ses
résultats ; ceux qui n'ont pas de jumeau dans la cible disparaissent jusqu'au
prochain re-scrape, et il en existe — deux chronométreurs ne publient pas les
mêmes partants (#261 relève des nombres d'athlètes différents sur la même
épreuve). La perte est assumée par l'epic #275 ; ce qui ne l'est pas, c'est
qu'elle se découvre après.

Ce module ne modifie rien. La fusion elle-même est #287, et viendra ici.
"""
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError, NotFoundError
from app.models.course import Course
from app.repositories import (
    athlete_repository,
    course_repository,
    course_source_repository,
    participation_repository,
)


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
    if course_id == absorbed_id:
        # Rien à absorber, et #287 supprimerait la cible qu'on croit garder.
        raise DomainError("Une épreuve ne peut pas être fusionnée avec elle-même.")

    target = _course_or_404(db, course_id)
    absorbed = _course_or_404(db, absorbed_id)

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
