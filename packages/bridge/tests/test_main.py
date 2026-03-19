import asyncio
import io
from pathlib import Path

import pytest
from bridge import __main__, bridge
from bridge.message import MessageQueue
from core import db
from core.models import Event, PendingCommand
from core.pending_command_repository import AlchemyPendingCommandRepository

SKIPPED_PENDING_COMMANDS = 2


@pytest.mark.asyncio
async def test_process_next_iteration_stops_when_stop_event_is_set() -> None:
    message_queue = MessageQueue()
    stop_event = asyncio.Event()
    stop_event.set()

    engine = db.create_engine(Path(":memory:"))
    sessionmaker = db.create_sessionmaker(engine)

    try:
        should_continue = await bridge.process_next_iteration(
            sessionmaker,
            message_queue,
            stop_event,
            io.StringIO(),
        )

        assert should_continue is False
    finally:
        await db.close_engine(engine)


@pytest.mark.asyncio
async def test_process_next_iteration_prioritizes_message_over_pending_command(
    tmp_path: Path,
) -> None:
    sqlite_file = tmp_path / "iteration-priority.sqlite"
    engine = db.create_engine(sqlite_file)
    sessionmaker = db.create_sessionmaker(engine)
    message_queue = MessageQueue()
    stop_event = asyncio.Event()
    output_stream = io.StringIO()

    try:
        await db.init(engine)
        await db.init_dev(engine)

        async with sessionmaker.begin() as session:
            repository = AlchemyPendingCommandRepository(session)
            pending_command_id = await repository.add("play")

        message_queue.put_nowait("state")

        should_continue = await bridge.process_next_iteration(
            sessionmaker,
            message_queue,
            stop_event,
            output_stream,
        )

        assert should_continue is True
        assert output_stream.getvalue() == ""

        async with sessionmaker() as session:
            pending_command = await session.get(PendingCommand, pending_command_id)
            event = await session.get(Event, 1)

            assert pending_command is not None
            assert pending_command.status == "pending"
            assert event is not None
            assert event.kind == "message"
            assert event.data == "state"
    finally:
        await db.close_engine(engine)


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


@pytest.mark.asyncio
async def test_skip_pending_commands_at_startup_records_skipped_events(
    tmp_path: Path,
) -> None:
    sqlite_file = tmp_path / "skip-pending.sqlite"
    engine = db.create_engine(sqlite_file)
    sessionmaker = db.create_sessionmaker(engine)

    try:
        await db.init(engine)
        await db.init_dev(engine)

        async with sessionmaker.begin() as session:
            repository = AlchemyPendingCommandRepository(session)
            first_pending_command_id = await repository.add("play")
            second_pending_command_id = await repository.add("state")

        skipped_count = await bridge.skip_pending_commands_at_startup(
            sessionmaker,
        )

        assert skipped_count == SKIPPED_PENDING_COMMANDS

        async with sessionmaker() as session:
            first_pending_command = await session.get(
                PendingCommand,
                first_pending_command_id,
            )
            second_pending_command = await session.get(
                PendingCommand,
                second_pending_command_id,
            )
            first_event = await session.get(Event, 1)
            second_event = await session.get(Event, 2)

            assert first_pending_command is not None
            assert first_pending_command.status == "skipped"
            assert second_pending_command is not None
            assert second_pending_command.status == "skipped"
            assert first_event is not None
            assert first_event.kind == "command_skipped"
            assert first_event.data == "play"
            assert second_event is not None
            assert second_event.kind == "command_skipped"
            assert second_event.data == "state"
    finally:
        await db.close_engine(engine)


@pytest.mark.asyncio
async def test_process_next_pending_command_writes_stdout_and_records_event(
    tmp_path: Path,
) -> None:
    sqlite_file = tmp_path / "pending-command.sqlite"
    engine = db.create_engine(sqlite_file)
    sessionmaker = db.create_sessionmaker(engine)
    output_stream = io.StringIO()

    try:
        await db.init(engine)
        await db.init_dev(engine)

        async with sessionmaker.begin() as session:
            repository = AlchemyPendingCommandRepository(session)
            pending_command_id = await repository.add("play")

        processed = await bridge.process_next_pending_command(
            sessionmaker,
            output_stream,
        )

        assert processed is True
        assert output_stream.getvalue() == "play\n"

        async with sessionmaker() as session:
            pending_command = await session.get(PendingCommand, pending_command_id)
            event = await session.get(Event, 1)

            assert pending_command is not None
            assert pending_command.status == "recorded"
            assert event is not None
            assert event.kind == "command_recorded"
            assert event.data == "play"
    finally:
        await db.close_engine(engine)
