"""Modèles SQLAlchemy. Importer ce package enregistre toutes les tables sur Base.metadata."""
from app.models.athlete import Athlete
from app.models.course import Course
from app.models.identity import Identity
from app.models.participation import Participation
from app.models.pending_provider import PendingProvider
from app.models.user import User
from app.models.user_session import UserSession

__all__ = [
    "Athlete",
    "Course",
    "Identity",
    "Participation",
    "PendingProvider",
    "User",
    "UserSession",
]
