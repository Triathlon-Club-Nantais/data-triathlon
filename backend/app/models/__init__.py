"""Modèles SQLAlchemy. Importer ce package enregistre toutes les tables sur Base.metadata."""
from app.models.athlete import Athlete
from app.models.course import Course
from app.models.identity import Identity
from app.models.organisation import Organisation
from app.models.participation import Participation
from app.models.pending_provider import PendingProvider
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.user import User
from app.models.user_role import UserRole
from app.models.user_session import UserSession

__all__ = [
    "Athlete",
    "Course",
    "Identity",
    "Organisation",
    "Participation",
    "PendingProvider",
    "Role",
    "RolePermission",
    "User",
    "UserRole",
    "UserSession",
]
