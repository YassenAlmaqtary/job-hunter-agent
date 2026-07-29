"""
SQLAlchemy engine and session helpers.

EN: Replaces raw psycopg helpers with ORM sessions; schema via ``Base.metadata.create_all``.
AR: محرك وجلسات SQLAlchemy بدل استعلامات SQL اليدوية.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from core.db.models import Base

_SCHEMA_BOOTSTRAPPED = False
_ENGINE: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def database_url() -> str:
    """Return a SQLAlchemy-compatible Postgres URL (psycopg3 driver)."""
    raw = (os.getenv("DATABASE_URL") or "").strip()
    if not raw:
        return ""
    # Accept both postgresql:// and postgres:// from Docker/.env.
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://") :]
    if raw.startswith("postgresql://") and "+psycopg" not in raw.split("://", 1)[0]:
        raw = "postgresql+psycopg://" + raw[len("postgresql://") :]
    return raw


def database_configured() -> bool:
    return bool(database_url())


def get_engine() -> Engine:
    global _ENGINE, _SessionLocal
    url = database_url()
    if not url:
        raise RuntimeError("DATABASE_URL غير مضبوط.")
    if _ENGINE is None:
        _ENGINE = create_engine(url, pool_pre_ping=True)
        _SessionLocal = sessionmaker(bind=_ENGINE, autoflush=False, autocommit=False, expire_on_commit=False)
    return _ENGINE


def _session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional ORM session; commits on success, rolls back on error."""
    ensure_schema()
    session = _session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ensure_schema() -> None:
    """Create tables (and pgcrypto if available) once per process."""
    global _SCHEMA_BOOTSTRAPPED
    if _SCHEMA_BOOTSTRAPPED or not database_configured():
        return
    engine = get_engine()
    with engine.begin() as conn:
        # Optional: keeps compatibility if other tools still rely on gen_random_uuid().
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        Base.metadata.create_all(bind=conn)
        # Lightweight migrations for existing deployments (create_all does not ALTER).
        conn.execute(text("ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS google_sub TEXT"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_provider VARCHAR(32) NOT NULL DEFAULT 'password'"))
        conn.execute(
            text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = 'users_google_sub_key'
                    ) THEN
                        ALTER TABLE users ADD CONSTRAINT users_google_sub_key UNIQUE (google_sub);
                    END IF;
                END $$;
                """
            )
        )
    _SCHEMA_BOOTSTRAPPED = True


def reset_engine_for_tests() -> None:
    """Drop cached engine — useful when DATABASE_URL changes under pytest."""
    global _ENGINE, _SessionLocal, _SCHEMA_BOOTSTRAPPED
    if _ENGINE is not None:
        _ENGINE.dispose()
    _ENGINE = None
    _SessionLocal = None
    _SCHEMA_BOOTSTRAPPED = False
