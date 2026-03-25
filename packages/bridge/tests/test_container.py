import asyncio
from datetime import UTC, datetime

import pytest
from bridge.command_id_service import CommandIdService, CommandIdServiceImpl
from bridge.command_writer import CommandWriter, CommandWriterImpl
from bridge.common import Clock, ClockImpl, Message
from bridge.container import Container
from bridge.db import Db
from bridge.event_service import EventService, EventServiceImpl
from bridge.execution_service import ExecutionService, ExecutionServiceImpl
from bridge.message_service import MessageService
from bridge.models import CommandId, Event, EventKind
from typing_extensions import override


class RecordingDb(Db):
    def __init__(self, calls: list[str]) -> None:
        self._calls = calls

    @override
    async def init(self) -> None:
        self._calls.append("db.init")

    @override
    async def close(self) -> None:
        self._calls.append("db.close")


class RecordingCommandWriter(CommandWriter):
    commands: list[str]

    def __init__(self) -> None:
        self.commands = []

    @override
    def write(self, command: str) -> None:
        self.commands.append(command)


class RecordingClock(Clock):
    @override
    def now_utc(self) -> datetime:
        return datetime.now(UTC)

    @override
    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


class RecordingCommandIdService(CommandIdService):
    @override
    async def next(self) -> CommandId:
        return CommandId(id=1, value=1, updated_at=datetime.now(UTC))


class RecordingEventService(EventService):
    @override
    async def add(self, kind: EventKind, data: str) -> Event:
        return Event(kind=kind, data=data)

    @override
    async def list_recent_events(self, *, limit: int) -> list[Event]:
        return []


class RecordingExecutionService(ExecutionService):
    def __init__(self, calls: list[str]) -> None:
        self._calls = calls

    @override
    async def init(self) -> None:
        self._calls.append("execution.init")

    @override
    async def close(self) -> None:
        self._calls.append("execution.close")

    @override
    async def execute(self, command: str) -> Message:
        self._calls.append(f"execution.execute:{command}")
        return Message(ready_for_command=True)

    @override
    def receive_message(self, message: Message) -> None:
        self._calls.append(f"execution.receive:{message.command_id}")


class RecordingMessageService(MessageService):
    def __init__(self, calls: list[str]) -> None:
        self._calls = calls

    @override
    async def init(self) -> None:
        self._calls.append("message.init")

    @override
    async def close(self) -> None:
        self._calls.append("message.close")


def test_container_builds_default_bridge_components() -> None:
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    container = Container(queue)

    assert isinstance(container._db, Db)
    assert isinstance(container._command_writer, CommandWriterImpl)
    assert isinstance(container._clock, ClockImpl)
    assert isinstance(container._command_id_service, CommandIdServiceImpl)
    assert isinstance(container.event_service, EventServiceImpl)
    assert isinstance(container.execution_service, ExecutionServiceImpl)
    assert isinstance(container._message_service, MessageService)
    assert (
        container.execution_service._command_id_service is container._command_id_service
    )
    assert container.execution_service._command_writer is container._command_writer
    assert container.execution_service._event_service is container.event_service
    assert container.execution_service._clock is container._clock
    assert container._message_service._execution_service is container.execution_service
    assert container._message_service._event_service is container.event_service
    assert container._message_service._queue is queue


def test_container_uses_injected_dependencies_as_is() -> None:
    calls: list[str] = []
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    db = RecordingDb(calls)
    command_writer = RecordingCommandWriter()
    clock = RecordingClock()
    command_id_service = RecordingCommandIdService()
    event_service = RecordingEventService()
    execution_service = RecordingExecutionService(calls)
    message_service = RecordingMessageService(calls)

    container = Container(
        queue,
        db=db,
        command_writer=command_writer,
        clock=clock,
        execution_service=execution_service,
        message_service=message_service,
        command_id_service=command_id_service,
        event_service=event_service,
    )

    assert container._db is db
    assert container._command_writer is command_writer
    assert container._clock is clock
    assert container._command_id_service is command_id_service
    assert container.event_service is event_service
    assert container.execution_service is execution_service
    assert container._message_service is message_service


@pytest.mark.asyncio
async def test_container_init_and_close_follow_expected_order() -> None:
    calls: list[str] = []
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    container = Container(
        queue,
        db=RecordingDb(calls),
        command_writer=RecordingCommandWriter(),
        clock=RecordingClock(),
        execution_service=RecordingExecutionService(calls),
        message_service=RecordingMessageService(calls),
        command_id_service=RecordingCommandIdService(),
        event_service=RecordingEventService(),
    )

    await container.init()
    await container.close()

    assert calls == [
        "db.init",
        "message.init",
        "execution.init",
        "execution.execute:ready",
        "execution.close",
        "message.close",
        "db.close",
    ]
