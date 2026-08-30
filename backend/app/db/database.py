"""SQLAlchemy engine, session factory, and declarative base for the relational database."""

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from ..core.config import settings


class Base(DeclarativeBase):
    """Base class shared by all ORM models."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def dumps_json(value) -> str:
    return json.dumps(value)


database_path = settings.data_directory / "app.db"
database_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    f"sqlite:///{database_path}",
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    """Yield a database session, ensuring it is always closed afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables that have not been created yet."""
    Base.metadata.create_all(bind=engine)
