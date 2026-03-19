import asyncio
import io
from pathlib import Path

import pytest
from bridge import __main__
from bridge.message import MessageQueue
from core import db
from core.models import Event


@pytest.mark.asyncio
async def test_main_persists_received_message_events(tmp_path: Path) -> None:
    sqlite_file = tmp_path / "bridge.sqlite"
    engine = db.create_engine(sqlite_file)
    sessionmaker = db.create_sessionmaker(engine)
    message_queue = MessageQueue()
    stop_event = asyncio.Event()
    message_queue.put_nowait("play")
    message_queue.put_nowait(None)

    await __main__.main(
        engine,
        sessionmaker,
        message_queue,
        stop_event,
        io.StringIO(),
    )

    verify_engine = db.create_engine(sqlite_file)
    verify_sessionmaker = db.create_sessionmaker(verify_engine)
    try:
        async with verify_sessionmaker() as session:
            event = await session.get(Event, 1)

            assert event is not None
            assert event.kind == "message"
            assert event.data == "play"
    finally:
        await db.close_engine(verify_engine)
