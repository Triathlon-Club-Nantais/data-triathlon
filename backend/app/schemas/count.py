from pydantic import BaseModel


class QueueCount(BaseModel):
    """The size of a work queue, for its nav badge (#1232)."""

    total: int
