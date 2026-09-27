"""
Database engine/session setup. Uses SQLite for local/demo deployment by
default (see Settings.database_url); swapping to Postgres for a
multi-intersection production deployment only requires changing that URL -
no other code in this project should reference SQLite directly.
"""
from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def build_engine():
    settings = get_settings()
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    return create_engine(settings.database_url, connect_args=connect_args)


engine = build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Create all tables. Called once at application startup."""
    from app.models import (  # noqa: F401 - import registers models on Base.metadata
        intersection,
        lane,
        camera,
        traffic,
        signal,
        emergency,
        safety,
        events,
        simulation,
        user,
    )

    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    """FastAPI dependency: yields a request-scoped session, closed after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope():
    """Context manager for use outside request handlers (e.g. background loop)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
