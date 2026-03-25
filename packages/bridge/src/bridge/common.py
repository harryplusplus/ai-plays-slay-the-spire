import asyncio
from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel
from typing_extensions import override

from bridge.models import now_utc


class Message(BaseModel):
    command_id: str | None = None
    ready_for_command: bool = False

    # error
    error: str | None = None

    # result
    available_commands: list[str] | None = None
    in_game: bool | None = None
    game_state: dict[str, Any] | None = None


class ClockProtocol(Protocol):
    def now_utc(self) -> datetime: ...
    async def sleep(self, seconds: float) -> None: ...


class Clock(ClockProtocol):
    @override
    def now_utc(self) -> datetime:
        return now_utc()

    @override
    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)
