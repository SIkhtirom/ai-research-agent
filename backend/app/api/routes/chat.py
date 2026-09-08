"""API route for asking the RAG assistant a query."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...schemas.chat import ChatRequest, ChatResponse
from ...services.rag.rag_service import RAGService
from ..dependencies import get_rag_service, resolve_session

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])

logger = logging.getLogger(__name__)


def _serialise_sse(payload: dict) -> str:
    """Encode a dict as one Server-Sent Events data frame."""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/query", response_model=ChatResponse)
def answer_query(
    request: ChatRequest,
    db: Session = Depends(get_db),
    rag_service: RAGService = Depends(get_rag_service),
):
    if not request.query.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query must not be empty.",
        )
    resolved_session_id = resolve_session(
        db, request.session_id, default_title=request.query.strip()[:80]
    )
    try:
        result = rag_service.generate_answer(
            db, request.query.strip(), resolved_session_id
        )
    except Exception as error:
        logger.error("Failed to generate answer for session %s: %s", resolved_session_id, error)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal menghasilkan jawaban. Silakan coba lagi.",
        ) from error
    return ChatResponse(
        session_id=resolved_session_id,
        generated_response=result["generated_response"],
        citations=result["citations"],
        include_citations=result["include_citations"],
        comparison_mode=result["comparison_mode"],
    )


@router.post("/query/stream")
def stream_answer_query(
    request: ChatRequest,
    db: Session = Depends(get_db),
    rag_service: RAGService = Depends(get_rag_service),
):
    """SSE endpoint: answer chunks arrive incrementally for real-time rendering."""
    if not request.query.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query must not be empty.",
        )
    resolved_session_id = resolve_session(
        db, request.session_id, default_title=request.query.strip()[:80]
    )

    def event_source():
        try:
            for payload in rag_service.stream_answer(
                db, request.query.strip(), resolved_session_id
            ):
                yield _serialise_sse(payload)
        except Exception as error:
            logger.error(
                "Failed to stream answer for session %s: %s",
                resolved_session_id,
                error,
            )
            yield _serialise_sse({"error": "Gagal menghasilkan jawaban. Silakan coba lagi."})

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
