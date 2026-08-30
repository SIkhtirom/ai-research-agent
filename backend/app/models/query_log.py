"""QueryLog ORM model representing a user prompt and its generated response."""

import json
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.database import Base, utc_now


class QueryLog(Base):
    __tablename__ = "query_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), index=True)
    prompt: Mapped[str] = mapped_column(Text)
    generated_response: Mapped[str] = mapped_column(Text)
    citations: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    session = relationship("ResearchSession", back_populates="query_logs")

    @property
    def citations_list(self) -> list[dict]:
        return json.loads(self.citations or "[]")
