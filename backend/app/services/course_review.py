"""Revue humaine de la fiabilité d'une épreuve (#115, FR-036).

**Aucune branche, aucun recalcul** : `Course.is_reliable` est
`coalesce(reliability_override, is_reliable_computed)`, la propriété fait le
travail. Lever l'avis humain fait donc réapparaître le *dernier* verdict
calculé — pas celui qui valait au moment de la décision (FR-039).
"""
from sqlalchemy.orm import Session

from app.models.course import Course


def set_override(db: Session, course: Course, *, verdict: bool | None) -> Course:
    """Pose (`True`/`False`) ou **lève** (`None`) l'avis humain.

    N'écrit jamais `is_reliable_computed` : les deux chemins d'écriture ne se
    croisent pas, et c'est la forme qui l'assure — pas une garde applicative
    qu'un import distrait pourrait contourner (FR-037).
    """
    course.reliability_override = verdict
    db.flush()
    return course
