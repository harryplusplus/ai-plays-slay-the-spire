from pathlib import Path

import pytest
from aiosqlite import Connection
from core import db

BUSY_TIMEOUT_MS = 5000


async def read_scalar(connection: Connection, query: str) -> object | None:
    async with connection.execute(query) as cursor:
        row = await cursor.fetchone()

    return None if row is None else row[0]


@pytest.mark.asyncio
async def test_create_returns_open_connection(tmp_path: Path) -> None:
    sqlite_file = tmp_path / "test.sqlite"

    connection = await db.create(sqlite_file)

    try:
        assert sqlite_file.exists()
        assert await read_scalar(connection, "SELECT 1;") == 1
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_set_journal_mode_returns_wal(tmp_path: Path) -> None:
    connection = await db.create(tmp_path / "journal.sqlite")

    try:
        mode = await db.set_journal_mode(connection)

        assert mode == "wal"
    finally:
        await connection.close()


def test_check_journal_mode_accepts_wal_case_insensitively() -> None:
    db.check_journal_mode("WAL")


def test_check_journal_mode_raises_for_non_wal_mode() -> None:
    with pytest.raises(db.JournalModeError) as exc_info:
        db.check_journal_mode("delete")

    assert str(exc_info.value) == "Failed to set journal_mode to WAL"
    assert exc_info.value.mode == "delete"


@pytest.mark.asyncio
async def test_configure_sets_expected_sqlite_pragmas(tmp_path: Path) -> None:
    connection = await db.create(tmp_path / "configure.sqlite")

    try:
        await db.configure(connection)

        assert await read_scalar(connection, "PRAGMA journal_mode;") == "wal"
        assert await read_scalar(connection, "PRAGMA synchronous;") == 1
        assert await read_scalar(connection, "PRAGMA busy_timeout;") == BUSY_TIMEOUT_MS
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_try_init_runs_initializer_and_keeps_connection_open(
    tmp_path: Path,
) -> None:
    connection = await db.create(tmp_path / "init-success.sqlite")
    initialized_connection: Connection | None = None

    async def initializer(candidate: Connection) -> None:
        nonlocal initialized_connection

        initialized_connection = candidate
        await candidate.execute("CREATE TABLE initialized(id INTEGER PRIMARY KEY);")

    try:
        await db.try_init(connection, initializer)

        assert initialized_connection is connection
        assert (
            await read_scalar(
                connection,
                (
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name='initialized';"
                ),
            )
            == "initialized"
        )
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_try_init_closes_connection_and_raises_init_error(
    tmp_path: Path,
) -> None:
    connection = await db.create(tmp_path / "init-failure.sqlite")
    cause = ValueError("boom")

    async def initializer(_: Connection) -> None:
        raise cause

    with pytest.raises(db.InitError) as exc_info:
        await db.try_init(connection, initializer)

    assert exc_info.value.__cause__ is cause

    with pytest.raises(ValueError, match="no active connection"):
        await connection.execute("SELECT 1;")
