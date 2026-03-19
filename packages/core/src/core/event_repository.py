from typing import Literal, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from core.db import Event

EventKind = Literal["command", "message"]


class EventRepository(Protocol):
    async def add(self, kind: EventKind, data: str) -> int: ...


class AlchemyEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, kind: EventKind, data: str) -> int:
        event = Event(kind=kind, data=data)
        self._session.add(event)
        await self._session.flush()
        return event.id
