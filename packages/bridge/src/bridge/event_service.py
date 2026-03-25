from bridge.db import Db
from bridge.event_repository import EventRepository
from bridge.models import Event, EventKind


class EventService:
    def __init__(self, db: Db) -> None:
        self._db = db

    async def add(self, kind: EventKind, data: str) -> Event:
        async with self._db.sessionmaker.begin() as session:
            return await EventRepository(session).add(kind=kind, data=data)

    async def list_recent_events(self, *, limit: int) -> list[Event]:
        async with self._db.sessionmaker.begin() as session:
            return await EventRepository(session).list_recent(limit=limit)
