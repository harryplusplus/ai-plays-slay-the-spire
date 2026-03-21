from pathlib import Path

import pytest
from core.db import Db
from core.event_repository import AlchemyEventRepository
from core.models import Event


@pytest.mark.asyncio
async def test_add_persists_events_and_returns_ids(tmp_path: Path) -> None:
    db = Db(tmp_path / "events-repository.sqlite", should_create_schema=True)

    async with db:
        async with db.sessionmaker.begin() as session:
            repository = AlchemyEventRepository(session)
            command_event_id = await repository.add("command_recorded", "state")
            message_event_id = await repository.add("message", "battle started")

        assert command_event_id == 1
        assert message_event_id == command_event_id + 1

        async with db.sessionmaker() as session:
            command_event = await session.get(Event, command_event_id)
            message_event = await session.get(Event, message_event_id)

            assert command_event is not None
            assert command_event.kind == "command_recorded"
            assert command_event.data == "state"

            assert message_event is not None
            assert message_event.kind == "message"
            assert message_event.data == "battle started"


@pytest.mark.asyncio
async def test_list_recent_returns_latest_events_up_to_limit_in_oldest_first_order(
    tmp_path: Path,
) -> None:
    db = Db(tmp_path / "events-list-recent.sqlite", should_create_schema=True)

    async with db:
        async with db.sessionmaker.begin() as session:
            repository = AlchemyEventRepository(session)
            await repository.add("command_recorded", "first")
            second_event_id = await repository.add("message", "second")
            third_event_id = await repository.add("command_skipped", "third")

        async with db.sessionmaker() as session:
            repository = AlchemyEventRepository(session)
            recent_events = await repository.list_recent(limit=2)

            assert [event.id for event in recent_events] == [
                second_event_id,
                third_event_id,
            ]
            assert [event.kind for event in recent_events] == [
                "message",
                "command_skipped",
            ]
            assert [event.data for event in recent_events] == ["second", "third"]
