"""API routes for listing sessions and fetching session detail (sources + messages)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...core.config import settings
from ...db.crud import DocumentRepository, QueryLogRepository, SessionRepository
from ...db.database import get_db
from ...db.vector_store import get_vector_store
from ...schemas.message import (
    SessionDetailResponse,
    SessionDocumentItem,
    SessionMessageItem,
)
from ...schemas.session import SessionListItem

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
                created_at=session.created_at.isoformat(),
                source_count=source_count,
            )
        )
    return items


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


def __to_file_item(source: dict) -> SessionDocumentItem:
    return SessionDocumentItem(
        id=source["id"],
        source_type=source["source_type"],
        filename=source.get("filename"),
        url=source.get("url"),
        source_name=source.get("source_name"),
        chunk_count=source.get("chunk_count", 0),
    )


def __to_message_item(query_log) -> SessionMessageItem:
    return SessionMessageItem(
        id=query_log.id,
        prompt=query_log.prompt,
        generated_response=query_log.generated_response,
        citations=query_log.citations_list,
    )
