import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from bridge.command_id_service import CommandIdService
from bridge.command_writer import CommandWriter
from bridge.common import Clock, Message
from bridge.event_service import EventService
from bridge.execution_service import (
    EXECUTION_TIMEOUT_SECONDS,
    Execution,
    ExecutionServiceImpl,
)
from bridge.models import CommandId, Event, EventKind
from typing_extensions import override

COMMAND_ID_VALUE = 7


def make_command_id(
    value: int,
    *,
    updated_at: datetime | None = None,
) -> CommandId:
    return CommandId(
        id=1,
        value=value,
        updated_at=updated_at or datetime.now(UTC),
    )


class FakeCommandIdService(CommandIdService):
    def __init__(self, command_ids: list[CommandId]) -> None:
        self._command_ids = list(command_ids)

    @override
    async def next(self) -> CommandId:
        return self._command_ids.pop(0)


class RecordingCommandWriter(CommandWriter):
    def __init__(self, error: BaseException | None = None) -> None:
        self.commands: list[str] = []
        self._error = error

    @override
    def write(self, command: str) -> None:
        if self._error is not None:
            raise self._error
        self.commands.append(command)


class RecordingEventService(EventService):
    def __init__(self, error: BaseException | None = None) -> None:
        self.events: list[tuple[EventKind, str]] = []
        self._error = error

    @override
    async def add(self, kind: EventKind, data: str) -> Event:
        if self._error is not None:
            raise self._error
        self.events.append((kind, data))
        return Event(kind=kind, data=data)

    @override
    async def list_recent_events(self, *, limit: int) -> list[Event]:
        return [Event(kind=kind, data=data) for kind, data in self.events[-limit:]]


class BlockingClock(Clock):
    def __init__(self) -> None:
        self.started = asyncio.Event()

    @override
    def now_utc(self) -> datetime:
        return datetime.now(UTC)

    @override
    async def sleep(self, seconds: float) -> None:
        del seconds
        self.started.set()
        await asyncio.Future[None]()


class ScriptedClock(Clock):
    def __init__(self, now: datetime, *, iterations: int) -> None:
        self._now = now
        self._iterations = iterations
        self.sleep_calls: list[float] = []

    @override
    def now_utc(self) -> datetime:
        return self._now

    @override
    async def sleep(self, seconds: float) -> None:
        self.sleep_calls.append(seconds)
        if self._iterations == 0:
            raise asyncio.CancelledError
        self._iterations -= 1


@pytest.mark.asyncio
async def test_init_starts_timeout_task_and_close_cancels_it() -> None:
    service = ExecutionServiceImpl(
        FakeCommandIdService([]),
        RecordingCommandWriter(),
        RecordingEventService(),
        BlockingClock(),
    )

    await service.init()
    assert service._timeout_task is not None

    await asyncio.sleep(0)
    assert service._timeout_task.done() is False

    await service.close()

    assert service._timeout_task.done() is True


@pytest.mark.asyncio
async def test_close_is_noop_before_init() -> None:
    service = ExecutionServiceImpl(
        FakeCommandIdService([]),
        RecordingCommandWriter(),
        RecordingEventService(),
        BlockingClock(),
    )

    await service.close()

    assert service._timeout_task is None


@pytest.mark.asyncio
async def test_execute_writes_records_and_returns_received_message() -> None:
    command_id = make_command_id(COMMAND_ID_VALUE)
    writer = RecordingCommandWriter()
    event_service = RecordingEventService()
    service = ExecutionServiceImpl(
        FakeCommandIdService([command_id]),
        writer,
        event_service,
        BlockingClock(),
    )

    execute_task = asyncio.create_task(service.execute("play"))
    await asyncio.sleep(0)

    assert writer.commands == [f"--command-id={COMMAND_ID_VALUE} play"]
    assert event_service.events == [
        ("command", f"--command-id={COMMAND_ID_VALUE} play")
    ]
    assert str(COMMAND_ID_VALUE) in service._executions

    message = Message(command_id=str(COMMAND_ID_VALUE), ready_for_command=True)
    service.receive_message(message)

    assert await execute_task == message
    assert service._executions == {}


