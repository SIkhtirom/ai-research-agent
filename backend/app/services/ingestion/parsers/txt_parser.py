"""Plain text (.txt) extraction with robust encoding detection.

Windows Notepad commonly saves files as UTF-8 (with or without BOM) or as ANSI
(codepage-1252 on Western systems, or other locale codepages). Reading such a
file as UTF-8 alone garbles ANSI content, so this parser detects the encoding
before decoding so uploaded text reaches chunking/embedding intact.
"""

import logging
from pathlib import Path

from .base_parser import DocumentParser, ExtractedDocument

logger = logging.getLogger(__name__)


class TxtParser(DocumentParser):
    def parse(self, source: Path | str) -> ExtractedDocument:
        source_path = Path(source)
        raw = source_path.read_bytes()

        content_text, encoding = self.__decode(raw)
        if encoding == "utf-8-sig":
            # utf-8-sig already strips the BOM; keep text as-is.
            content_text = content_text.lstrip("\ufeff")
        content_text = content_text.strip()

        metadata = {
            "filename": source_path.name,
            "encoding": encoding,
            "line_count": content_text.count("\n") + 1 if content_text else 0,
        }
        if encoding != "utf-8-sig":
            logger.debug("Decoded '%s' using %s", source_path.name, encoding)
        return ExtractedDocument(content_text=content_text, metadata=metadata)

    @staticmethod
    def __decode(raw: bytes) -> tuple[str, str]:
        """Return (decoded_text, encoding) preferring the most lossless decode.

        Explicit BOM detection is used for UTF-16/UTF-32 so ANSI (cp1252) files –
        which are not byte-aligned and can be mis-decoded as UTF-16 otherwise –
        are never read with the wrong codec.
        """
        if raw.startswith(b"\xef\xbb\xbf"):
            return raw.decode("utf-8-sig"), "utf-8-sig"
        if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
            return raw.decode("utf-16"), "utf-16"
        if raw.startswith(b"\x00\x00\xfe\xff") or raw.startswith(b"\xff\xfe\x00\x00"):
            return raw.decode("utf-32"), "utf-32"

        # No BOM: prefer strict UTF-8 (covers most content), else ANSI. cp1252 is
        # tested before latin-1 so Windows typographic characters decode properly.
        for encoding in ("utf-8", "cp1252"):
            try:
                return raw.decode(encoding), encoding
            except (UnicodeDecodeError, LookupError):
                continue

        # latin-1 never fails; last-resort safe decode.
        return raw.decode("latin-1"), "latin-1"
