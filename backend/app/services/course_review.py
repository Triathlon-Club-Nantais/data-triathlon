"""Revue humaine de la fiabilité d'une épreuve (#115, FR-036 ; tracée par #119).

**Aucune branche, aucun recalcul** : `Course.is_reliable` est
`coalesce(reliability_override, is_reliable_computed)`, la propriété fait le
travail. Lever l'avis humain fait donc réapparaître le *dernier* verdict
calculé — pas celui qui valait au moment de la décision (FR-039).
"""
from sqlalchemy.orm import Session

from app.models.course import Course
from app.repositories import admin_action_log_repository


def set_override(
    db: Session,
    course: Course,
    *,
    verdict: bool | None,
    user_id: int,
    notes: str | None = None,
) -> Course:
    """Pose (`True`/`False`) ou **lève** (`None`) l'avis humain, et le consigne.

    N'écrit jamais `is_reliable_computed` : les deux chemins d'écriture ne se
    croisent pas, et c'est la forme qui l'assure — pas une garde applicative
    qu'un import distrait pourrait contourner (FR-037).

    `flush`, jamais `commit` : la route clôt la transaction, ce qui rend le
    verdict et sa trace indissociables. Et **rien n'est consigné quand rien ne
    change** — reposer le verdict déjà en place n'est pas un geste.
    """
    previous = course.reliability_override
    if previous == verdict:
        return course

    course.reliability_override = verdict
    admin_action_log_repository.create(
        db,
        user_id=user_id,
        action="course.reliability",
        entity_type="course",
        entity_id=course.id,
        payload={
            # Les trois valeurs, parce qu'elles ne se déduisent pas l'une de
            # l'autre : « la machine doutait, un humain a tranché l'inverse »
            # est précisément ce qu'une relecture du journal doit pouvoir dire.
            "before": previous,
            "after": verdict,
            "computed": course.is_reliable_computed,
            "notes": notes,
        },
    )
    db.flush()
    return course
