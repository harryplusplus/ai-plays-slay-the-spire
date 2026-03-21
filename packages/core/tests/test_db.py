from datetime import datetime
from pathlib import Path

import pytest
from core import db
from core.models import Event
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

BUSY_TIMEOUT_MS = 5000


async def read_scalar(connection: AsyncConnection, query: str) -> object | None:
    result = await connection.exec_driver_sql(query)
    return result.scalar_one_or_none()


class RecordingCursor:
    queries: list[str]
    closed: bool

    def __init__(self) -> None:
        self.queries = []
        self.closed = False

    def execute(self, query: str) -> None:
        self.queries.append(query)

    def close(self) -> None:
        self.closed = True


class RecordingDBAPIConnection:
    cursor_: RecordingCursor

    def __init__(self) -> None:
        self.cursor_ = RecordingCursor()

    def cursor(self) -> RecordingCursor:
        return self.cursor_


@pytest.mark.asyncio
async def test_create_engine_connects_to_sqlite_file(tmp_path: Path) -> None:
    sqlite_file = tmp_path / "test.sqlite"
    engine = db.create_engine(sqlite_file)

    try:
        assert isinstance(engine, AsyncEngine)

        async with engine.connect() as connection:
            assert await read_scalar(connection, "SELECT 1;") == 1

        assert sqlite_file.exists()
    finally:
        await db.close_engine(engine)


@pytest.mark.asyncio
async def test_init_sets_expected_sqlite_pragmas(tmp_path: Path) -> None:
    engine = db.create_engine(tmp_path / "init.sqlite")

    try:
        await db.init(engine)

        async with engine.connect() as connection:
            assert await read_scalar(connection, "PRAGMA journal_mode;") == "wal"
            assert await read_scalar(connection, "PRAGMA synchronous;") == 1
            assert (
                await read_scalar(connection, "PRAGMA busy_timeout;") == BUSY_TIMEOUT_MS
            )
    finally:
        await db.close_engine(engine)


def test_on_connect_sets_pragmas_and_closes_cursor() -> None:
    connection = RecordingDBAPIConnection()

    db.on_connect(connection, object())

    assert connection.cursor_.queries == [
        "PRAGMA synchronous=NORMAL;",
        f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS};",
    ]
    assert connection.cursor_.closed is True


@pytest.mark.asyncio
async def test_create_schema_dev_creates_events_and_pending_commands_tables(
    tmp_path: Path,
) -> None:
    engine = db.create_engine(tmp_path / "schema.sqlite")

    try:
        async with engine.begin() as connection:
            await db.create_schema_dev(connection)

        async with engine.connect() as connection:
            assert (
                await read_scalar(
                    connection,
                    (
                        "SELECT name FROM sqlite_master "
                        "WHERE type='table' AND name='events';"
                    ),
                )
                == "events"
            )
            assert (
                await read_scalar(
                    connection,
                    (
                        "SELECT name FROM sqlite_master "
                        "WHERE type='table' AND name='pending_commands';"
                    ),
                )
                == "pending_commands"
            )
    finally:
        await db.close_engine(engine)


@pytest.mark.asyncio
async def test_create_sessionmaker_persists_event_rows(tmp_path: Path) -> None:
    engine = db.create_engine(tmp_path / "events.sqlite")

    try:
        async with engine.begin() as connection:
            await db.create_schema_dev(connection)

        sessionmaker = db.create_sessionmaker(engine)

        async with sessionmaker() as session:
            event = Event(
                kind="command_recorded",
                data='{"command":"state","floor":1}',
            )
            session.add(event)

            await session.commit()

            event_id = event.id
            assert event_id == 1
            assert isinstance(event.created_at, datetime)
            assert isinstance(event.updated_at, datetime)

        async with sessionmaker() as session:
            loaded_event = await session.get(Event, event_id)

            assert loaded_event is not None
            assert loaded_event.kind == "command_recorded"
            assert loaded_event.data == '{"command":"state","floor":1}'
    finally:
        await db.close_engine(engine)


@pytest.mark.asyncio
async def test_set_journal_mode_returns_wal(tmp_path: Path) -> None:
    engine = db.create_engine(tmp_path / "journal.sqlite")

    try:
        async with engine.connect() as connection:
            mode = await db.set_journal_mode(connection)

        assert mode == "wal"
    finally:
        await db.close_engine(engine)


def test_check_journal_mode_accepts_wal_case_insensitively() -> None:
    db.check_journal_mode("WAL")


def test_check_journal_mode_raises_for_non_wal_mode() -> None:
    with pytest.raises(db.JournalModeError) as exc_info:
        db.check_journal_mode("delete")

    assert str(exc_info.value) == "Failed to set journal_mode to WAL"
    assert exc_info.value.mode == "delete"


@pytest.mark.asyncio
async def test_db_requires_open_before_engine_and_sessionmaker_access(
    tmp_path: Path,
) -> None:
    database = db.Db(tmp_path / "access.sqlite")

    assert database.state is db.DbState.IDLE

    with pytest.raises(RuntimeError, match=r"Db is not opened\."):
        _ = database.engine

    with pytest.raises(RuntimeError, match=r"Db is not opened\."):
        _ = database.sessionmaker


@pytest.mark.asyncio
async def test_db_open_initializes_engine_and_sessionmaker(tmp_path: Path) -> None:
    database = db.Db(tmp_path / "open.sqlite")

    await database.open()

    try:
        assert database.state is db.DbState.OPENED

        async with database.engine.connect() as connection:
            assert await read_scalar(connection, "PRAGMA journal_mode;") == "wal"
            assert await read_scalar(connection, "PRAGMA synchronous;") == 1
            assert (
                await read_scalar(connection, "PRAGMA busy_timeout;") == BUSY_TIMEOUT_MS
            )

        async with database.sessionmaker() as session:
            assert await session.scalar(select(1)) == 1
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_db_async_context_manager_opens_dev_schema_and_closes(
    tmp_path: Path,
) -> None:
    database = db.Db(tmp_path / "context.sqlite", init_dev=True)

    async with database as opened_database:
        assert opened_database is database
        assert database.state is db.DbState.OPENED

        async with database.engine.connect() as connection:
            assert (
                await read_scalar(
                    connection,
                    (
                        "SELECT name FROM sqlite_master "
                        "WHERE type='table' AND name='events';"
                    ),
                )
                == "events"
            )
            assert (
                await read_scalar(
                    connection,
                    (
                        "SELECT name FROM sqlite_master "
                        "WHERE type='table' AND name='pending_commands';"
                    ),
                )
                == "pending_commands"
            )

    assert database.state is db.DbState.CLOSED

    with pytest.raises(RuntimeError, match=r"Db is already closed\."):
        _ = database.engine


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
async def test_db_open_failure_closes_instance(tmp_path: Path) -> None:
    database = db.Db(tmp_path / "missing-parent" / "failure.sqlite")

    with pytest.raises(OperationalError, match="unable to open database file"):
        await database.open()

    assert database.state is db.DbState.CLOSED

    with pytest.raises(RuntimeError, match=r"Db is already closed\."):
        await database.open()

    with pytest.raises(RuntimeError, match=r"Db is already closed\."):
        _ = database.sessionmaker


@pytest.mark.asyncio
async def test_db_close_is_idempotent(tmp_path: Path) -> None:
    database = db.Db(tmp_path / "close.sqlite")

    await database.close()
    await database.close()

    assert database.state is db.DbState.CLOSED
