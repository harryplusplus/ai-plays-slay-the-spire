import asyncio
from typing import cast

import pytest
from bridge import connection
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

CLOSE_CODE = 1001
CLOSE_REASON = "Connection manager is closed."
DISCONNECT_CODE = 1000


class _FakeWebSocket:
    def __init__(
        self,
        *,
        send_exception: Exception | None = None,
        close_exception: Exception | None = None,
    ) -> None:
        self.accepted = False
        self.accepted_event = asyncio.Event()
        self._receive_queue: asyncio.Queue[str | Exception] = asyncio.Queue()
        self.sent_messages: list[str] = []
        self.send_calls = 0
        self.close_calls: list[tuple[int, str]] = []
        self._send_exception = send_exception
        self._close_exception = close_exception

    def queue_receive(self, item: str | Exception) -> None:
        self._receive_queue.put_nowait(item)

    async def accept(self) -> None:
        self.accepted = True
        self.accepted_event.set()

    async def receive_text(self) -> str:
        item = await self._receive_queue.get()
        if isinstance(item, Exception):
            raise item
        return item

    async def send_text(self, message: str) -> None:
        self.send_calls += 1
        if self._send_exception is not None:
            raise self._send_exception
        self.sent_messages.append(message)

    async def close(self, code: int, reason: str) -> None:
        self.close_calls.append((code, reason))
        if self._close_exception is not None:
            raise self._close_exception


def _as_websocket(websocket: _FakeWebSocket) -> WebSocket:
    return cast("WebSocket", websocket)


async def _connect(
    manager: connection.ManagerService,
    websocket: _FakeWebSocket,
) -> asyncio.Task[None]:
    task = asyncio.create_task(manager.on_websocket(_as_websocket(websocket)))
    await asyncio.wait_for(websocket.accepted_event.wait(), timeout=1)
    await asyncio.sleep(0)
    return task


@pytest.mark.anyio
async def test_on_websocket_accepts_receives_and_discards_connection() -> None:
    received_commands: list[str] = []
    command_received = asyncio.Event()

    async def command_sender(command: str) -> None:
        received_commands.append(command)
        command_received.set()

    manager = connection.ManagerServiceImpl(command_sender)
    websocket = _FakeWebSocket()
    websocket.queue_receive("play")

    task = await _connect(manager, websocket)
    await asyncio.wait_for(command_received.wait(), timeout=1)
    websocket.queue_receive(WebSocketDisconnect(code=DISCONNECT_CODE))
    await task

    assert websocket.accepted is True
    assert received_commands == ["play"]

    await manager.broadcast("hello")
    assert websocket.sent_messages == []


@pytest.mark.anyio
async def test_on_websocket_rejects_duplicate_connection() -> None:
    async def command_sender(command: str) -> None:
        _ = command

    manager = connection.ManagerServiceImpl(command_sender)
    websocket = _FakeWebSocket()

    task = await _connect(manager, websocket)

    with pytest.raises(RuntimeError, match=r"WebSocket is already connected\."):
        await manager.on_websocket(_as_websocket(websocket))

    websocket.queue_receive(WebSocketDisconnect(code=DISCONNECT_CODE))
    await task


@pytest.mark.anyio
async def test_close_is_idempotent_and_rejects_future_operations() -> None:
    async def command_sender(command: str) -> None:
        _ = command

    manager = connection.ManagerServiceImpl(command_sender)
    healthy_websocket = _FakeWebSocket()
    failing_websocket = _FakeWebSocket(close_exception=RuntimeError("boom"))

    healthy_task = await _connect(manager, healthy_websocket)
    failing_task = await _connect(manager, failing_websocket)

    await manager.close()
    await manager.close()

    assert healthy_websocket.close_calls == [(CLOSE_CODE, CLOSE_REASON)]
    assert failing_websocket.close_calls == [(CLOSE_CODE, CLOSE_REASON)]

    with pytest.raises(RuntimeError, match=r"Connection manager is closed\."):
        await manager.broadcast("hello")

    with pytest.raises(RuntimeError, match=r"Connection manager is closed\."):
        await manager.on_websocket(_as_websocket(_FakeWebSocket()))

    healthy_websocket.queue_receive(WebSocketDisconnect(code=DISCONNECT_CODE))
    failing_websocket.queue_receive(WebSocketDisconnect(code=DISCONNECT_CODE))
    await healthy_task
    await failing_task


@pytest.mark.anyio
async def test_message_handler_broadcasts_and_removes_stale_websockets() -> None:
    async def command_sender(command: str) -> None:
        _ = command

    manager = connection.ManagerServiceImpl(command_sender)
    healthy_websocket = _FakeWebSocket()
    stale_websocket = _FakeWebSocket(send_exception=RuntimeError("gone"))

    healthy_task = await _connect(manager, healthy_websocket)
    stale_task = await _connect(manager, stale_websocket)

    handler = manager.message_handler()
    await handler("hello")
    await manager.broadcast("again")

    assert healthy_websocket.sent_messages == ["hello", "again"]
    assert stale_websocket.send_calls == 1

    healthy_websocket.queue_receive(WebSocketDisconnect(code=DISCONNECT_CODE))
    stale_websocket.queue_receive(WebSocketDisconnect(code=DISCONNECT_CODE))
    await healthy_task
    await stale_task
