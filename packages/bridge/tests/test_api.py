from datetime import UTC, datetime
from http import HTTPStatus

from bridge import api
from bridge.common import Message
from bridge.container import Container
from bridge.event_service import EventService
from bridge.execution_service import ExecutionService
from bridge.models import Event
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from typing_extensions import override

LATEST_EVENT_ID = 2


class RecordingExecutionService(ExecutionService):
    def __init__(self) -> None:
        self.commands: list[str] = []
        self.messages: list[Message] = []

    @override
    async def init(self) -> None:
        return None

    @override
    async def close(self) -> None:
        return None

    @override
    async def execute(self, command: str) -> Message:
        self.commands.append(command)
        return Message(command_id="42", ready_for_command=True)

    @override
    def receive_message(self, message: Message) -> None:
        self.messages.append(message)


class RecordingEventService(EventService):
    def __init__(self, events: list[Event]) -> None:
        self._events = events
        self.added: list[tuple[str, str]] = []
        self.limits: list[int] = []

    @override
    async def add(self, kind: str, data: str) -> Event:
        self.added.append((kind, data))
        return Event(kind="message", data=data)

    @override
    async def list_recent_events(self, *, limit: int) -> list[Event]:
        self.limits.append(limit)
        return self._events[-limit:]


class RecordingContainer(Container):
    def __init__(
        self,
        execution_service: RecordingExecutionService,
        event_service: RecordingEventService,
    ) -> None:
        self.execution_service = execution_service
        self.event_service = event_service
        self.calls: list[str] = []

    @override
    async def init(self) -> None:
        self.calls.append("init")

    @override
    async def close(self) -> None:
        self.calls.append("close")


def test_create_app_sets_container_and_registers_routes() -> None:
    container = RecordingContainer(
        RecordingExecutionService(),
        RecordingEventService([]),
    )

    app = api.create_app(container)

    assert api.get_container(app) is container
    assert {route.path for route in app.routes if isinstance(route, APIRoute)} >= {
        "/execute",
        "/events",
    }


def test_lifespan_initializes_and_closes_container() -> None:
    container = RecordingContainer(
        RecordingExecutionService(),
        RecordingEventService([]),
    )
    app = api.create_app(container)

    with TestClient(app):
        assert container.calls == ["init"]

    assert container.calls == ["init", "close"]


def test_execute_delegates_to_execution_service() -> None:
    execution_service = RecordingExecutionService()
    container = RecordingContainer(execution_service, RecordingEventService([]))
    app = api.create_app(container)

    with TestClient(app) as client:
        response = client.post("/execute", json={"command": "play"})

    assert execution_service.commands == ["play"]
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "command_id": "42",
        "ready_for_command": True,
        "error": None,
        "available_commands": None,
        "in_game": None,
        "game_state": None,
    }


def test_events_returns_validated_event_dtos() -> None:
    timestamp = datetime(2026, 3, 25, 12, 34, 56, tzinfo=UTC)
    events = [
        Event(
            id=1,
            kind="command",
            data="play",
            created_at=timestamp,
            updated_at=timestamp,
        ),
        Event(
            id=2,
            kind="message",
            data='{"ready_for_command":true}',
            created_at=timestamp,
            updated_at=timestamp,
        ),
    ]
    event_service = RecordingEventService(events)
    container = RecordingContainer(RecordingExecutionService(), event_service)
    app = api.create_app(container)

    with TestClient(app) as client:
        response = client.get("/events", params={"limit": 1})

    assert event_service.limits == [1]
    assert response.status_code == HTTPStatus.OK
    assert response.json() == [
        {
            "id": LATEST_EVENT_ID,
            "kind": "message",
            "data": '{"ready_for_command":true}',
            "created_at": "2026-03-25T12:34:56Z",
            "updated_at": "2026-03-25T12:34:56Z",
        }
    ]
