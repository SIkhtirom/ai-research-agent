"""Document ORM model representing a source stored in the knowledge base."""

import json
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.database import Base, utc_now


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(16))
    content_text: Mapped[str] = mapped_column(Text)
    doc_metadata: Mapped[str] = mapped_column(Text, default="{}")
    vector_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    session = relationship("ResearchSession", back_populates="documents")

    @property
    def metadata_dict(self) -> dict[str, Any]:
        return json.loads(self.doc_metadata or "{}")
