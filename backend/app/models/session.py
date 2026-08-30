"""Session ORM model representing a chat/research session."""

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.database import Base, utc_now


class ResearchSession(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    documents = relationship("Document", back_populates="session", cascade="all, delete-orphan")
    query_logs = relationship("QueryLog", back_populates="session", cascade="all, delete-orphan")
