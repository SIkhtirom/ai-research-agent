"""API routes for listing sessions and fetching session detail (sources + messages)."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...core.config import settings
from ...db.crud import DocumentRepository, QueryLogRepository, SessionRepository
from ...db.database import get_db, to_utc_iso
from ...db.vector_store import get_vector_store
from ...schemas.message import (
    SessionDetailResponse,
    SessionDocumentItem,
    SessionMessageItem,
)
from ...schemas.session import SessionCreateResponse, SessionListItem

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sessions", tags=["Sessions"])


@router.get("", response_model=list[SessionListItem])
async def list_sessions(db: Session = Depends(get_db)):
    sessions = SessionRepository().list_by_user(db, settings.default_user_id)
    document_repository = DocumentRepository()
    items = []
    for session in sessions:
        source_count = len(document_repository.list_file_sources(db, session.id))
        items.append(
            SessionListItem(
                id=session.id,
                title=session.title,
                created_at=to_utc_iso(session.created_at),
                source_count=source_count,
            )
        )
    return items


@router.post("", response_model=SessionCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_session(db: Session = Depends(get_db)):
    """Create a brand-new empty session up front. The frontend binds its ID as
    the active session immediately so uploads and chat queries always target the
    freshly created session instead of a stale previously-active one."""
    new_session = SessionRepository().create(
        db, user_id=settings.default_user_id, title="Sesi Riset Baru"
    )
    logger.info("session created session=%s", new_session.id)
    return SessionCreateResponse(
        session_id=new_session.id,
        title=new_session.title,
        created_at=to_utc_iso(new_session.created_at),
    )


@router.delete("")
async def hard_reset(db: Session = Depends(get_db)):
    """Full isolation reset: purge every stored session, document, query log,
    and every vector on disk/FAISS so no remnants from previous runs can ever
    leak into a new session."""
    removed_messages = QueryLogRepository().delete_all(db)
    removed_documents = DocumentRepository().delete_all(db)
    removed_sessions = SessionRepository().delete_all(db)
    get_vector_store().clear()
    logger.info(
        "hard reset complete sessions=%d documents=%d messages=%d",
        removed_sessions,
        removed_documents,
        removed_messages,
    )
    return {
        "success": True,
        "sessions_removed": removed_sessions,
        "documents_removed": removed_documents,
        "messages_removed": removed_messages,
    }


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session_detail(session_id: int, db: Session = Depends(get_db)):
    session = SessionRepository().get_by_id(db, session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' does not exist.",
        )

    document_sources = DocumentRepository().list_file_sources(db, session_id)
    query_logs = QueryLogRepository().list_by_session(db, session_id)

    return SessionDetailResponse(
        session_id=session.id,
        title=session.title,
        documents=[__to_file_item(source) for source in document_sources],
        messages=[__to_message_item(query_log) for query_log in query_logs],
    )


@router.delete("/{session_id}/documents")
async def clear_session_documents(session_id: int, db: Session = Depends(get_db)):
    """Remove all files (documents and their vectors) of a session."""
    session = SessionRepository().get_by_id(db, session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' does not exist.",
        )

    removed = DocumentRepository().delete_by_session(db, session_id)
    get_vector_store().clear_session(session_id)

    return {"success": True, "session_id": session_id, "documents_removed": removed}


@router.delete("/{session_id}/documents/{document_id}")
async def delete_session_document(
    session_id: int, document_id: int, db: Session = Depends(get_db)
):
    """Delete a single uploaded file (all of its chunks and vectors) from a session.
    ``document_id`` is any chunk id belonging to the target file."""
    session = SessionRepository().get_by_id(db, session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' does not exist.",
        )

    repository = DocumentRepository()
    document = repository.get_by_id(db, document_id)
    if document is None or document.session_id != session_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' does not exist in session '{session_id}'.",
        )

    metadata = document.metadata_dict
    if document.source_type == "url" and metadata.get("url"):
        metadata_match = {"url": metadata.get("url")}
    else:
        metadata_match = {"filename": metadata.get("filename")}

    removed = repository.delete_file_members(db, session_id, metadata_match)
    get_vector_store().remove_documents(session_id, metadata_match)

    return {
        "success": True,
        "session_id": session_id,
        "filename": metadata.get("filename"),
        "url": metadata.get("url"),
        "documents_removed": removed,
    }


@router.post("/{session_id}/close")
async def close_session(session_id: int, db: Session = Depends(get_db)):
    """Idempotently remove everything tied to a session (documents, vectors,
    query logs, the session row). Safe to re-fire (e.g. from a calling-page
    keepalive beacon): missing sessions are simply reported as not cleaned."""
    existing = SessionRepository().get_by_id(db, session_id)
    if existing is None:
        return {"success": True, "session_id": session_id, "cleaned": False}

    removed_documents = DocumentRepository().delete_by_session(db, session_id)
    removed_messages = QueryLogRepository().delete_by_session(db, session_id)
    get_vector_store().clear_session(session_id)
    SessionRepository().delete_by_id(db, session_id)
    logger.info(
        "session closed session=%s documents=%d messages=%d",
        session_id,
        removed_documents,
        removed_messages,
    )
    return {
        "success": True,
        "session_id": session_id,
        "cleaned": True,
        "documents_removed": removed_documents,
        "messages_removed": removed_messages,
    }


def __to_file_item(source: dict) -> SessionDocumentItem:
    return SessionDocumentItem(
        id=source["id"],
        source_type=source["source_type"],
        filename=source.get("filename"),
        url=source.get("url"),
        source_name=source.get("source_name"),
        chunk_count=source.get("chunk_count", 0),
        authors=source.get("authors"),
        publication_year=source.get("publication_year"),
        document_number=source.get("document_number"),
        document_label=source.get("document_label"),
    )


def __to_message_item(query_log) -> SessionMessageItem:
    return SessionMessageItem(
        id=query_log.id,
        prompt=query_log.prompt,
        generated_response=query_log.generated_response,
        citations=query_log.citations_list,
    )
