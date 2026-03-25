from pathlib import Path

import pytest
from bridge.db import Db
from bridge.event_repository import EventRepository
from bridge.models import Event


@pytest.mark.asyncio
async def test_add_persists_event_and_returns_row(tmp_path: Path) -> None:
    database = Db(tmp_path / "event-repository.sqlite")
    await database.init()

    try:
        async with database.sessionmaker.begin() as session:
            repository = EventRepository(session)
            event_row = await repository.add("command", "play")

        assert event_row.id == 1
        assert event_row.kind == "command"
        assert event_row.data == "play"

        async with database.sessionmaker() as session:
            stored_event = await session.get(Event, event_row.id)

            assert stored_event is not None
            assert stored_event.kind == "command"
            assert stored_event.data == "play"
            assert stored_event.created_at == event_row.created_at.replace(tzinfo=None)
            assert stored_event.updated_at == event_row.updated_at.replace(tzinfo=None)
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_list_recent_returns_latest_events_in_oldest_first_order(
    tmp_path: Path,
) -> None:
    database = Db(tmp_path / "event-repository-list.sqlite")
    await database.init()

    try:
        async with database.sessionmaker.begin() as session:
            repository = EventRepository(session)
            await repository.add("command", "first")
            second_event = await repository.add("message", "second")
            third_event = await repository.add("command", "third")

        async with database.sessionmaker() as session:
            repository = EventRepository(session)
            recent_events = await repository.list_recent(limit=2)

        assert [event.id for event in recent_events] == [
            second_event.id,
            third_event.id,
        ]
        assert [event.kind for event in recent_events] == ["message", "command"]
        assert [event.data for event in recent_events] == ["second", "third"]
    finally:
        await database.close()
