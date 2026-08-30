"""Shared OCR utilities for extracting text from images embedded in documents.

Parsers (PDF, DOCX, PPTX, and URL) call into this module so OCR behaviour stays
consistent across all formats. The Tesseract binary is located automatically on
common install paths; when it is missing the module degrades gracefully and logs
a clear warning so scanned/image-only content is not silently treated as empty.
"""

import io
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image

logger = logging.getLogger(__name__)

_TESSERACT_CANDIDATES = [
    "tesseract",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    "/usr/bin/tesseract",
    "/usr/local/bin/tesseract",
]


def _resolve_tesseract_cmd() -> str | None:
    """Return an available tesseract executable path, or None."""
    for candidate in _TESSERACT_CANDIDATES:
        if candidate == "tesseract":
            resolved = shutil.which("tesseract")
            if resolved:
                return resolved
        elif Path(candidate).exists():
            return candidate
    return None


_ocr_available: bool | None = None
_tesseract_path: str | None = None


def _probe_ocr() -> bool:
    """Detect once whether the Tesseract engine is usable."""
    global _ocr_available, _tesseract_path
    if _ocr_available is not None:
        return _ocr_available
    try:
        import pytesseract

        tesseract_path = _resolve_tesseract_cmd()
        if tesseract_path is None:
            _ocr_available = False
            return False
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
        pytesseract.get_tesseract_version()
        _tesseract_path = tesseract_path
        _ocr_available = True
        return True
    except Exception:  # noqa: BLE001 - any failure means OCR is unavailable
        _ocr_available = False
        return False


def is_ocr_available() -> bool:
    """Return True when Tesseract can actually be invoked."""
    return _probe_ocr()


def ocr_image(image: Image.Image, lang: str = "eng") -> str:
    """Run OCR on a PIL image and return trimmed text ('' when unavailable)."""
    if not _probe_ocr():
        logger.warning(
            "OCR is not available (Tesseract engine not found). Install Tesseract OCR "
            "for image/scan extraction."
        )
        return ""
    try:
        import pytesseract

        if _tesseract_path is not None:
            pytesseract.pytesseract.tesseract_cmd = _tesseract_path
        if image.mode != "RGB":
            image = image.convert("RGB")
        return pytesseract.image_to_string(image, lang=lang).strip()
    except Exception as exc:  # noqa: BLE001 - OCR is best-effort
        logger.warning("OCR failed for an image: %s", exc)
        return ""


def ocr_image_bytes(data: bytes, lang: str = "eng") -> str:
    """Open image bytes and OCR them, returning '' on any failure."""
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
        return ocr_image(image, lang=lang)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not read image bytes for OCR: %s", exc)
        return ""


def ocr_pdf_pages(source: Path | str, scale: float = 2.0, lang: str = "eng") -> list[str]:
    """Render each page of a PDF and OCR it, returning one text per page.

    Requires pypdfium2; returns an empty list when rendering is unavailable.
    """
    if not _probe_ocr():
        logger.warning("OCR skipped for PDF '%s': Tesseract engine not found.", Path(source).name)
        return []
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:  # noqa: BLE001
        logger.warning("OCR skipped for PDF '%s': pypdfium2 not installed (%s)", Path(source).name, exc)
        return []

    try:
        pdf = pdfium.PdfDocument(str(source))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not open PDF '%s' for OCR: %s", Path(source).name, exc)
        return []

    page_texts: list[str] = []
    try:
        for page in pdf:
            bitmap = page.render(scale=scale)
            image = bitmap.to_pil().convert("RGB")
            page_texts.append(ocr_image(image, lang=lang))
    except Exception as exc:  # noqa: BLE001
        logger.warning("OCR failed while processing PDF '%s': %s", Path(source).name, exc)
        return []
    finally:
        pdf.close()
    return page_texts


def extract_images_from_zip(zip_path: Path, extensions=(".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")) -> list[bytes]:
    """Extract embedded image bytes from an Office (zip) package.

    Used by the DOCX/PPTX parsers to surface text that lives inside pictures.
    """
    import zipfile

    images: list[bytes] = []
    try:
        with zipfile.ZipFile(zip_path) as archive:
            for name in archive.namelist():
                lower = name.lower()
                if lower.startswith(("word/media/", "ppt/media/")) and lower.endswith(
                    extensions
                ):
                    images.append(archive.read(name))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not extract embedded images from '%s': %s", zip_path.name, exc)
        return []
    return images
