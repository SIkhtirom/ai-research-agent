"""Base contracts and factory used by all document parsers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ExtractedDocument:
    """Normalised output produced by every parser."""

    content_text: str
    metadata: dict[str, Any]
    pages: list[str] | None = None


class DocumentParser(ABC):
    """Interface every concrete parser must implement."""

    @abstractmethod
    def parse(self, source: Path | str) -> ExtractedDocument:
        """Extract plain text and base metadata from the given source."""
