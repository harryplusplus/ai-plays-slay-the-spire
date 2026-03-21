from datetime import datetime
from pathlib import Path

import pytest
from core import db
from core.models import Event
from sqlalchemy import event, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncConnection


async def read_scalar(connection: AsyncConnection, query: str) -> object:
    result = await connection.exec_driver_sql(query)
    return result.scalar_one()


async def read_table_name(
    connection: AsyncConnection, table_name: str
) -> object | None:
    result = await connection.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?;",
        (table_name,),
    )
    return result.scalar_one_or_none()


class RecordingCursor:
    def __init__(self) -> None:
        self.queries: list[str] = []
        self.closed = False

    def execute(self, operation: object) -> None:
        self.queries.append(str(operation))

    def close(self) -> None:
        self.closed = True


class RecordingDBAPIConnection:
    def __init__(self) -> None:
        self.recording_cursor = RecordingCursor()

    def cursor(self) -> RecordingCursor:
        return self.recording_cursor


@pytest.mark.asyncio
async def test_check_journal_mode_validates_wal_case_insensitively(
    tmp_path: Path,
) -> None:
    database = db.Db(tmp_path / "journal.sqlite")

    try:
        database._check_journal_mode("WAL")

        with pytest.raises(db.JournalModeError) as exc_info:
            database._check_journal_mode("delete")
    finally:
        await database.close()

    assert str(exc_info.value) == "Failed to set journal_mode to WAL"
    assert exc_info.value.mode == "delete"


def test_on_connect_sets_pragmas_and_closes_cursor() -> None:
    connection = RecordingDBAPIConnection()

    db._on_connect(connection, object())

    assert connection.recording_cursor.queries == [
        "PRAGMA synchronous=NORMAL;",
        f"PRAGMA busy_timeout={db._BUSY_TIMEOUT_MS};",
    ]
    assert connection.recording_cursor.closed is True


@pytest.mark.asyncio
async def test_db_engine_and_sessionmaker_require_open(tmp_path: Path) -> None:
    database = db.Db(tmp_path / "access.sqlite")

    assert database._state is db._State.IDLE

    with pytest.raises(RuntimeError, match=r"Db is not opened\."):
        _ = database.engine

    with pytest.raises(RuntimeError, match=r"Db is not opened\."):
        _ = database.sessionmaker

    await database.open()

    try:
        assert database._state is db._State.OPENED
        assert event.contains(database._engine.sync_engine, "connect", db._on_connect)

        async with database.engine.connect() as connection:
            assert await read_scalar(connection, "PRAGMA journal_mode;") == "wal"
            assert await read_scalar(connection, "PRAGMA synchronous;") == 1
            assert (
                await read_scalar(connection, "PRAGMA busy_timeout;")
                == db._BUSY_TIMEOUT_MS
            )
            assert await read_table_name(connection, "events") is None
            assert await read_table_name(connection, "pending_commands") is None

        async with database.sessionmaker() as session:
            assert await session.scalar(select(1)) == 1
    finally:
        await database.close()

    assert database._state is db._State.CLOSED
    assert not event.contains(database._engine.sync_engine, "connect", db._on_connect)

    with pytest.raises(RuntimeError, match=r"Db is already closed\."):
        _ = database.engine

    with pytest.raises(RuntimeError, match=r"Db is already closed\."):
        _ = database.sessionmaker


@pytest.mark.asyncio
async def test_db_open_raises_when_already_opened(tmp_path: Path) -> None:
    database = db.Db(tmp_path / "reopen.sqlite")

    await database.open()

    try:
        with pytest.raises(RuntimeError, match=r"Db is already opened\."):
            await database.open()
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_db_async_context_manager_creates_schema_and_persists_events(
    tmp_path: Path,
) -> None:
    database = db.Db(tmp_path / "context.sqlite", should_create_schema=True)

    async with database as opened_database:
        assert opened_database is database
        assert database._state is db._State.OPENED

        async with database.engine.connect() as connection:
            assert await read_table_name(connection, "events") == "events"
            assert (
                await read_table_name(connection, "pending_commands")
                == "pending_commands"
            )

        async with database.sessionmaker() as session:
            event_row = Event(
                kind="command_recorded",
                data='{"command":"state","floor":1}',
            )
            session.add(event_row)

            await session.commit()

            event_id = event_row.id
            assert event_id == 1
            assert isinstance(event_row.created_at, datetime)
            assert isinstance(event_row.updated_at, datetime)

        async with database.sessionmaker() as session:
            loaded_event = await session.get(Event, event_id)

            assert loaded_event is not None
            assert loaded_event.kind == "command_recorded"
            assert loaded_event.data == '{"command":"state","floor":1}'

    assert database._state is db._State.CLOSED


@pytest.mark.asyncio
async def test_db_open_failure_closes_instance_and_removes_listener(
    tmp_path: Path,
) -> None:
    database = db.Db(tmp_path / "missing-parent" / "failure.sqlite")

    with pytest.raises(OperationalError, match="unable to open database file"):
        await database.open()

    assert database._state is db._State.CLOSED
    assert not event.contains(database._engine.sync_engine, "connect", db._on_connect)

    with pytest.raises(RuntimeError, match=r"Db is already closed\."):
        await database.open()

    with pytest.raises(RuntimeError, match=r"Db is already closed\."):
        _ = database.engine


@pytest.mark.asyncio
async def test_db_close_is_idempotent_without_opening(tmp_path: Path) -> None:
    database = db.Db(tmp_path / "close.sqlite")

    await database.close()

    assert database._state is db._State.CLOSED
    assert not event.contains(database._engine.sync_engine, "connect", db._on_connect)

    await database.close()

    assert database._state is db._State.CLOSED
