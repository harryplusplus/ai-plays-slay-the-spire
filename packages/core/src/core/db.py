from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import TracebackType
from typing import Protocol, Self

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.models import Base

BUSY_TIMEOUT_MS = 5000


class OnConnectCursor(Protocol):
    def execute(self, query: str) -> object: ...
    def close(self) -> None: ...


class OnConnectDBAPIConnection(Protocol):
    def cursor(self) -> OnConnectCursor: ...


def create_engine(sqlite_file: Path) -> AsyncEngine:
    return create_async_engine(f"sqlite+aiosqlite:///{sqlite_file}")


def on_connect(dbapi_connection: OnConnectDBAPIConnection, _: object) -> None:
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


AsyncSessionmaker = async_sessionmaker[AsyncSession]


class DbState(StrEnum):
    IDLE = "idle"
    OPENED = "opened"
    CLOSED = "closed"


class Db:
    def __init__(self, sqlite_file: Path, *, init_dev: bool = False) -> None:
        self._engine = create_engine(sqlite_file)
        self._sessionmaker = create_sessionmaker(self._engine)
        self._init_dev = init_dev
        self._state = DbState.IDLE

    @property
    def state(self) -> DbState:
        return self._state

    @property
    def engine(self) -> AsyncEngine:
        self._require_opened()
        return self._engine

    @property
    def sessionmaker(self) -> AsyncSessionmaker:
        self._require_opened()
        return self._sessionmaker

    async def open(self) -> None:
        if self._state is DbState.OPENED:
            raise RuntimeError("Db is already opened.")
        if self._state is DbState.CLOSED:
            raise RuntimeError("Db is already closed.")

        try:
            await init(self._engine)
            if self._init_dev:
                await init_dev(self._engine)
        except Exception:
            self._state = DbState.CLOSED
            await close_engine(self._engine)
            raise

        self._state = DbState.OPENED

    async def close(self) -> None:
        if self._state is DbState.CLOSED:
            return

        self._state = DbState.CLOSED
        await close_engine(self._engine)

    async def __aenter__(self) -> Self:
        await self.open()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    def _require_opened(self) -> None:
        if self._state is DbState.IDLE:
            raise RuntimeError("Db is not opened.")
        if self._state is DbState.CLOSED:
            raise RuntimeError("Db is already closed.")


def create_sessionmaker(engine: AsyncEngine) -> AsyncSessionmaker:
    return AsyncSessionmaker(engine, expire_on_commit=False)


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
