"""Accès données pour IgnoredCourseDuplicate — seule couche qui touche la Session (Principe II).

L'existence de la ligne porte la décision (patron `season_validation_repository`) :
`create` écarte une paire (#754), `delete` annule la mise à l'écart (#1243).
"""
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, aliased

from app.models.course import Course
from app.models.ignored_course_duplicate import IgnoredCourseDuplicate


def _paire(course_id_a: int, course_id_b: int) -> tuple[int, int]:
    """La paire normalisée, le plus petit id en premier.

    Rien ne garantit que l'appelant envoie toujours le même côté de la paire
    en premier : normaliser ici est ce qui rend `exists` et `create`
    indifférents à l'ordre reçu.
    """
    return (course_id_a, course_id_b) if course_id_a < course_id_b else (course_id_b, course_id_a)


def create(
    db: Session, *, course_id_a: int, course_id_b: int, user_id: int
) -> IgnoredCourseDuplicate:
    low, high = _paire(course_id_a, course_id_b)
    ignoree = IgnoredCourseDuplicate(
        course_id_low=low, course_id_high=high, ignored_by_user_id=user_id
    )
    db.add(ignoree)
    db.flush()
    return ignoree


def exists(db: Session, *, course_id_a: int, course_id_b: int) -> bool:
    low, high = _paire(course_id_a, course_id_b)
    return (
        db.query(IgnoredCourseDuplicate.id)
        .filter(
            IgnoredCourseDuplicate.course_id_low == low,
            IgnoredCourseDuplicate.course_id_high == high,
        )
        .first()
        is not None
    )


def get(db: Session, pair_id: int) -> IgnoredCourseDuplicate | None:
    return db.get(IgnoredCourseDuplicate, pair_id)


def delete(db: Session, pair: IgnoredCourseDuplicate) -> None:
    db.delete(pair)
    db.flush()


def list_with_courses(db: Session) -> list[tuple[IgnoredCourseDuplicate, Course, Course]]:
    """Les paires écartées et leurs deux épreuves, la plus récente d'abord (#1243)."""
    low, high = aliased(Course), aliased(Course)
    return [
        tuple(row)
        for row in db.execute(
            select(IgnoredCourseDuplicate, low, high)
            .join(low, low.id == IgnoredCourseDuplicate.course_id_low)
            .join(high, high.id == IgnoredCourseDuplicate.course_id_high)
            .order_by(IgnoredCourseDuplicate.ignored_at.desc(), IgnoredCourseDuplicate.id.desc())
        )
    ]


def all_pairs(db: Session) -> set[tuple[int, int]]:
    """Toutes les paires ignorées, en une seule requête.

    C'est ce qui laisse `course_duplicates.find_candidates` filtrer sans
    ouvrir une requête par paire candidate (même exigence de constance que
    `list_identities_with_counts`, cf. AC5 de #288).
    """
    lignes = db.query(
        IgnoredCourseDuplicate.course_id_low, IgnoredCourseDuplicate.course_id_high
    ).all()
    return {(low, high) for low, high in lignes}


def delete_for_course(db: Session, course_id: int) -> None:
    """Retire les paires ignorées où `course_id` apparaît, d'un côté ou de l'autre.

    **À appeler avant toute suppression d'une `Course`** (`course_repository.delete`,
    et par elle la fusion de #287) : aucun `ondelete` n'est posé sur
    `course_id_low`/`course_id_high` — même parti pris que `course_sources.course_id`,
    documenté dans `course_repository.delete` — et rien sur `Course` ne porte de
    relation `cascade="all, delete-orphan"` vers cette table, contrairement à
    `sources`. Sans cet appel, la ligne survivrait à l'épreuve qu'elle référence :
    invisible en SQLite (aucun `PRAGMA foreign_keys=ON`, cf. `database.py`), mais
    un `ForeignKeyViolation` en PostgreSQL.
    """
    db.query(IgnoredCourseDuplicate).filter(
        or_(
            IgnoredCourseDuplicate.course_id_low == course_id,
            IgnoredCourseDuplicate.course_id_high == course_id,
        )
    ).delete(synchronize_session=False)


def delete_all(db: Session) -> None:
    """Vide la table entière — pendant de `course_repository.delete_all` (#384).

    Même raison que `delete_for_course` : sans elle, « Supprimer toutes les
    épreuves » laisserait des lignes pointant vers des `courses.id` qui
    n'existent plus, et le `DELETE` de masse sur `courses` échouerait dès
    qu'une seule paire aurait été ignorée.
    """
    db.query(IgnoredCourseDuplicate).delete(synchronize_session=False)
