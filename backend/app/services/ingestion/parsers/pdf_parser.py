"""PDF text extraction using pypdf, page-aware so no early page is dropped.

For scanned/image-heavy PDFs (e.g. thick undergraduate theses) the parser also
runs OCR: full-page OCR when a page has no extractable text, and OCR of embedded
images on otherwise text-bearing pages. This keeps diagrams/captions/images from
being silently lost while preserving strict page ordering.
"""

import logging
from pathlib import Path

from pypdf import PdfReader

from .base_parser import DocumentParser, ExtractedDocument
from .ocr import is_ocr_available, ocr_image_bytes, ocr_pdf_pages

logger = logging.getLogger(__name__)

_MIN_TEXT_FOR_REAL_DOCUMENT = 20


class PdfParser(DocumentParser):
    def parse(self, source: Path | str) -> ExtractedDocument:
        source_path = Path(source)
        reader = PdfReader(source_path)

        pages: list[str] = []
        for page in reader.pages:
            page_text = (page.extract_text() or "").strip()
            embedded_text = self.__ocr_embedded_images(page)
            if embedded_text:
                page_text = f"{page_text}\n{embedded_text}" if page_text else embedded_text
            pages.append(page_text.strip())

        extracted_text_length = sum(len(page_text) for page_text in pages)
        ocr_full_pages_used = False

        if extracted_text_length < _MIN_TEXT_FOR_REAL_DOCUMENT:
            ocr_text_pages = ocr_pdf_pages(source_path)
            if ocr_text_pages and any(text.strip() for text in ocr_text_pages):
                ocr_full_pages_used = True
                pages = [text.strip() for text in ocr_text_pages]
            else:
                logger.warning(
                    "PDF '%s' appears to be scanned/image-only and OCR produced no text. "
                    "Ensure Tesseract OCR is installed and on PATH to index scanned pages.",
                    source_path.name,
                )

        page_markers: list[str] = []
        extracted_non_empty_pages = 0
        for index, page_text in enumerate(pages, start=1):
            if page_text.strip():
                extracted_non_empty_pages += 1
            joined = page_text if page_text.strip() else "(halaman tanpa teks terdeteksi)"
            page_markers.append(f"[Halaman {index}]\n{joined}")

        content_text = "\n\n".join(page_markers)
        metadata = {
            "filename": source_path.name,
            "page_count": len(reader.pages),
            "extracted_page_count": extracted_non_empty_pages,
            "ocr_available": is_ocr_available(),
            "ocr_used": ocr_full_pages_used,
            "scanned": extracted_text_length < _MIN_TEXT_FOR_REAL_DOCUMENT,
        }
        return ExtractedDocument(
            content_text=content_text,
            metadata=metadata,
            pages=pages,
        )

    def __ocr_embedded_images(self, page) -> str:
        """OCR images embedded directly on a PDF page (best-effort)."""
        texts: list[str] = []
        try:
            for image_file_object in page.images:
                data = getattr(image_file_object, "data", None)
                if data:
                    ocr_text = ocr_image_bytes(data)
                    if ocr_text:
                        texts.append(f"(OCR: {ocr_text})")
        except Exception as exc:  # noqa: BLE001 - best-effort image OCR
            logger.debug("Embedded image OCR skipped for a page: %s", exc)
        return "\n".join(texts)
