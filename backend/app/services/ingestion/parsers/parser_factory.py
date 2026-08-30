"""Factory that resolves the matching parser from a source type."""

from pathlib import Path

from .base_parser import DocumentParser
from .pdf_parser import PdfParser
from .docx_parser import DocxParser
from .pptx_parser import PptxParser
from .txt_parser import TxtParser
from .url_scraper import UrlScraper

SUPPORTED_FILE_EXTENSIONS = {
    ".pdf": PdfParser,
    ".docx": DocxParser,
    ".pptx": PptxParser,
    ".txt": TxtParser,
}


def detect_source_type(source: Path | str) -> str:
    """Return the source type key ('pdf'|'docx'|'pptx'|'txt'|'url')."""
    if str(source).lower().startswith(("http://", "https://")):
        return "url"
    extension = Path(source).suffix.lower()
    if extension not in SUPPORTED_FILE_EXTENSIONS:
        raise ValueError(f"Unsupported file extension: {extension}")
    return extension.lstrip(".")


def get_parser(source: Path | str) -> DocumentParser:
    """Instantiate the parser matching the detected source type."""
    source_type = detect_source_type(source)
    if source_type == "url":
        return UrlScraper()
    parser_class = SUPPORTED_FILE_EXTENSIONS[f".{source_type}"]
    return parser_class()
