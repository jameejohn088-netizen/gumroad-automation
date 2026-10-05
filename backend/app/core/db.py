"""Database engine, session factory, and declarative base.

Works on SQLite (default, $0 dev) and PostgreSQL (change DATABASE_URL).
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def _engine_kwargs(database_url: str) -> dict:
    if database_url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {"pool_pre_ping": True}


def create_app_engine(database_url: str):
    engine = create_engine(database_url, **_engine_kwargs(database_url))
    if database_url.startswith("sqlite"):
        # Enforce FK cascades in SQLite (off by default).
        from sqlalchemy import event

        @event.listens_for(engine, "connect")
        def _fk_pragma(dbapi_conn, _):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()
    return engine


# Lazily created so tests can override DATABASE_URL before first use.
_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        from app.core.config import get_settings

        _engine = create_app_engine(get_settings().DATABASE_URL)
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
    return _SessionLocal


def reset_engine():
    """Test helper: drop cached engine/session so a new DATABASE_URL takes effect."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def get_db():
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
