import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from ai import api


class _FakeWebSocket:
    def __init__(self, responses: list[str | bytes]) -> None:
        self._responses = responses
        self.sent_messages: list[str] = []

    async def send(self, message: str) -> None:
        self.sent_messages.append(message)

    async def recv(self) -> str | bytes:
        return self._responses.pop(0)


@pytest.mark.anyio
async def test_connect_sends_command_and_parses_json_response() -> None:
    websocket = _FakeWebSocket([json.dumps({"ready_for_command": True})])
    seen_urls: list[str] = []

    @asynccontextmanager
    async def connector(url: str) -> AsyncIterator[_FakeWebSocket]:
        seen_urls.append(url)
        yield websocket

    async with api.connect(connector=connector) as session:
        response = await session.communicate("state")

    assert seen_urls == [api.BRIDGE_WS_URL]
    assert websocket.sent_messages == ["state"]
    assert response == {"ready_for_command": True}


@pytest.mark.anyio
async def test_connect_rejects_binary_messages() -> None:
    websocket = _FakeWebSocket([b'{"ready_for_command": true}'])

    @asynccontextmanager
    async def connector(_: str) -> AsyncIterator[_FakeWebSocket]:
        yield websocket

    async with api.connect(connector=connector) as session:
        with pytest.raises(TypeError, match=r"Expected text message from bridge\."):
            await session.communicate("state")


@pytest.mark.anyio
async def test_connect_rejects_non_object_json_messages() -> None:
    websocket = _FakeWebSocket([json.dumps(["not", "an", "object"])])

    @asynccontextmanager
    async def connector(_: str) -> AsyncIterator[_FakeWebSocket]:
        yield websocket

    async with api.connect(connector=connector) as session:
        with pytest.raises(TypeError, match=r"Expected JSON object from bridge\."):
            await session.communicate("state")
