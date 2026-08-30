"""API routes for ingesting files and URLs."""

import logging
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...schemas.ingestion import (
    FileIngestItem,
    IngestionResponse,
    MultiIngestResponse,
    UrlIngestionRequest,
)
from ...services.ingestion.ingestion_service import IngestionService
from ...services.ingestion.parsers.base_parser import ExtractedDocument
from ...services.ingestion.security import (
    UNIFORM_ERROR_MESSAGE,
    ContentScanner,
    FileSignatureValidator,
    ValidationError,
)
from ..dependencies import get_ingestion_service, resolve_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ingest", tags=["Ingestion"])

ALLOWED_FILE_EXTENSIONS = {".pdf", ".docx", ".pptx", ".txt"}

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB per file

_signature_validator = FileSignatureValidator()
_content_scanner = ContentScanner()

# Characters never allowed in a stored name, regardless of source, because they
# enable path traversal or terminal/control abuse.
_DANGEROUS_FILENAME_CHARS = str.maketrans({"/": "_", "\\": "_"})


def _sanitize_filename(filename: str | None) -> str:
    """Return a safe *display/metadata* name while preserving as much of the
    original filename as possible.

    Only genuinely dangerous components are removed:
      - path separators ``/`` and ``\\`` (path traversal)
      - the null byte and other C0/C1 control characters
    Everything else — spaces, brackets, commas, dots, symbols, unicode, emoji —
    is kept verbatim, so a legitimate file from any source that happens to use
    unique or unusual characters is never mangled or rejected.

    The sanitized name is only used for metadata/display and delete-matching; the
    on-disk file itself is always written to an auto-generated temp path, so the
    name never carries filesystem risk.
    """
    if not filename:
        return "document"

    # Collapse any directory components (both separators) so a traversal string
    # like ``../../etc/passwd.pdf`` becomes just ``passwd.pdf``.
    base = filename.replace("\\", "/").rsplit("/", 1)[-1]
    # At this point no separator can remain; replace any leftover with a safe char
    # and drop null/control characters entirely.
    base = base.translate(_DANGEROUS_FILENAME_CHARS)
    base = "".join(ch for ch in base if ch >= " " and ch != "\x7f")

    # Strip surrounding whitespace and degenerate dot-only names.
    base = base.strip().strip(".")
    if not base or base in (".", ".."):
        return "document"

    # Cap absurdly long names so stored metadata stays sane.
    if len(base) > 255:
        base = base[:255]
    return base


def _validate_file(file: UploadFile) -> str:
    """Validate a single uploaded file against the extension whitelist.

    Raises a 415 with the uniform error message when the extension is not
    one of PDF/DOCX/PPTX/TXT.
    """
    original_name = file.filename or ""
    file_extension = Path(original_name).suffix.lower()
    if file_extension not in ALLOWED_FILE_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=UNIFORM_ERROR_MESSAGE,
        )
    return file_extension


async def _read_and_verify(file: UploadFile, file_extension: str) -> bytes:
    """Read an upload with a size limit and verify its actual magic bytes.

    Raises a 413 when too large, or a 422 with the uniform message when the
    bytes do not match the declared extension (format forgery).
    """
    data = await file.read(MAX_FILE_SIZE_BYTES + 1)
    if len(data) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File '{file.filename}' exceeds the {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB size limit.",
        )
    try:
        _signature_validator.validate(file_extension, data)
    except ValidationError as error:
        logger.warning("Signature validation failed: %s", error)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=UNIFORM_ERROR_MESSAGE,
        ) from error
    return data


def _write_temp(file_extension: str, data: bytes) -> Path:
    """Persist upload bytes to a safe temp file and return its path."""
    temp_dir = Path(tempfile.gettempdir()) / "ai-research-ingest"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_file = tempfile.NamedTemporaryFile(
        dir=temp_dir, suffix=file_extension, delete=False
    )
    try:
        temp_file.write(data)
    finally:
        temp_file.close()
    return Path(temp_file.name)


@router.post("/file", response_model=IngestionResponse, status_code=status.HTTP_201_CREATED)
async def ingest_file(
    file: Annotated[UploadFile, File(description="Supported: pdf, docx, pptx, txt")],
    db: Session = Depends(get_db),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
    session_id: int | None = None,
):
    file_extension = _validate_file(file)
    safe_name = _sanitize_filename(file.filename or "document")
    temporary_path = _write_temp(file_extension, await _read_and_verify(file, file_extension))

    try:
        # Parse and scan content BEFORE resolving/creating a session so a rejected
        # file never creates an empty session or records anything to history.
        extracted_document = ingestion_service.extract_and_scan(
            temporary_path, text_scanner=_content_scanner
        )
        resolved_session_id = resolve_session(
            db, session_id, default_title=f"Research on {Path(safe_name).stem}"
        )
        document_ids = ingestion_service.ingest(
            db,
            temporary_path,
            resolved_session_id,
            source_type=file_extension.lstrip("."),
            source_name=safe_name,
            text_scanner=_content_scanner,
            pre_extracted=extracted_document,
        )
    except ValidationError as error:
        logger.warning("Content scan blocked file '%s': %s", safe_name, error)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=UNIFORM_ERROR_MESSAGE,
        ) from error
    except Exception as error:
        logger.error("Failed to ingest file '%s': %s", safe_name, error)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=UNIFORM_ERROR_MESSAGE,
        ) from error
    finally:
        temporary_path.unlink(missing_ok=True)

    return IngestionResponse(
        success=True,
        message=f"Successfully ingested {safe_name}",
        session_id=resolved_session_id,
        document_ids=document_ids,
        metadata={"filename": safe_name, "source_type": file_extension.lstrip(".")},
    )


