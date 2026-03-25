import asyncio

import pytest
from bridge.common import Message
from bridge.event_service import EventServiceProtocol
from bridge.execution_service import ExecutionServiceProtocol
from bridge.message_service import MessageService
from bridge.models import Event, EventKind
from typing_extensions import override


class RecordingExecutionService(ExecutionServiceProtocol):
    def __init__(self) -> None:
        self.messages: list[Message] = []

    @override
    async def init(self) -> None:
        return None

    @override
    async def close(self) -> None:
        return None

    @override
    async def execute(self, command: str) -> Message:
        return Message(error=command)

    @override
    def receive_message(self, message: Message) -> None:
        self.messages.append(message)


class RecordingEventService(EventServiceProtocol):
    def __init__(self) -> None:
        self.events: list[tuple[EventKind, str]] = []

    @override
    async def add(self, kind: EventKind, data: str) -> Event:
        self.events.append((kind, data))
        return Event(kind=kind, data=data)

    @override
    async def list_recent_events(self, *, limit: int) -> list[Event]:
        return [Event(kind=kind, data=data) for kind, data in self.events[-limit:]]


@pytest.mark.asyncio
async def test_init_starts_background_task_and_close_cancels_it() -> None:
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    service = MessageService(
        queue,
        RecordingExecutionService(),
        RecordingEventService(),
    )

    await service.init()
    assert service._task is not None

    await asyncio.sleep(0)
    assert service._task.done() is False

    await service.close()
    assert service._task.done() is True


@pytest.mark.asyncio
async def test_close_is_noop_before_init() -> None:
    service = MessageService(
        asyncio.Queue(),
        RecordingExecutionService(),
        RecordingEventService(),
    )

    await service.close()

    assert service._task is None


@pytest.mark.asyncio
async def test_run_records_message_and_forwards_valid_payload() -> None:
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    execution_service = RecordingExecutionService()
    event_service = RecordingEventService()
    service = MessageService(queue, execution_service, event_service)
    raw_message = '{"command_id":"42","ready_for_command":true}'

    queue.put_nowait(raw_message)
    queue.put_nowait(None)

    await service._run()

    assert event_service.events == [("message", raw_message)]
    assert execution_service.messages == [
        Message(command_id="42", ready_for_command=True)
    ]


@pytest.mark.asyncio
async def test_run_records_message_and_skips_invalid_payload() -> None:
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    execution_service = RecordingExecutionService()
    event_service = RecordingEventService()
    service = MessageService(queue, execution_service, event_service)
    raw_message = "{invalid json"

    queue.put_nowait(raw_message)
    queue.put_nowait(None)

    await service._run()

    assert event_service.events == [("message", raw_message)]
    assert execution_service.messages == []


@pytest.mark.asyncio
async def test_run_stops_immediately_on_eof() -> None:
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    execution_service = RecordingExecutionService()
    event_service = RecordingEventService()
    service = MessageService(queue, execution_service, event_service)

    queue.put_nowait(None)

    await service._run()

    assert event_service.events == []
    assert execution_service.messages == []
