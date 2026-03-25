from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bridge.models import Event, EventKind


class EventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, kind: EventKind, data: str) -> Event:
        event = Event(kind=kind, data=data)
        self._session.add(event)
        await self._session.flush()
        return event

    async def list_recent(self, *, limit: int) -> list[Event]:
        recent_event_ids = (
            select(Event.id).order_by(Event.id.desc()).limit(limit).subquery()
        )
        statement = (
            select(Event)
            .join(recent_event_ids, Event.id == recent_event_ids.c.id)
            .order_by(Event.id.asc())
        )
        result = await self._session.execute(statement)
        return list(result.scalars())
