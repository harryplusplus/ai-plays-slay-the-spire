from pathlib import Path

import pytest
from bridge.db import Db
from bridge.event_service import EventService


@pytest.mark.asyncio
async def test_add_persists_event_and_returns_it(tmp_path: Path) -> None:
    database = Db(tmp_path / "event-service.sqlite")
    service = EventService(database)
    await database.init()

    try:
        event = await service.add("command", "play")

        assert event.id == 1
        assert event.kind == "command"
        assert event.data == "play"

        recent_events = await service.list_recent_events(limit=1)

        assert [item.id for item in recent_events] == [event.id]
        assert [item.kind for item in recent_events] == ["command"]
        assert [item.data for item in recent_events] == ["play"]
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_list_recent_events_returns_latest_items_in_oldest_first_order(
    tmp_path: Path,
) -> None:
    database = Db(tmp_path / "event-service-list.sqlite")
    service = EventService(database)
    await database.init()

    try:
        await service.add("command", "first")
        second_event = await service.add("message", "second")
        third_event = await service.add("command", "third")

        recent_events = await service.list_recent_events(limit=2)

        assert [item.id for item in recent_events] == [second_event.id, third_event.id]
        assert [item.kind for item in recent_events] == ["message", "command"]
        assert [item.data for item in recent_events] == ["second", "third"]
    finally:
        await database.close()
