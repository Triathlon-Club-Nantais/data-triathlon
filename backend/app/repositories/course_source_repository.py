"""Accès données pour CourseSource — les N sources d'une épreuve, dont une active (#279).

**Seule** couche qui touche la Session pour ces lignes. Elle existe parce que
`Course.source_url` et `Course.provider` ne sont plus des colonnes : les écrire
signifie désormais écrire *ici*, et nulle part ailleurs.
"""
from sqlalchemy.orm import Session, selectinload

from app.models.course import Course
from app.models.course_source import CourseSource


def list_for_course(db: Session, course_id: int) -> list[CourseSource]:
    """Les sources de l'épreuve, **l'active en tête** puis les passives par âge.

    L'ordre n'est pas cosmétique : c'est celui que rendra la liste publique
    (#284), et le laisser au hasard du plan de requête ferait sauter la source
    affichée d'un rechargement à l'autre.
    """
    return (
        db.query(CourseSource)
        .filter(CourseSource.course_id == course_id)
        .order_by(CourseSource.is_active.desc(), CourseSource.created_at, CourseSource.id)
        .all()
    )


def get_active(db: Session, course_id: int) -> CourseSource | None:
    """La source active, ou `None` — une épreuve saisie à la main n'en a aucune."""
    return (
        db.query(CourseSource)
        .filter(CourseSource.course_id == course_id, CourseSource.is_active)
        .first()
    )


def find_by_url(db: Session, *, course_id: int, url: str) -> CourseSource | None:
    """La source de **cette** épreuve portant **cette** URL, sur la clé unique.

    Portée à l'épreuve, et non globale, parce que c'est la forme de la contrainte :
    `UNIQUE(course_id, url)`. Une même URL porte légitimement N épreuves — heats
    Klikego, multi-catégories Wiclax, multi-listes RaceResult, multi-épreuves
    Chronoplace — donc « trouver par URL » sans dire *sur quelle épreuve* n'a pas
    de réponse unique.
    """
    return (
        db.query(CourseSource)
        .filter(CourseSource.course_id == course_id, CourseSource.url == url)
        .first()
    )


def list_by_urls(db: Session, urls: list[str]) -> list[CourseSource]:
    """Les sources portant l'une de ces URLs, **toutes épreuves confondues** (#282).

    Le pendant global de `find_by_url` : celui-ci répond « cette URL, sur cette
    épreuve », celle-ci « qui porte cette URL, où que ce soit ». C'est la question
    du ciblage explicite de `rescrape-db`, qui reçoit une URL nue sans savoir à
    quelle épreuve elle appartient, ni même si elle est connue.

    Rend les **lignes de source**, pas les épreuves, parce que l'appelant a
    besoin de `is_active` : une URL absente de la table et une URL passive
    demandent deux réponses opposées (scraper, refuser).

    `selectinload` en chaîne jusqu'aux sources de l'épreuve : le refus nomme
    `source.course.name` **et** l'URL active de cette épreuve, laquelle se lit sur
    la collection `course.sources`. Sans la seconde étape, nommer l'active
    coûterait une requête par URL refusée.

    Ordre stable `(course_id, id)` : deux URLs d'une même épreuve se suivent, et
    le refus ne change pas de forme d'une exécution à l'autre.
    """
    if not urls:
        return []
    return (
        db.query(CourseSource)
        .options(selectinload(CourseSource.course).selectinload(Course.sources))
        .filter(CourseSource.url.in_(urls))
        .order_by(CourseSource.course_id, CourseSource.id)
        .all()
    )


def add(
    db: Session,
    *,
    course: Course,
    url: str,
    provider: str = "",
    is_active: bool = False,
    created_by_user_id: int | None = None,
) -> CourseSource:
    """Rattache une source à l'épreuve. **Passive par défaut** (D3).

    Passe par `course.sources` et non par un `db.add` sec : la collection est
    peut-être déjà chargée, et une ligne insérée à côté d'elle laisserait
    `course.source_url` sur sa valeur d'avant jusqu'à expiration — la propriété
    dérivée lit cette collection.
    """
    source = CourseSource(
        url=url,
        provider=provider,
        is_active=is_active,
        created_by_user_id=created_by_user_id,
    )
    course.sources.append(source)
    db.flush()
    return source


def attach(db: Session, *, course: Course, url: str, provider: str = "") -> CourseSource:
    """La source de cette épreuve portant cette URL, **rattachée au besoin** (#283).

    Le point d'entrée de l'import : il est appelé une fois par ligne scrapée, sans
    condition, et c'est son idempotence qui le permet — l'appelant n'a aucun
    registre à tenir de ce qu'il a déjà vu, et `UNIQUE(course_id, url)` ne remonte
    jamais en exception sur le chemin nominal du re-scrape.

    **Active si l'épreuve n'en a aucune, passive sinon.** Les deux moitiés sont la
    même règle (D3, « la première scrapée garde la main ») lue dans deux états :
    une épreuve sans source n'a personne à qui laisser la main, une épreuve qui en
    a une ne la reprend pas. Rattacher en passive une épreuve sans active
    produirait une source orpheline — jamais scrapée (#282), jamais affichée
    (#279), et qu'un administrateur devrait activer à la main faute d'alternative.

    Cherche dans `course.sources` plutôt que par `find_by_url` : la collection est
    déjà chargée (la propriété dérivée `Course.source_url` la lit), et une requête
    par ligne scrapée coûterait 250 allers-retours sur un classement ordinaire.
    """
    for existante in course.sources:
        if existante.url == url:
            return existante
    return add(
        db, course=course, url=url, provider=provider,
        is_active=not any(source.is_active for source in course.sources),
    )


def set_active(db: Session, source: CourseSource) -> CourseSource:
    """Fait de cette source l'active de son épreuve, et de l'ancienne une passive.

    **Deux `flush` et pas un.** L'unicité est un index partiel
    `UNIQUE(course_id) WHERE is_active` : émettre les deux `UPDATE` dans le même
    vidage laisserait le moteur libre de poser le second actif avant de retirer
    le premier, et la contrainte tomberait sur un état que l'appelant n'a jamais
    demandé. L'ordre est donc explicite — on désactive, on vide, on active.

    Ne re-scrape rien : le remplacement total des participations (D2) est le
    travail de #285, sur ce point de bascule.
    """
    sortante = get_active(db, source.course_id)
    if sortante is not None and sortante.id == source.id:
        return source
    if sortante is not None:
        sortante.is_active = False
        db.flush()
    source.is_active = True
    db.flush()
    return source
