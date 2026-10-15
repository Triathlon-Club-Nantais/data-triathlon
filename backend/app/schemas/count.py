from pydantic import BaseModel


class QueueCount(BaseModel):
    """The size of a work queue, for its nav badge (#1232)."""

    total: int


class BadgeCounts(BaseModel):
    """The admin rail badges (#1385). A badge the session cannot see is absent."""

    quality: int | None = None
    duplicates: int | None = None
    providers: int | None = None
    feedback: int | None = None
    identities: int | None = None
    members: int | None = None
    volunteer: int | None = None
    validation: int | None = None
