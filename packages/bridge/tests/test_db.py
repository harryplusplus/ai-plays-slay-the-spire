from pathlib import Path

import pytest
from bridge import db
from sqlalchemy import event, select
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


def test_journal_mode_error_stores_mode_and_message() -> None:
    error = db.JournalModeError("delete")

    assert str(error) == "Failed to set journal_mode to WAL"
    assert error.mode == "delete"


def test_on_connect_sets_pragmas_and_closes_cursor() -> None:
    connection = RecordingDBAPIConnection()

    db._on_connect(connection, object())

    assert connection.recording_cursor.queries == [
        "PRAGMA synchronous=NORMAL;",
        f"PRAGMA busy_timeout={db._BUSY_TIMEOUT_MS};",
    ]
    assert connection.recording_cursor.closed is True


@pytest.mark.asyncio
async def test_init_creates_schema_and_close_removes_connect_listener(
    tmp_path: Path,
) -> None:
    database = db.Db(tmp_path / "bridge.sqlite")

    assert (
        event.contains(database.engine.sync_engine, "connect", db._on_connect) is False
    )

    await database.init()

    try:
        assert event.contains(database.engine.sync_engine, "connect", db._on_connect)

        async with database.engine.connect() as connection:
            assert await read_scalar(connection, "PRAGMA journal_mode;") == "wal"
            assert await read_scalar(connection, "PRAGMA synchronous;") == 1
            assert (
                await read_scalar(connection, "PRAGMA busy_timeout;")
                == db._BUSY_TIMEOUT_MS
            )
            assert await read_table_name(connection, "command_ids") == "command_ids"
            assert await read_table_name(connection, "events") == "events"

        async with database.sessionmaker() as session:
            assert await session.scalar(select(1)) == 1
    finally:
        await database.close()

    assert (
        event.contains(database.engine.sync_engine, "connect", db._on_connect) is False
    )


@pytest.mark.asyncio
async def test_close_is_noop_when_connect_listener_is_missing(tmp_path: Path) -> None:
    database = db.Db(tmp_path / "bridge-close.sqlite")

    await database.close()

    assert (
        event.contains(database.engine.sync_engine, "connect", db._on_connect) is False
    )


@pytest.mark.asyncio
async def test_init_raises_journal_mode_error_when_wal_is_unavailable() -> None:
    database = db.Db(Path(":memory:"))

    try:
        with pytest.raises(db.JournalModeError) as exc_info:
            await database.init()
    finally:
        await database.close()

    assert exc_info.value.mode == "memory"
    assert (
        event.contains(database.engine.sync_engine, "connect", db._on_connect) is False
    )
