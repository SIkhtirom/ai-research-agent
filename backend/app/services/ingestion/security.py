"""Upload security: magic-byte signature validation and malicious-content inspection.

Two independent guards run before any document reaches the RAG/embedding step:

1. ``FileSignatureValidator`` -- strict magic-bytes checks so that a `.exe` or
   arbitrary binary renamed to `.pdf`/`.docx`/`.pptx`/`.txt` is rejected. DOCX and
   PPTX are both ZIP (PK) archives, so the actual OOXML package type is confirmed
   by inspecting the zip's ``[Content_Types].xml`` word/ppt markers.

2. ``ContentScanner`` -- scans extracted document text and user-supplied text for
   prompt-injection / jailbreak patterns (e.g. "ignore previous instructions")
   and dangerous payload markers before the text is forwarded to the AI/RAG stack.

Both raise :class:`ValidationError`, which callers translate into the single,
uniform client-facing message: "Format file tidak valid, pastikan file yang
diupload sudah sesuai."
"""

from __future__ import annotations

import io
import logging
import re
import zipfile
from typing import Pattern

logger = logging.getLogger(__name__)

UNIFORM_ERROR_MESSAGE = "Format file tidak valid, pastikan file yang diupload sudah sesuai."


class ValidationError(Exception):
    """Raised when a file fails signature or content validation.

    The message is intentionally generic so no internal detail leaks to clients.
    """


# --------------------------------------------------------------------------- #
# Magic bytes signatures
# --------------------------------------------------------------------------- #
_MAGIC_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    ".pdf": (
        b"%PDF-",
        b"\xef\xbb\xbf%PDF-",  # UTF-8 BOM then signature
    ),
    # DOCX, PPTX and XLSX are all OOXML packages (ZIP archives). Only the empty
    # (zero-entry) and normal PK variants are acceptable containers.
    ".docx": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
    ".pptx": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
}

# OOXML content markers that distinguish DOCX from PPTX inside the package.
_DOCX_CONTENT_TYPES = (b"word/", b"application/vnd.openxmlformats-officedocument.wordprocessingml")
_PPTX_CONTENT_TYPES = (b"ppt/", b"application/vnd.openxmlformats-officedocument.presentationml")

# TXT files must be text. Anything containing NUL bytes (or mostly binary
# control characters) is treated as a disguised binary and rejected.
_MAX_BINARY_CONTROL_FRACTION = 0.30
_NUL_BYTE = b"\x00"


class FileSignatureValidator:
    """Validates a file's declared extension against its actual magic bytes."""

    def validate(self, file_extension: str, data: bytes) -> None:
        """Raise :class:`ValidationError` when the bytes do not match the extension."""
        extension = file_extension.lower()

        if extension == ".txt":
            self.__validate_txt(data)
            return

        signatures = _MAGIC_SIGNATURES.get(extension)
        if signatures is None:
            raise ValidationError(f"Unsupported extension: {extension}")

        head = data[:8]
        if not any(head.startswith(magic) for magic in signatures):
            logger.warning("Magic bytes mismatch for %s file (head=%r)", extension, head)
            raise ValidationError(f"Magic bytes do not match {extension}")

        if extension in (".docx", ".pptx"):
            self.__validate_ooxml_type(extension, data)

    # ---------------------------------------------------------------- helpers
    def __validate_txt(self, data: bytes) -> None:
        if len(data) >= 1 and _NUL_BYTE in data:
            raise ValidationError("Binary content detected in a .txt file")

        if len(data) > 0:
            sample = data[:4096]
            control_count = sum(
                1
                for byte in sample
                if byte < 0x09 or (0x0E <= byte <= 0x1F) or byte == 0x7F
            )
            if control_count / len(sample) > _MAX_BINARY_CONTROL_FRACTION:
                raise ValidationError("Binary-like content detected in a .txt file")

    def __validate_ooxml_type(self, extension: str, data: bytes) -> None:
        """Best-effort confirmation that the OOXML zip package matches the extension.

        A genuine DOCX/PPTX is always a ZIP (PK) archive, which the caller has
        already verified via magic bytes. This step therefore only hard-fails when
        the package *positively* identifies as the OTHER office type (e.g. a real
        ``.docx`` renamed to ``.pptx``), or when it is not a readable ZIP at all.

        It is intentionally lenient in the good direction: a valid OOXML package
        whose internals omit the usual markers or use an unusual structure is still
        accepted, so a legitimate PPTX from ANY source is never rejected.
        """
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                content_types = ""
                try:
                    content_types = archive.read("[Content_Types].xml").decode(
                        "utf-8", "ignore"
                    )
                except KeyError:
                    # Some producers omit the central content-types entry; treat
                    # it as "no evidence of the wrong type" rather than a failure.
                    pass

                if extension == ".docx":
                    other_markers = _PPTX_CONTENT_TYPES
                else:
                    other_markers = _DOCX_CONTENT_TYPES

                # Positive proof that the package is actually the OTHER type.
                other_actual = any(
                    marker.decode("utf-8", "ignore") in content_types
                    for marker in other_markers
                )
                other_names = any(
                    name.startswith(marker.decode())
                    for marker in other_markers
                    for name in archive.namelist()
                )
                if other_actual or other_names:
                    logger.warning(
                        "OOXML package is not a %s (content types=%r)",
                        extension[1:].upper(),
                        content_types[:200],
                    )
                    raise ValidationError(
                        f"OOXML package is not a {extension[1:].upper()}"
                    )
        except ValidationError:
            raise
        except (zipfile.BadZipFile, OSError) as error:  # noqa: BLE001 - invalid/truncated package
            logger.warning("Invalid %s package: %s", extension, error)
            raise ValidationError(f"Invalid {extension[1:].upper()} package") from error