@pytest.mark.asyncio
async def test_execute_raises_for_duplicate_pending_command_id() -> None:
    first_command_id = make_command_id(COMMAND_ID_VALUE)
    duplicate_command_id = make_command_id(COMMAND_ID_VALUE)
    service = ExecutionServiceImpl(
        FakeCommandIdService([first_command_id, duplicate_command_id]),
        RecordingCommandWriter(),
        RecordingEventService(),
        BlockingClock(),
    )

    execute_task = asyncio.create_task(service.execute("play"))
    await asyncio.sleep(0)

    with pytest.raises(RuntimeError, match="Duplicate command_id: 7"):
        await service.execute("state")

    service.receive_message(Message(command_id=str(COMMAND_ID_VALUE)))
    await execute_task


@pytest.mark.asyncio
async def test_execute_removes_pending_execution_when_writer_raises() -> None:
    service = ExecutionServiceImpl(
        FakeCommandIdService([make_command_id(COMMAND_ID_VALUE)]),
        RecordingCommandWriter(RuntimeError("write failed")),
        RecordingEventService(),
        BlockingClock(),
    )

    with pytest.raises(RuntimeError, match="write failed"):
        await service.execute("play")

    assert service._executions == {}


@pytest.mark.asyncio
async def test_execute_removes_pending_execution_when_event_recording_raises() -> None:
    writer = RecordingCommandWriter()
    service = ExecutionServiceImpl(
        FakeCommandIdService([make_command_id(COMMAND_ID_VALUE)]),
        writer,
        RecordingEventService(RuntimeError("event failed")),
        BlockingClock(),
    )

    with pytest.raises(RuntimeError, match="event failed"):
        await service.execute("play")

    assert writer.commands == [f"--command-id={COMMAND_ID_VALUE} play"]
    assert service._executions == {}


def test_receive_message_ignores_missing_or_unknown_command_id() -> None:
    service = ExecutionServiceImpl(
        FakeCommandIdService([]),
        RecordingCommandWriter(),
        RecordingEventService(),
        BlockingClock(),
    )

    service.receive_message(Message())
    service.receive_message(Message(command_id="missing"))

    assert service._executions == {}


@pytest.mark.asyncio
async def test_receive_message_does_not_override_done_future() -> None:
    service = ExecutionServiceImpl(
        FakeCommandIdService([]),
        RecordingCommandWriter(),
        RecordingEventService(),
        BlockingClock(),
    )
    future: asyncio.Future[Message] = asyncio.get_running_loop().create_future()
    future.set_result(Message(error="already done"))
    service._executions["1"] = Execution(
        future=future,
        command_id=make_command_id(1),
    )

    service.receive_message(Message(command_id="1", error="late"))

    assert future.result().error == "already done"
    assert service._executions == {}


@pytest.mark.asyncio
async def test_run_timeout_times_out_pending_execution_and_removes_it() -> None:
    expired_at = datetime.now(UTC) - timedelta(seconds=EXECUTION_TIMEOUT_SECONDS + 1)
    clock = ScriptedClock(datetime.now(UTC), iterations=1)
    service = ExecutionServiceImpl(
        FakeCommandIdService([]),
        RecordingCommandWriter(),
        RecordingEventService(),
        clock,
    )
    future: asyncio.Future[Message] = asyncio.get_running_loop().create_future()
    service._executions["1"] = Execution(
        future=future,
        command_id=make_command_id(1, updated_at=expired_at),
    )

    task = asyncio.create_task(service._run_timeout())
    with pytest.raises(asyncio.CancelledError):
        await task

    assert clock.sleep_calls == [1, 1]
    assert future.result() == Message(command_id="1", error="Command timed out")
    assert service._executions == {}


@pytest.mark.asyncio
async def test_run_timeout_removes_done_execution_without_overwriting_result() -> None:
    expired_at = datetime.now(UTC) - timedelta(seconds=EXECUTION_TIMEOUT_SECONDS + 1)
    clock = ScriptedClock(datetime.now(UTC), iterations=1)
    service = ExecutionServiceImpl(
        FakeCommandIdService([]),
        RecordingCommandWriter(),
        RecordingEventService(),
        clock,
    )
    future: asyncio.Future[Message] = asyncio.get_running_loop().create_future()
    future.set_result(Message(command_id="1", error="done"))
    service._executions["1"] = Execution(
        future=future,
        command_id=make_command_id(1, updated_at=expired_at),
    )

    task = asyncio.create_task(service._run_timeout())
    with pytest.raises(asyncio.CancelledError):
        await task

    assert future.result() == Message(command_id="1", error="done")
    assert service._executions == {}
