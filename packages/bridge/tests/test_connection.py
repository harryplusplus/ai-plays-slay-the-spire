import asyncio
from typing import cast

import pytest
from bridge.connection import (
    BridgeConnectionError,
    Connection,
    ConnectionManagerService,
    ConnectionManagerServiceImpl,
    WebSocketConnection,
)
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect
from typing_extensions import override

CLOSE_CODE = 1001
CLOSE_REASON = "Connection manager is closed."


class _FakeConnection(Connection):
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

    @override
    async def accept(self) -> None:
        self.accepted = True
        self.accepted_event.set()

    @override
    async def receive_text(self) -> str:
        item = await self._receive_queue.get()
        if isinstance(item, Exception):
            raise item
        return item

    @override
    async def send_text(self, message: str) -> None:
        self.send_calls += 1
        if self._send_exception is not None:
            raise self._send_exception
        self.sent_messages.append(message)

    @override
    async def close(self, code: int, reason: str) -> None:
        self.close_calls.append((code, reason))
        if self._close_exception is not None:
            raise self._close_exception


class _FakeWebSocket:
    def __init__(
        self,
        *,
        receive_text_value: str = "play",
        accept_exception: Exception | None = None,
        receive_text_exception: Exception | None = None,
        send_text_exception: Exception | None = None,
        close_exception: Exception | None = None,
    ) -> None:
        self.accept_calls = 0
        self.receive_text_calls = 0
        self.sent_messages: list[str] = []
        self.close_calls: list[tuple[int, str]] = []
        self._receive_text_value = receive_text_value
        self._accept_exception = accept_exception
        self._receive_text_exception = receive_text_exception
        self._send_text_exception = send_text_exception
        self._close_exception = close_exception

    async def accept(self) -> None:
        self.accept_calls += 1
        if self._accept_exception is not None:
            raise self._accept_exception

    async def receive_text(self) -> str:
        self.receive_text_calls += 1
        if self._receive_text_exception is not None:
            raise self._receive_text_exception
        return self._receive_text_value

    async def send_text(self, message: str) -> None:
        if self._send_text_exception is not None:
            raise self._send_text_exception
        self.sent_messages.append(message)

    async def close(self, code: int, reason: str) -> None:
        self.close_calls.append((code, reason))
        if self._close_exception is not None:
            raise self._close_exception


def _as_websocket(fake_websocket: _FakeWebSocket) -> WebSocket:
    return cast("WebSocket", fake_websocket)


async def _run_websocket_operation(
    connection: WebSocketConnection,
    operation: str,
) -> None:
    if operation == "accept":
        await connection.accept()
        return

    if operation == "receive_text":
        await connection.receive_text()
        return

    if operation == "send_text":
        await connection.send_text("world")
        return

    if operation == "close":
        await connection.close(1000, "done")
        return

    raise AssertionError(f"Unsupported operation: {operation}")


async def _connect(
    connection_manager_service: ConnectionManagerService,
    connection: _FakeConnection,
) -> asyncio.Task[None]:
    task = asyncio.create_task(
        connection_manager_service.on_connection(connection),
    )
    await asyncio.wait_for(connection.accepted_event.wait(), timeout=1)
    await asyncio.sleep(0)
    return task


@pytest.mark.anyio
async def test_websocket_connection_forwards_calls() -> None:
    fake_websocket = _FakeWebSocket(receive_text_value="hello")
    connection = WebSocketConnection(_as_websocket(fake_websocket))

    await connection.accept()
    assert await connection.receive_text() == "hello"
    await connection.send_text("world")
    await connection.close(1000, "done")

    assert fake_websocket.accept_calls == 1
    assert fake_websocket.receive_text_calls == 1
    assert fake_websocket.sent_messages == ["world"]
    assert fake_websocket.close_calls == [(1000, "done")]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("operation", "exception"),
    [
        ("accept", RuntimeError("boom")),
        ("receive_text", WebSocketDisconnect(code=1000)),
        ("send_text", RuntimeError("boom")),
        ("close", WebSocketDisconnect(code=1000)),
    ],
)
async def test_websocket_connection_translates_transport_errors(
    operation: str,
    exception: Exception,
) -> None:
    fake_websocket = _FakeWebSocket(
        accept_exception=exception if operation == "accept" else None,
        receive_text_exception=exception if operation == "receive_text" else None,
        send_text_exception=exception if operation == "send_text" else None,
        close_exception=exception if operation == "close" else None,
    )
    connection = WebSocketConnection(_as_websocket(fake_websocket))

    with pytest.raises(BridgeConnectionError):
        await _run_websocket_operation(connection, operation)


