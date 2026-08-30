"""API route for exporting a session's Q&A history as md, pdf, or pptx."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...services.export.export_service import ExportService

router = APIRouter(prefix="/api/v1/export", tags=["Export"])

export_service = ExportService()

logger = logging.getLogger(__name__)


@router.get("/{session_id}")
async def export_session(
    session_id: int,
    format: str = Query(default="md", pattern="^(md|pdf|pptx)$"),
    db: Session = Depends(get_db),
):
    try:
        export_result = export_service.export_session_data(db, session_id, format)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error
    except Exception as error:
        logger.error("Failed to export session %s: %s", session_id, error)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal mengekspor sesi. Silakan coba lagi.",
        ) from error

    headers = {"Content-Disposition": f'attachment; filename="{export_result["filename"]}"'}
    return Response(
        content=export_result["bytes"],
        media_type=export_result["media_type"],
        headers=headers,
    )
