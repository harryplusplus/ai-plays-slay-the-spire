from pathlib import Path

import pytest
from core import db
from core.event_repository import AlchemyEventRepository
from core.models import Event


@pytest.mark.asyncio
async def test_add_persists_events_and_returns_ids(tmp_path: Path) -> None:
    engine = db.create_engine(tmp_path / "events-repository.sqlite")

    try:
        await db.init(engine)
        await db.init_dev(engine)

        sessionmaker = db.create_sessionmaker(engine)

        async with sessionmaker.begin() as session:
            repository = AlchemyEventRepository(session)
            command_event_id = await repository.add("command_recorded", "state")
            message_event_id = await repository.add("message", "battle started")

        assert command_event_id == 1
        assert message_event_id == command_event_id + 1

        async with sessionmaker() as session:
            command_event = await session.get(Event, command_event_id)
            message_event = await session.get(Event, message_event_id)

            assert command_event is not None
            assert command_event.kind == "command_recorded"
            assert command_event.data == "state"

            assert message_event is not None
            assert message_event.kind == "message"
            assert message_event.data == "battle started"
    finally:
        await db.close_engine(engine)
