"""Charger une fiche par son id, sinon 404 : un seul garde par entité (#1584)."""
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.athlete import Athlete
from app.models.course import Course
from app.models.user import User
from app.repositories import athlete_repository, course_repository, user_repository


def athlete_or_404(
    db: Session, athlete_id: int, *, hide_pending_only: bool, message: str = "Athlète introuvable."
) -> Athlete:
    athlete = athlete_repository.get(db, athlete_id, hide_pending_only=hide_pending_only)
    if athlete is None:
        raise NotFoundError(message)
    return athlete


def course_or_404(
    db: Session, course_id: int, *, hide_pending_only: bool, message: str = "Épreuve introuvable."
) -> Course:
    course = course_repository.get(db, course_id, hide_pending_only=hide_pending_only)
    if course is None:
        raise NotFoundError(message)
    return course


def user_or_404(db: Session, user_id: int) -> User:
    user = user_repository.get(db, user_id)
    if user is None:
        raise NotFoundError("Cet utilisateur n'existe pas.")
    return user
