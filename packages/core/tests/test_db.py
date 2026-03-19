from pathlib import Path

import pytest
from core import db
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from sqlalchemy.orm import Mapped, mapped_column

BUSY_TIMEOUT_MS = 5000


class ExampleNote(db.Base):
    __tablename__ = "example_note"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()


async def read_scalar(connection: AsyncConnection, query: str) -> object | None:
    result = await connection.exec_driver_sql(query)
    return result.scalar_one_or_none()


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
async def test_create_schema_dev_creates_registered_tables(tmp_path: Path) -> None:
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
                        "WHERE type='table' AND name='example_note';"
                    ),
                )
                == "example_note"
            )
    finally:
        await db.close_engine(engine)


@pytest.mark.asyncio
async def test_create_sessionmaker_persists_rows_without_expiring_attributes(
    tmp_path: Path,
) -> None:
    engine = db.create_engine(tmp_path / "session.sqlite")

    try:
        async with engine.begin() as connection:
            await db.create_schema_dev(connection)

        sessionmaker = db.create_sessionmaker(engine)

        async with sessionmaker() as session:
            note = ExampleNote(name="first")
            session.add(note)

            await session.commit()

            note_id = note.id
            assert note_id == 1
            assert note.name == "first"

        async with sessionmaker() as session:
            loaded_note = await session.get(ExampleNote, note_id)

            assert loaded_note is not None
            assert loaded_note.name == "first"
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
async def test_configure_sets_expected_sqlite_pragmas(tmp_path: Path) -> None:
    engine = db.create_engine(tmp_path / "configure.sqlite")

    try:
        async with engine.connect() as connection:
            await db.configure(connection)

            assert await read_scalar(connection, "PRAGMA journal_mode;") == "wal"
            assert await read_scalar(connection, "PRAGMA synchronous;") == 1
            assert (
                await read_scalar(connection, "PRAGMA busy_timeout;") == BUSY_TIMEOUT_MS
            )
    finally:
        await db.close_engine(engine)
