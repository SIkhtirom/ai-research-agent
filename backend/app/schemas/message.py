"""Response models for a session's source documents and message history."""

from typing import Any

from pydantic import BaseModel


class SessionDocumentItem(BaseModel):
    id: int
    source_type: str
    filename: str | None = None
    url: str | None = None
    source_name: str | None = None
    chunk_count: int = 0


class SessionMessageItem(BaseModel):
    id: int
    prompt: str
    generated_response: str
    citations: list[dict[str, Any]]


class SessionDetailResponse(BaseModel):
    session_id: int
    title: str
    documents: list[SessionDocumentItem]
    messages: list[SessionMessageItem]
