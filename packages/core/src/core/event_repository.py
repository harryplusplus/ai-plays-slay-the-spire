from typing import Protocol, override

from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Event, EventKind


class EventRepository(Protocol):
    async def add(self, kind: EventKind, data: str) -> int: ...


class AlchemyEventRepository(EventRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @override
    async def add(self, kind: EventKind, data: str) -> int:
        event = Event(kind=kind, data=data)
        self._session.add(event)
        await self._session.flush()
        return event.id
