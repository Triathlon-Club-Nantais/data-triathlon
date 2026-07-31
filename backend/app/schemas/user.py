"""DTO for the User model (issue #114)."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_serializer


class UserRead(BaseModel):
    """Public view of a User. `github_id` is a technical identifier and is not exposed."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    github_login: str
    created_at: datetime

    @field_serializer("created_at")
    def _serialize_created_at(self, value: datetime) -> str:
        """Emit `…Z` so JS `new Date()` reads it as UTC, matching the contract.

        `app.core.time.utcnow` returns a naive UTC datetime (convention of this
        project) — appending `Z` is the right marker to make it unambiguous
        client-side.
        """
        return value.isoformat(timespec="microseconds") + "Z"
