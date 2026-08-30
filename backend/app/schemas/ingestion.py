"""Request and response models for the ingestion endpoints."""

from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class UrlIngestionRequest(BaseModel):
    url: HttpUrl
    session_id: int | None = Field(default=None, description="Optional existing session id.")


class IngestionResponse(BaseModel):
    success: bool
    message: str
    session_id: int
    document_ids: list[str]
    metadata: dict[str, Any]


class FileIngestItem(BaseModel):
    filename: str
    success: bool
    message: str
    document_ids: list[str]


class MultiIngestResponse(BaseModel):
    success: bool
    session_id: int
    files: list[FileIngestItem]