@pytest.mark.anyio
async def test_on_connection_accepts_receives_and_discards_connection() -> None:
    received_commands: list[str] = []
    command_received = asyncio.Event()

    async def command_sender(command: str) -> None:
        received_commands.append(command)
        command_received.set()

    connection_manager_service = ConnectionManagerServiceImpl(command_sender)
    connection = _FakeConnection()
    connection.queue_receive("play")

    task = await _connect(connection_manager_service, connection)
    await asyncio.wait_for(command_received.wait(), timeout=1)
    connection.queue_receive(BridgeConnectionError())
    await task

    assert connection.accepted is True
    assert received_commands == ["play"]

    await connection_manager_service.broadcast("hello")
    assert connection.sent_messages == []


@pytest.mark.anyio
async def test_on_connection_rejects_duplicate_connection() -> None:
    async def command_sender(command: str) -> None:
        _ = command

    connection_manager_service = ConnectionManagerServiceImpl(command_sender)
    connection = _FakeConnection()

    task = await _connect(connection_manager_service, connection)

    with pytest.raises(RuntimeError, match=r"Connection is already connected\."):
        await connection_manager_service.on_connection(connection)

    connection.queue_receive(BridgeConnectionError())
    await task


@pytest.mark.anyio
async def test_close_is_idempotent_and_rejects_future_operations() -> None:
    async def command_sender(command: str) -> None:
        _ = command

    connection_manager_service = ConnectionManagerServiceImpl(command_sender)
    healthy_connection = _FakeConnection()
    failing_connection = _FakeConnection(close_exception=BridgeConnectionError())

    healthy_task = await _connect(connection_manager_service, healthy_connection)
    failing_task = await _connect(connection_manager_service, failing_connection)

    await connection_manager_service.close()
    await connection_manager_service.close()

    assert healthy_connection.close_calls == [(CLOSE_CODE, CLOSE_REASON)]
    assert failing_connection.close_calls == [(CLOSE_CODE, CLOSE_REASON)]

    with pytest.raises(RuntimeError, match=r"Connection manager is closed\."):
        await connection_manager_service.broadcast("hello")

    with pytest.raises(RuntimeError, match=r"Connection manager is closed\."):
        await connection_manager_service.on_connection(_FakeConnection())

    healthy_connection.queue_receive(BridgeConnectionError())
    failing_connection.queue_receive(BridgeConnectionError())
    await healthy_task
    await failing_task


@pytest.mark.anyio
async def test_message_handler_broadcasts_and_removes_stale_connections() -> None:
    async def command_sender(command: str) -> None:
        _ = command

    connection_manager_service = ConnectionManagerServiceImpl(command_sender)
    healthy_connection = _FakeConnection()
    stale_connection = _FakeConnection(send_exception=BridgeConnectionError())

    healthy_task = await _connect(connection_manager_service, healthy_connection)
    stale_task = await _connect(connection_manager_service, stale_connection)

    handler = connection_manager_service.message_handler()
    await handler("hello")
    await connection_manager_service.broadcast("again")

    assert healthy_connection.sent_messages == ["hello", "again"]
    assert stale_connection.send_calls == 1

    healthy_connection.queue_receive(BridgeConnectionError())
    stale_connection.queue_receive(BridgeConnectionError())
    await healthy_task
    await stale_task
