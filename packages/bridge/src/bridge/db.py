from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from bridge.models import Base

AsyncSessionmaker = async_sessionmaker[AsyncSession]


_BUSY_TIMEOUT_MS = 5000


@dataclass(init=False)
class JournalModeError(Exception):
    mode: str

    def __init__(self, mode: str) -> None:
        self.mode = mode
        super().__init__("Failed to set journal_mode to WAL")


class Db:
    def __init__(self, sqlite: Path) -> None:
        self._engine = create_async_engine(f"sqlite+aiosqlite:///{sqlite}")
        self._sessionmaker = AsyncSessionmaker(self._engine, expire_on_commit=False)

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    @property
    def sessionmaker(self) -> AsyncSessionmaker:
        return self._sessionmaker

    async def init(self) -> None:
        event.listen(self._engine.sync_engine, "connect", _on_connect)

        async with self._engine.connect() as connection:
            result = await connection.exec_driver_sql("PRAGMA journal_mode=WAL;")
            mode = str(result.scalar_one())
            self._check_journal_mode(mode)

        async with self._engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    def _check_journal_mode(self, mode: str) -> None:
        if mode.lower() != "wal":
            raise JournalModeError(mode)

    async def close(self) -> None:
        self._remove_connect_listener(
            contains=event.contains(self._engine.sync_engine, "connect", _on_connect)
        )
        await self._engine.dispose()

    def _remove_connect_listener(self, *, contains: bool) -> None:
        if not contains:
            return

        event.remove(self._engine.sync_engine, "connect", _on_connect)


class _DBAPICursorProtocol(Protocol):
    def close(self) -> None: ...
    def execute(self, operation: object) -> object: ...


class _DBAPIConnectionProtocol(Protocol):
    def cursor(self) -> _DBAPICursorProtocol: ...


def _on_connect(dbapi_connection: _DBAPIConnectionProtocol, _: object) -> None:
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS};")
    finally:
        cursor.close()
