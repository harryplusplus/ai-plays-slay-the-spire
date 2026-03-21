import asyncio
import io
from contextlib import redirect_stdout
from pathlib import Path

import pytest
from bridge import bridge
from bridge.message import Queue
from core.db import Db
from core.models import Event, PendingCommand
from core.pending_command_repository import AlchemyPendingCommandRepository
from typing_extensions import override

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


def create_db(tmp_path: Path, sqlite_file: str) -> Db:
    return Db(tmp_path / sqlite_file, should_create_schema=True)


@pytest.mark.asyncio
async def test_record_message_event_persists_message_and_returns_id(
    tmp_path: Path,
) -> None:
    db = create_db(tmp_path, "record-message-event.sqlite")

    async with db:
        event_id = await bridge._record_message_event(db.sessionmaker, "state")
        assert event_id == 1

        async with db.sessionmaker() as session:
            event = await session.get(Event, event_id)

            assert event is not None
            assert event.kind == "message"
            assert event.data == "state"


@pytest.mark.asyncio
async def test_get_next_pending_command_returns_oldest_pending_command(
    tmp_path: Path,
) -> None:
    db = create_db(tmp_path, "get-next-pending-command.sqlite")

    async with db:
        async with db.sessionmaker.begin() as session:
            repository = AlchemyPendingCommandRepository(session)
            oldest_pending_id = await repository.add("play")
            recorded_pending_id = await repository.add("state")
            await repository.mark_recorded(recorded_pending_id)
            await repository.add("end")

        pending_command = await bridge._get_next_pending_command(db.sessionmaker)

        assert pending_command is not None
        assert pending_command.id == oldest_pending_id
        assert pending_command.command == "play"
        assert pending_command.status == "pending"


@pytest.mark.asyncio
async def test_get_next_pending_command_returns_none_without_pending_command(
    tmp_path: Path,
) -> None:
    db = create_db(tmp_path, "get-next-pending-command-none.sqlite")

    async with db:
        pending_command = await bridge._get_next_pending_command(db.sessionmaker)

        assert pending_command is None


def test_write_command_writes_newline_and_flushes_output() -> None:
    output = RecordingOutput()

    bridge._write_command("play", output)

    assert output.getvalue() == "play\n"
    assert output.flush_count == 1


def test_write_command_uses_stdout_when_output_is_none() -> None:
    output = RecordingOutput()

    with redirect_stdout(output):
        bridge._write_command("play")

    assert output.getvalue() == "play\n"
    assert output.flush_count == 1


@pytest.mark.asyncio
async def test_process_after_write_command_records_event_and_marks_command(
    tmp_path: Path,
) -> None:
    db = create_db(tmp_path, "process-after-write-command.sqlite")

    async with db:
        async with db.sessionmaker.begin() as session:
            repository = AlchemyPendingCommandRepository(session)
            pending_command_id = await repository.add("play")

        event_id = await bridge._process_after_write_command(
            db.sessionmaker,
            pending_command_id,
            "play",
        )

        assert event_id == 1

        async with db.sessionmaker() as session:
            pending_command = await session.get(PendingCommand, pending_command_id)
            event = await session.get(Event, event_id)

            assert pending_command is not None
            assert pending_command.status == "recorded"
            assert event is not None
            assert event.kind == "command_recorded"
            assert event.data == "play"


@pytest.mark.asyncio
async def test_skip_pending_commands_at_startup_records_skipped_events(
    tmp_path: Path,
) -> None:
    db = create_db(tmp_path, "skip-pending.sqlite")

    async with db:
        async with db.sessionmaker.begin() as session:
            repository = AlchemyPendingCommandRepository(session)
            first_pending_command_id = await repository.add("play")
            second_pending_command_id = await repository.add("state")

        skipped_count = await bridge._skip_pending_commands(db.sessionmaker)

        assert skipped_count == SKIPPED_PENDING_COMMANDS

        async with db.sessionmaker() as session:
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


@pytest.mark.asyncio
async def test_skip_pending_commands_returns_zero_without_pending_commands(
    tmp_path: Path,
) -> None:
    db = create_db(tmp_path, "skip-pending-none.sqlite")

    async with db:
        skipped_count = await bridge._skip_pending_commands(db.sessionmaker)

        assert skipped_count == 0


@pytest.mark.asyncio
async def test_process_next_pending_command_writes_output_and_records_event(
    tmp_path: Path,
) -> None:
    db = create_db(tmp_path, "pending-command.sqlite")
    output = RecordingOutput()

    async with db:
        async with db.sessionmaker.begin() as session:
            repository = AlchemyPendingCommandRepository(session)
            pending_command_id = await repository.add("play")

        processed = await bridge._process_next_pending_command(
            db.sessionmaker,
            output,
        )

        assert processed is True
        assert output.getvalue() == "play\n"
        assert output.flush_count == 1

        async with db.sessionmaker() as session:
            pending_command = await session.get(PendingCommand, pending_command_id)
            event = await session.get(Event, 1)

            assert pending_command is not None
            assert pending_command.status == "recorded"
            assert event is not None
            assert event.kind == "command_recorded"
            assert event.data == "play"


