from __future__ import annotations

import pytest

from backend.core.events import clear, emit, on


@pytest.fixture(autouse=True)
def _wipe_handlers() -> None:
    clear()


async def test_emit_fans_out_to_handlers() -> None:
    received: list[dict] = []

    @on("test.event")
    async def h1(payload: dict) -> None:
        received.append(payload)

    @on("test.event")
    async def h2(payload: dict) -> None:
        received.append({**payload, "doubled": True})

    await emit("test.event", {"x": 1})
    assert {"x": 1} in received
    assert {"x": 1, "doubled": True} in received


async def test_emit_swallows_handler_errors() -> None:
    other_called: list[bool] = []

    @on("test.boom")
    async def bad(_payload: dict) -> None:
        raise RuntimeError("kaboom")

    @on("test.boom")
    async def good(_payload: dict) -> None:
        other_called.append(True)

    await emit("test.boom", {})
    assert other_called == [True]


async def test_emit_with_no_handlers_is_noop() -> None:
    await emit("nobody.listens", {"k": "v"})
