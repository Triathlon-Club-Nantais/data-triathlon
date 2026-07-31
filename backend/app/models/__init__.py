"""Modèles SQLAlchemy. Importer ce package enregistre toutes les tables sur Base.metadata."""
from app.models.athlete import Athlete
from app.models.course import Course
from app.models.participation import Participation
from app.models.pending_provider import PendingProvider
from app.models.user import User

__all__ = ["Athlete", "Course", "Participation", "PendingProvider", "User"]
