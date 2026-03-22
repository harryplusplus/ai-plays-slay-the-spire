from enum import StrEnum
from types import TracebackType
from typing import Protocol, Self

from fastapi.datastructures import State

from bridge import message


class App(Protocol):
    state: State


class _State(StrEnum):
    CREATED = "created"
    INITIALIZED = "initialized"
    CLOSED = "closed"


class Container:
    def __init__(self, message_queue: message.Queue) -> None:
        self._message_queue = message_queue
        self._state = _State.CREATED

    async def __aenter__(self) -> Self:
        self._state = _State.INITIALIZED
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        self._state = _State.CLOSED
        return None

    def attach(self, app: App) -> None:
        app.state.container = self

    @classmethod
    def get(cls, app: App) -> Self:
        return app.state.container
