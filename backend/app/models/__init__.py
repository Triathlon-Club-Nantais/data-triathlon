"""Modèles SQLAlchemy. Importer ce package enregistre toutes les tables sur Base.metadata."""
from app.models.admin_action_log import AdminActionLog
from app.models.allowed_email import AllowedEmail
from app.models.athlete import Athlete
from app.models.benevole_access_config import BenevoleAccessConfig
from app.models.counter_scope_entry import CounterScopeEntry
from app.models.course import Course
from app.models.course_source import CourseSource
from app.models.group import Group
from app.models.identity import Identity
from app.models.organisation import Organisation
from app.models.participation import Participation
from app.models.pending_provider import PendingProvider
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.season_validation import SeasonValidation
from app.models.site_access_config import SiteAccessConfig
from app.models.user import User
from app.models.user_feedback import UserFeedback
from app.models.user_group import UserGroup
from app.models.user_role import UserRole
from app.models.user_session import UserSession
from app.models.volunteer_action import VolunteerAction

__all__ = [
    "AdminActionLog",
    "AllowedEmail",
    "Athlete",
    "BenevoleAccessConfig",
    "CounterScopeEntry",
    "Course",
    "CourseSource",
    "Group",
    "Identity",
    "Organisation",
    "Participation",
    "PendingProvider",
    "Role",
    "RolePermission",
    "SeasonValidation",
    "SiteAccessConfig",
    "User",
    "UserFeedback",
    "UserGroup",
    "UserRole",
    "UserSession",
    "VolunteerAction",
]
