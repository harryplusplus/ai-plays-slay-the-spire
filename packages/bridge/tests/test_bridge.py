import asyncio
import io
from pathlib import Path
from typing import override

import pytest
from bridge import bridge
from bridge.message import Queue
from core import db
from core.models import Event, PendingCommand
from core.pending_command_repository import AlchemyPendingCommandRepository

SKIPPED_PENDING_COMMANDS = 2


class RecordingOutput(io.StringIO):
    flush_count: int

    def __init__(self) -> None:
        super().__init__()
        self.flush_count = 0

    @override
    def flush(self) -> None:
        super().flush()
        self.flush_count += 1


@pytest.mark.asyncio
async def test_record_message_event_persists_message_and_returns_id(
    tmp_path: Path,
) -> None:
    engine = db.create_engine(tmp_path / "record-message-event.sqlite")

    try:
        await db.init(engine)
        await db.init_dev(engine)
        sessionmaker = db.create_sessionmaker(engine)

        event_id = await bridge.record_message_event(sessionmaker, "state")

        assert event_id == 1

        async with sessionmaker() as session:
            event = await session.get(Event, event_id)

            assert event is not None
            assert event.kind == "message"
            assert event.data == "state"
    finally:
        await db.close_engine(engine)


@pytest.mark.asyncio
async def test_get_next_pending_command_returns_oldest_pending_command(
    tmp_path: Path,
) -> None:
    engine = db.create_engine(tmp_path / "get-next-pending-command.sqlite")

    try:
        await db.init(engine)
        await db.init_dev(engine)
        sessionmaker = db.create_sessionmaker(engine)

        async with sessionmaker.begin() as session:
            repository = AlchemyPendingCommandRepository(session)
            oldest_pending_id = await repository.add("play")
            recorded_pending_id = await repository.add("state")
            await repository.mark_recorded(recorded_pending_id)
            await repository.add("end")

        pending_command = await bridge.get_next_pending_command(sessionmaker)

        assert pending_command is not None
        assert pending_command.id == oldest_pending_id
        assert pending_command.command == "play"
        assert pending_command.status == "pending"
    finally:
        await db.close_engine(engine)


def test_write_command_writes_newline_and_flushes_output() -> None:
    output = RecordingOutput()

    bridge.write_command("play", output)

    assert output.getvalue() == "play\n"
    assert output.flush_count == 1


@pytest.mark.asyncio
async def test_process_after_write_command_records_event_and_marks_command(
    tmp_path: Path,
) -> None:
    engine = db.create_engine(tmp_path / "process-after-write-command.sqlite")

    try:
        await db.init(engine)
        await db.init_dev(engine)
        sessionmaker = db.create_sessionmaker(engine)

        async with sessionmaker.begin() as session:
            repository = AlchemyPendingCommandRepository(session)
            pending_command_id = await repository.add("play")

        event_id = await bridge.process_after_write_command(
            sessionmaker,
            pending_command_id,
            "play",
        )

        assert event_id == 1

        async with sessionmaker() as session:
            pending_command = await session.get(PendingCommand, pending_command_id)
            event = await session.get(Event, event_id)

            assert pending_command is not None
            assert pending_command.status == "recorded"
            assert event is not None
            assert event.kind == "command_recorded"
            assert event.data == "play"
    finally:
        await db.close_engine(engine)


@pytest.mark.asyncio
async def test_skip_pending_commands_at_startup_records_skipped_events(
    tmp_path: Path,
) -> None:
    engine = db.create_engine(tmp_path / "skip-pending.sqlite")

    try:
        await db.init(engine)
        await db.init_dev(engine)
        sessionmaker = db.create_sessionmaker(engine)

        async with sessionmaker.begin() as session:
            repository = AlchemyPendingCommandRepository(session)
            first_pending_command_id = await repository.add("play")
            second_pending_command_id = await repository.add("state")

        skipped_count = await bridge.skip_pending_commands(sessionmaker)

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
async def test_process_next_pending_command_writes_output_and_records_event(
    tmp_path: Path,
) -> None:
    engine = db.create_engine(tmp_path / "pending-command.sqlite")
    output = RecordingOutput()

    try:
        await db.init(engine)
        await db.init_dev(engine)
        sessionmaker = db.create_sessionmaker(engine)

        async with sessionmaker.begin() as session:
            repository = AlchemyPendingCommandRepository(session)
            pending_command_id = await repository.add("play")

        processed = await bridge.process_next_pending_command(sessionmaker, output)

        assert processed is True
        assert output.getvalue() == "play\n"
        assert output.flush_count == 1

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


@pytest.mark.asyncio
async def test_process_next_pending_command_returns_false_without_pending_command(
    tmp_path: Path,
) -> None:
    engine = db.create_engine(tmp_path / "no-pending-command.sqlite")
    output = RecordingOutput()

    try:
        await db.init(engine)
        await db.init_dev(engine)
        sessionmaker = db.create_sessionmaker(engine)

        processed = await bridge.process_next_pending_command(sessionmaker, output)

        assert processed is False
        assert output.getvalue() == ""
        assert output.flush_count == 0
    finally:
        await db.close_engine(engine)