@router.post("/files", response_model=MultiIngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_files(
    files: Annotated[list[UploadFile], File(description="Multiple files at once")],
    db: Session = Depends(get_db),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
    session_id: int | None = None,
):
    """Upload many files at once. All files are merged and processed into ONE
    session so users can discuss them collectively."""
    if not files:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one file is required.",
        )

    file_results: list[FileIngestItem] = []

    # Phase 1: validate every file (extension, magic bytes, content scan) and
    # build a prepared list WITHOUT touching any session. Files that fail any
    # check are rejected immediately and never create or contaminate history.
    prepared: list[tuple[str, str, ExtractedDocument, Path]] = []
    for file in files:
        failure: str | None = None
        temporary_path: Path | None = None
        try:
            file_extension = _validate_file(file)
            safe_name = _sanitize_filename(file.filename or "document")
            temporary_path = _write_temp(
                file_extension, await _read_and_verify(file, file_extension)
            )
            extracted_document = ingestion_service.extract_and_scan(
                temporary_path, text_scanner=_content_scanner
            )
        except HTTPException as error:
            failure = error.detail
        except ValidationError:
            failure = UNIFORM_ERROR_MESSAGE
        except Exception as error:
            logger.error("Validation failed for '%s': %s", getattr(file, "filename", "?"), error)
            failure = UNIFORM_ERROR_MESSAGE
        if failure is not None:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            file_results.append(
                FileIngestItem(
                    filename=_sanitize_filename(file.filename or "document"),
                    success=False,
                    message=failure,
                    document_ids=[],
                )
            )
            continue
        # Defer deletion: the temp file is still needed by Phase 2 ingestion.
        prepared.append((safe_name, file_extension, extracted_document, temporary_path))

    # Phase 2: only a request with at least one valid file creates/uses a session,
    # keeping history clean when every file was rejected.
    if not prepared:
        return MultiIngestResponse(success=False, session_id=0, files=file_results)

    first_filename = Path(prepared[0][0]).stem
    resolved_session_id = resolve_session(
        db, session_id, default_title=f"Research on {first_filename}"
    )

    any_success = False
    for safe_name, file_extension, extracted_document, temporary_path in prepared:
        try:
            document_ids = ingestion_service.ingest(
                db,
                temporary_path,
                resolved_session_id,
                source_type=file_extension.lstrip("."),
                source_name=safe_name,
                text_scanner=_content_scanner,
                pre_extracted=extracted_document,
            )
            any_success = True
            file_results.append(
                FileIngestItem(
                    filename=safe_name,
                    success=True,
                    message="Berhasil diproses.",
                    document_ids=document_ids,
                )
            )
        except Exception as error:
            logger.error("Failed to ingest file '%s': %s", safe_name, error)
            file_results.append(
                FileIngestItem(
                    filename=safe_name,
                    success=False,
                    message=UNIFORM_ERROR_MESSAGE,
                    document_ids=[],
                )
            )
        finally:
            temporary_path.unlink(missing_ok=True)

    return MultiIngestResponse(
        success=any_success,
        session_id=resolved_session_id,
        files=file_results,
    )


@router.post("/url", response_model=IngestionResponse, status_code=status.HTTP_201_CREATED)
async def ingest_url(
    request: UrlIngestionRequest,
    db: Session = Depends(get_db),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
):
    url = str(request.url)
    try:
        # Fetch + scan content before creating/using a session so a rejected URL
        # (blocked/SSRF/malicious content) never records anything to history.
        extracted_document = ingestion_service.extract_and_scan(
            url, text_scanner=_content_scanner
        )
        resolved_session_id = resolve_session(
            db, request.session_id, default_title=f"Research on {url}"
        )
        document_ids = ingestion_service.ingest(
            db,
            url,
            resolved_session_id,
            source_type="url",
            text_scanner=_content_scanner,
            pre_extracted=extracted_document,
        )
    except ValidationError as error:
        logger.warning("Content scan blocked URL '%s': %s", url, error)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=UNIFORM_ERROR_MESSAGE,
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except Exception as error:
        logger.error("Failed to ingest URL '%s': %s", url, error)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=UNIFORM_ERROR_MESSAGE,
        ) from error

    return IngestionResponse(
        success=True,
        message=f"Successfully ingested {url}",
        session_id=resolved_session_id,
        document_ids=document_ids,
        metadata={"url": url, "source_type": "url"},
    )
