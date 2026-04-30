"""Shared pytest fixtures — in-memory app instance + httpx client.

These tests do **not** hit a real database; they verify import-time wiring,
Pydantic validation, JWT round-trip, state machine logic, and the event bus.
Database-backed tests will live in ``tests/integration/`` once Postgres is
running in CI.
"""

from __future__ import annotations

import os

# Ensure required env vars exist before settings is read.
os.environ.setdefault("KOB_SECRET_KEY", "test-secret-" + "x" * 40)
os.environ.setdefault("KOB_ENV", "development")

from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@pytest.fixture(scope="session")
def app() -> FastAPI:
    from backend.main import create_app

    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
