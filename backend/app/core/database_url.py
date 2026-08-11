"""Database URL normalization shared by the application and Alembic."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def normalize_database_url(value: str) -> str:
    """Return a SQLAlchemy asyncpg URL for Render/Postgres connection strings.

    Render exposes managed Postgres URLs using either ``postgres://`` or
    ``postgresql://``.  The application uses SQLAlchemy's async engine, so
    those URLs need the explicit ``+asyncpg`` driver.  Other schemes (including
    an already-normalized URL) are intentionally left untouched.
    """

    for prefix in ("postgres://", "postgresql://"):
        if value.startswith(prefix):
            return "postgresql+asyncpg://" + value[len(prefix) :]
    return value


def create_async_engine_for_url(database_url: str, **kwargs: Any) -> AsyncEngine:
    """Construct an async SQLAlchemy engine after normalizing its URL."""

    return create_async_engine(normalize_database_url(database_url), **kwargs)
