"""Best-effort bibliographic metadata extraction from ingested document text.

Pulls author names, publication year, title, journal name, volume, issue, pages,
and DOI out of the opening text of a parsed source so every chunk indexed in the
vector store inherits the metadata that keeps narrative in-text citations and
APA-style references accurate.
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_YEAR_RE = re.compile(r"(?<![\d])((?:19|20)\d{2})(?![\d])")
_VOLUME_RE = re.compile(r"Vol\.?\s*([A-Za-z\d]+)", re.IGNORECASE)
_ISSUE_RE = re.compile(r"(?:No\.?|Issue|Iss\.?)\s*([A-Za-z\d]+)", re.IGNORECASE)
_PAGES_RE = re.compile(
    r"(?:pp?\.?|p\.?|halaman|hal\.?)\s*(\d+)\s*(?:-|–|—)\s*(\d+)",
    re.IGNORECASE,
)
_DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
_EMAIL_RE = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
_NAME_TOKEN_RE = re.compile(r"^[A-Z][A-Za-z'.]+$")

_AUTHOR_BLOCKING_SUBSTRINGS = (
    " the ", " of ", " for ", " and ", " with ", " dan ", " untuk ", " pada ",
    " dalam ", " yang ", " dari ", " tentang ", " melalui ", " jurnal ",
    " journal ", " issn", " abstrak", " abstract", " keywords", " kata kunci",
    " universitas", " institut", " prodi ", " fakultas", " submitted",
    " received", " accepted", " email", " corresponding", " copyright",
)

_MAX_AUTHOR_LINE_CHARS = 160
_MAX_AUTHOR_LINE_WORDS = 10


def extract_bibliography(
    content_text: str,
    pages: list[str] | None = None,
    source_type: str = "pdf",
    existing_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return detected bibliographic fields as a flat dict of metadata keys.

    Every field is best-effort: only keys that can be detected with reasonable
    confidence are returned. ``existing_metadata`` lets callers keep
    authoritative values (e.g. DOCX core properties or the page title) by
    merging these detected values first.
    """
    lead = _lead_text(content_text, pages)
    fields: dict[str, Any] = {}

    year_match = _YEAR_RE.search(lead[:1500])
    if year_match:
        fields["publication_year"] = year_match.group(1)

    doi_match = _DOI_RE.search(lead)
    if doi_match:
        fields["doi"] = doi_match.group(0).rstrip(".,;")

    journal_info = _journal_info(lead)
    if journal_info:
        if journal_info["journal"]:
            fields["journal_name"] = journal_info["journal"]
        if journal_info["volume"]:
            fields["volume"] = journal_info["volume"]
        if journal_info["issue"]:
            fields["issue"] = journal_info["issue"]
        if journal_info["pages"]:
            fields["pages"] = journal_info["pages"]

    authors = _detect_authors(lead, existing_metadata or {})
    if authors:
        fields["authors"] = authors

    title = _detect_title(lead, existing_metadata or {})
    if title:
        fields["title"] = title

    if fields:
        logger.debug(
            "bibliography extracted source_type=%s fields=%s",
            source_type,
            sorted(fields),
        )
    return fields


def _lead_text(content_text: str, pages: list[str] | None) -> str:
    """Return the cleaned opening block (first page for page-aware parsers)."""
    text = ""
    if pages:
        text = next((page for page in pages if page.strip()), "") or ""
    if not text:
        text = content_text or ""
    text = text[:8000]
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _EMAIL_RE.search(line):
            continue
        lines.append(line)
    return "\n".join(lines)


def _journal_info(lead_text: str) -> dict[str, Any] | None:
    """Find the line carrying journal + volume + issue and related page range."""
    for line in lead_text.splitlines():
        if len(line) > 300:
            continue
        lowered = line.lower()
        if (
            "jurnal" not in lowered
            and "journal" not in lowered
            and "vol." not in lowered
        ):
            continue
        volume_match = _VOLUME_RE.search(line)
        if not volume_match:
            continue
        issue_match = _ISSUE_RE.search(line)
        pages_match = _PAGES_RE.search(lead_text)
        name = re.split(r"\bVol\.?\b", line, flags=re.I, maxsplit=1)[0]
        journal_name = name.strip(" ,;:\t\u2013\u2014-|·")
        if not journal_name or len(journal_name) > 160:
            journal_name = None
        return {
            "journal": journal_name,
            "volume": volume_match.group(1),
            "issue": issue_match.group(1) if issue_match else None,
            "pages": (
                f"{pages_match.group(1)}-{pages_match.group(2)}"
                if pages_match
                else None
            ),
        }
    return None


def _split_authors(value: str) -> list[str]:
    """Split a raw author string (comma/and/&/dan separated) into names."""
    parts = re.split(r"\s*,\s*|\s+&\s+|\s+dan\s+|\s+and\s+", value.strip())
    authors: list[str] = []
    for part in parts:
        name = part.strip(" \t.,;")
        if not name or len(name) > 60:
            continue
        if _EMAIL_RE.search(name) or re.search(r"\d", name):
            continue
        if name.lower().startswith(
            (
                "universitas", "institut", "institute", "prodi", "fakultas",
                "department", "departemen", "laboratorium", "jurusan",
                "sekolah", "politeknik", "stikes", "stmik", "stekom",
            )
        ):
            continue
        authors.append(name)
    return authors[:20]


def _looks_like_author_line(line: str) -> bool:
    """Return True when a line is plausibly a comma-separated author list."""
    if not line or len(line) > _MAX_AUTHOR_LINE_CHARS:
        return False
    if re.search(r"\d", line):
        return False
    lowered = line.lower()
    if any(marker in lowered for marker in _AUTHOR_BLOCKING_SUBSTRINGS):
        return False
    tokens: list[str] = []
    for chunk in re.split(r"[,\s&]+", line):
        chunk = chunk.strip()
        if not chunk or chunk in ("&", "dan", "and"):
            continue
        tokens.append(chunk)
    count = len(tokens)
    if count < 2 or count > _MAX_AUTHOR_LINE_WORDS:
        return False
    if not all(_NAME_TOKEN_RE.match(token) for token in tokens):
        return False
    has_separator = "," in line or " & " in line or " dan " in line or " and " in line
    if count > 3 and not has_separator:
        return False
    letters = [char for char in line if char.isalpha()]
    if letters and sum(char.isupper() for char in letters) / len(letters) > 0.85:
        return False
    return True


def _detect_authors(
    lead_text: str, existing_metadata: dict[str, Any]
) -> list[str]:
    existing_author = existing_metadata.get("author")
    if existing_author:
        authors = _split_authors(str(existing_author))
        if authors:
            return authors
    for line in lead_text.splitlines()[:60]:
        if _looks_like_author_line(line):
            authors = _split_authors(line)
            if authors:
                return authors
    return []


def _detect_title(
    lead_text: str, existing_metadata: dict[str, Any]
) -> str | None:
    existing_title = existing_metadata.get("title")
    if existing_title:
        return str(existing_title)
    for line in lead_text.splitlines()[:60]:
        letters = [char for char in line if char.isalpha()]
        if len(letters) < 15:
            continue
        if sum(char.isupper() for char in letters) / len(letters) < 0.7:
            continue
        if _VOLUME_RE.search(line) or _EMAIL_RE.search(line):
            continue
        return _capitalize_title(line.strip())
    return None


def _capitalize_title(title: str) -> str:
    letters = [char for char in title if char.isalpha()]
    if letters and sum(char.isupper() for char in letters) / len(letters) > 0.8:
        return title.title()
    return title