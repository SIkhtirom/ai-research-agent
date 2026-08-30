"""Lazily-initialised singletons and shared helper dependencies."""

from functools import lru_cache

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..core.config import settings
from ..db.crud import SessionRepository
from ..services.ingestion.ingestion_service import IngestionService
from ..services.rag.rag_service import RAGService


@lru_cache
def get_ingestion_service() -> IngestionService:
    return IngestionService()


@lru_cache
def get_rag_service() -> RAGService:
    return RAGService()


def resolve_session(
    db: Session, requested_session_id: int | None, default_title: str
) -> int:
    """Return the requested session id or create a new session when none is provided."""
    if requested_session_id is not None:
        existing = SessionRepository().get_by_id(db, requested_session_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session '{requested_session_id}' does not exist.",
            )
        return requested_session_id
    new_session = SessionRepository().create(
        db, user_id=settings.default_user_id, title=default_title
    )
    # A brand-new session is isolated from previous ones naturally because retrieval
    # is scoped by session_id. History is deliberately retained in the vector store
    # so a later explicit "compare with previous journal" request can pull it back.
    return new_session.id
