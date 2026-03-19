from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def create_engine(sqlite_file: Path) -> AsyncEngine:
    return create_async_engine(f"sqlite+aiosqlite:///{sqlite_file}")


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def create_schema_dev(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def set_journal_mode(connection: AsyncConnection) -> str:
    result = await connection.exec_driver_sql("PRAGMA journal_mode=WAL;")
    row = result.fetchone()
    mode = row[0] if row else None
    return str(mode)


@dataclass(init=False)
class JournalModeError(Exception):
    mode: str

    def __init__(self, mode: str) -> None:
        self.mode = mode
        super().__init__("Failed to set journal_mode to WAL")


def check_journal_mode(mode: str) -> None:
    if mode.lower() != "wal":
        raise JournalModeError(mode)


async def configure(connection: AsyncConnection) -> None:
    mode = await set_journal_mode(connection)
    check_journal_mode(mode)
    await connection.exec_driver_sql("PRAGMA synchronous=NORMAL;")
    await connection.exec_driver_sql("PRAGMA busy_timeout=5000;")
