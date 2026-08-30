"""Request and response models for the chat/query endpoint."""

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str
    session_id: int | None = Field(default=None, description="Optional existing session id.")


class ChatResponse(BaseModel):
    session_id: int
    generated_response: str
    citations: list[dict[str, Any]]
    include_citations: bool = False
    comparison_mode: bool = False
