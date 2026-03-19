from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import ConnectionPoolEntry

from core.models import Base

BUSY_TIMEOUT_MS = 5000


def create_engine(sqlite_file: Path) -> AsyncEngine:
    return create_async_engine(f"sqlite+aiosqlite:///{sqlite_file}")


def on_connect(dbapi_connection: DBAPIConnection, _: ConnectionPoolEntry) -> None:
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS};")
    finally:
        cursor.close()


def install_on_connect(engine: AsyncEngine) -> None:
    event.listen(engine.sync_engine, "connect", on_connect)


async def close_engine(engine: AsyncEngine) -> None:
    await engine.dispose()


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


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


async def init(engine: AsyncEngine) -> None:
    install_on_connect(engine)
    async with engine.connect() as connection:
        mode = await set_journal_mode(connection)
        check_journal_mode(mode)


async def create_schema_dev(connection: AsyncConnection) -> None:
    await connection.run_sync(Base.metadata.create_all)


async def init_dev(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await create_schema_dev(connection)
