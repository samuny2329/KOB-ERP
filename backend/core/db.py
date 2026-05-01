"""SQLAlchemy 2.0 engine + async session factory.

Schema-per-module convention: each module declares `__table_args__` with its
own schema (e.g. ``{"schema": "core"}``).  The schemas are created by
Alembic during the first migration.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from backend.config import get_settings

# Schema names — single source of truth, referenced by every module.
SCHEMAS = (
    "core",
    "wms",
    "inventory",
    "outbound",
    "quality",
    "ops",
    "purchase",
    "mfg",
    "sales",
    "accounting",
    "hr",
    "grp",  # group / multi-company features (`group` is reserved in Postgres)
)


class Base(DeclarativeBase):
    """Declarative base for all ORM models.  Models accept kwargs via the
    default ``__init__`` provided by SQLAlchemy."""


_settings = get_settings()

engine = create_async_engine(
    _settings.database_url_async,
    echo=_settings.debug,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency — yields a request-scoped async session."""
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


SessionDep = Annotated[AsyncSession, Depends(get_session)]