@pytest.mark.asyncio
async def test_process_next_stops_when_stop_event_is_set() -> None:
    message_queue = Queue()
    stop_event = asyncio.Event()
    stop_event.set()

    engine = db.create_engine(Path(":memory:"))
    sessionmaker = db.create_sessionmaker(engine)

    try:
        should_continue = await bridge.process_next(
            sessionmaker,
            message_queue,
            stop_event,
        )

        assert should_continue is False
    finally:
        await db.close_engine(engine)


@pytest.mark.asyncio
async def test_process_next_stops_when_message_queue_signals_eof() -> None:
    message_queue = Queue()
    message_queue.put_nowait(None)
    stop_event = asyncio.Event()

    engine = db.create_engine(Path(":memory:"))
    sessionmaker = db.create_sessionmaker(engine)

    try:
        should_continue = await bridge.process_next(
            sessionmaker,
            message_queue,
            stop_event,
        )

        assert should_continue is False
    finally:
        await db.close_engine(engine)


@pytest.mark.asyncio
async def test_process_next_prioritizes_message_over_pending_command(
    tmp_path: Path,
) -> None:
    engine = db.create_engine(tmp_path / "iteration-priority.sqlite")
    message_queue = Queue()
    stop_event = asyncio.Event()
    output = RecordingOutput()

    try:
        await db.init(engine)
        await db.init_dev(engine)
        sessionmaker = db.create_sessionmaker(engine)

        async with sessionmaker.begin() as session:
            repository = AlchemyPendingCommandRepository(session)
            pending_command_id = await repository.add("play")

        message_queue.put_nowait("state")

        should_continue = await bridge.process_next(
            sessionmaker,
            message_queue,
            stop_event,
            output,
        )

        assert should_continue is True
        assert output.getvalue() == ""
        assert output.flush_count == 0

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
async def test_process_next_processes_pending_command_without_message(
    tmp_path: Path,
) -> None:
    engine = db.create_engine(tmp_path / "iteration-pending.sqlite")
    message_queue = Queue()
    stop_event = asyncio.Event()
    output = RecordingOutput()

    try:
        await db.init(engine)
        await db.init_dev(engine)
        sessionmaker = db.create_sessionmaker(engine)

        async with sessionmaker.begin() as session:
            repository = AlchemyPendingCommandRepository(session)
            pending_command_id = await repository.add("play")

        should_continue = await bridge.process_next(
            sessionmaker,
            message_queue,
            stop_event,
            output,
        )

        assert should_continue is True
        assert output.getvalue() == "play\n"
        assert output.flush_count == 1

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


@pytest.mark.asyncio
async def test_process_next_sleeps_when_message_and_pending_are_absent(
    tmp_path: Path,
) -> None:
    engine = db.create_engine(tmp_path / "idle-iteration.sqlite")
    message_queue = Queue()
    stop_event = asyncio.Event()
    output = RecordingOutput()

    try:
        await db.init(engine)
        await db.init_dev(engine)
        sessionmaker = db.create_sessionmaker(engine)

        should_continue = await bridge.process_next(
            sessionmaker,
            message_queue,
            stop_event,
            output,
        )

        assert should_continue is True
        assert output.getvalue() == ""
        assert output.flush_count == 0

        async with sessionmaker() as session:
            event = await session.get(Event, 1)

            assert event is None
    finally:
        await db.close_engine(engine)


@pytest.mark.asyncio
async def test_run_skips_pending_commands_before_processing_messages(
    tmp_path: Path,
) -> None:
    engine = db.create_engine(tmp_path / "run.sqlite")
    message_queue = Queue()
    stop_event = asyncio.Event()
    output = RecordingOutput()

    try:
        await db.init(engine)
        await db.init_dev(engine)
        sessionmaker = db.create_sessionmaker(engine)

        async with sessionmaker.begin() as session:
            repository = AlchemyPendingCommandRepository(session)
            pending_command_id = await repository.add("play")

        message_queue.put_nowait("state")
        message_queue.put_nowait(None)

        await bridge.run(sessionmaker, message_queue, stop_event, output)

        assert output.getvalue() == ""
        assert output.flush_count == 0

        async with sessionmaker() as session:
            pending_command = await session.get(PendingCommand, pending_command_id)
            skipped_event = await session.get(Event, 1)
            message_event = await session.get(Event, 2)

            assert pending_command is not None
            assert pending_command.status == "skipped"
            assert skipped_event is not None
            assert skipped_event.kind == "command_skipped"
            assert skipped_event.data == "play"
            assert message_event is not None
            assert message_event.kind == "message"
            assert message_event.data == "state"
    finally:
        await db.close_engine(engine)