@pytest.mark.asyncio
async def test_process_next_pending_command_returns_false_without_pending_command(
    tmp_path: Path,
) -> None:
    db = create_db(tmp_path, "no-pending-command.sqlite")
    output = RecordingOutput()

    async with db:
        processed = await bridge._process_next_pending_command(
            db.sessionmaker,
            output,
        )

        assert processed is False
        assert output.getvalue() == ""
        assert output.flush_count == 0


@pytest.mark.asyncio
async def test_process_next_stops_when_stop_event_is_set(tmp_path: Path) -> None:
    message_queue = Queue()
    stop_event = asyncio.Event()
    stop_event.set()
    db = create_db(tmp_path, "stop-event.sqlite")

    async with db:
        should_continue = await bridge._process_next(
            db.sessionmaker,
            message_queue,
            stop_event,
        )

        assert should_continue is False


@pytest.mark.asyncio
async def test_process_next_stops_when_message_queue_signals_eof(
    tmp_path: Path,
) -> None:
    message_queue = Queue()
    message_queue.put_nowait(None)
    stop_event = asyncio.Event()
    db = create_db(tmp_path, "message-eof.sqlite")

    async with db:
        should_continue = await bridge._process_next(
            db.sessionmaker,
            message_queue,
            stop_event,
        )

        assert should_continue is False


@pytest.mark.asyncio
async def test_process_next_prioritizes_message_over_pending_command(
    tmp_path: Path,
) -> None:
    db = create_db(tmp_path, "iteration-priority.sqlite")
    message_queue = Queue()
    stop_event = asyncio.Event()
    output = RecordingOutput()

    async with db:
        async with db.sessionmaker.begin() as session:
            repository = AlchemyPendingCommandRepository(session)
            pending_command_id = await repository.add("play")

        message_queue.put_nowait("state")

        should_continue = await bridge._process_next(
            db.sessionmaker,
            message_queue,
            stop_event,
            output,
        )

        assert should_continue is True
        assert output.getvalue() == ""
        assert output.flush_count == 0

        async with db.sessionmaker() as session:
            pending_command = await session.get(PendingCommand, pending_command_id)
            event = await session.get(Event, 1)

            assert pending_command is not None
            assert pending_command.status == "pending"
            assert event is not None
            assert event.kind == "message"
            assert event.data == "state"


@pytest.mark.asyncio
async def test_process_next_processes_pending_command_without_message(
    tmp_path: Path,
) -> None:
    db = create_db(tmp_path, "iteration-pending.sqlite")
    message_queue = Queue()
    stop_event = asyncio.Event()
    output = RecordingOutput()

    async with db:
        async with db.sessionmaker.begin() as session:
            repository = AlchemyPendingCommandRepository(session)
            pending_command_id = await repository.add("play")

        should_continue = await bridge._process_next(
            db.sessionmaker,
            message_queue,
            stop_event,
            output,
        )

        assert should_continue is True
        assert output.getvalue() == "play\n"
        assert output.flush_count == 1

        async with db.sessionmaker() as session:
            pending_command = await session.get(PendingCommand, pending_command_id)
            event = await session.get(Event, 1)

            assert pending_command is not None
            assert pending_command.status == "recorded"
            assert event is not None
            assert event.kind == "command_recorded"
            assert event.data == "play"


@pytest.mark.asyncio
async def test_process_next_sleeps_when_message_and_pending_are_absent(
    tmp_path: Path,
) -> None:
    db = create_db(tmp_path, "idle-iteration.sqlite")
    message_queue = Queue()
    stop_event = asyncio.Event()
    output = RecordingOutput()

    async with db:
        should_continue = await bridge._process_next(
            db.sessionmaker,
            message_queue,
            stop_event,
            output,
        )

        assert should_continue is True
        assert output.getvalue() == ""
        assert output.flush_count == 0

        async with db.sessionmaker() as session:
            event = await session.get(Event, 1)

            assert event is None


@pytest.mark.asyncio
async def test_run_writes_ready_and_processes_messages_after_skipping_pending_commands(
    tmp_path: Path,
) -> None:
    db = create_db(tmp_path, "run.sqlite")
    message_queue = Queue()
    stop_event = asyncio.Event()
    output = RecordingOutput()

    async with db:
        async with db.sessionmaker.begin() as session:
            repository = AlchemyPendingCommandRepository(session)
            pending_command_id = await repository.add("play")

        message_queue.put_nowait("state")
        message_queue.put_nowait(None)

        await bridge.run(db.sessionmaker, message_queue, stop_event, output)

        assert output.getvalue() == "ready\n"
        assert output.flush_count == 1

        async with db.sessionmaker() as session:
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
