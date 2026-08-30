"""Response models for session listing."""

from pydantic import BaseModel


class SessionListItem(BaseModel):
    id: int
    title: str
    created_at: str
    source_count: int
