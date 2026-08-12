"""Accès données pour CourseSource — les N sources d'une épreuve, dont une active (#279).

**Seule** couche qui touche la Session pour ces lignes. Elle existe parce que
`Course.source_url` et `Course.provider` ne sont plus des colonnes : les écrire
signifie désormais écrire *ici*, et nulle part ailleurs.
"""
from sqlalchemy.orm import Session

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