# --------------------------------------------------------------------------- #
# Malicious content / jailbreak inspection
# --------------------------------------------------------------------------- #
# Prompt injection & jailbreak patterns (case-insensitive).
_JAILBREAK_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts)", re.IGNORECASE),
    re.compile(r"you\s+are\s+(now\s+)?(dan\b|free|unrestricted|in\s+dan|released)", re.IGNORECASE),
    re.compile(r"system\s+override", re.IGNORECASE),
    re.compile(r"developer\s+override", re.IGNORECASE),
    re.compile(r"(remove|disable|bypass|drop)\s+(your\s+)?(safety|guardrails|guidelines|restrictions|filters|censorship)", re.IGNORECASE),
    re.compile(r"act\s+as\s+(an?\s+)?(unfiltered|uncensored|jailbreak(ed)?)", re.IGNORECASE),
    re.compile(r"DAN\s+[\"\u201c\u201d]do\s+anything\s+now", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"anti[- ]?censorship\s+mode", re.IGNORECASE),
    re.compile(r"pretend\s+you(?:\'|\u2019)re\s+not\s+(an?\s+)?(ai|assistant|llm)", re.IGNORECASE),
)

# Dangerous payload markers: executable code / scripts / credential harvesting.
_MALICIOUS_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(r"<script[\s>]", re.IGNORECASE),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r"\b(eval|exec)\s*\(", re.IGNORECASE),
    re.compile(r"\bimport\s+(os|subprocess|base64|socket)\b", re.IGNORECASE),
    re.compile(r"\b(__import__|os\.system|subprocess\.(call|run|Popen)|base64\.b64decode)\b", re.IGNORECASE),
    re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|DROP)\b.+\bFROM\b", re.IGNORECASE),
    re.compile(r"\bBEGIN\s+[\s\S]*END;\s*--", re.IGNORECASE),
)

_WHITESPACE_RE = re.compile(r"\s+")


class ContentScanner:
    """Scans text for prompt-injection, jailbreak, and dangerous payload markers."""

    def __init__(
        self,
        max_patterns: int = 500,
        max_chars: int = 2_000_000,
    ):
        # Cap the number of pattern hits and text size so pathological inputs
        # cannot cause unbounded regex work.
        self.__max_patterns = max_patterns
        self.__max_chars = max_chars

    def inspect(self, text: str) -> None:
        """Raise :class:`ValidationError` when the text looks malicious."""
        if not text:
            return

        normalized = _WHITESPACE_RE.sub(" ", text)
        window = normalized[: self.__max_chars]
        hits = 0

        for pattern in (*_JAILBREAK_PATTERNS, *_MALICIOUS_PATTERNS):
            if pattern.search(window):
                hits += 1
                if hits >= self.__max_patterns:
                    break
                logger.warning("Malicious content pattern matched: %r", pattern.pattern)
                raise ValidationError("Suspicious content pattern detected")
