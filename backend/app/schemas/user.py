"""DTO for the User model (issue #114)."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserRead(BaseModel):
    """Public view of a User. `github_id` is a technical identifier and is not exposed."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    github_login: str
    created_at: datetime
