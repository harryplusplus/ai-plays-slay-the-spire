from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import TracebackType
from typing import Protocol, Self

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.models import Base

AsyncSessionmaker = async_sessionmaker[AsyncSession]


_BUSY_TIMEOUT_MS = 5000


@dataclass(init=False)
class JournalModeError(Exception):
    mode: str

    def __init__(self, mode: str) -> None:
        self.mode = mode
        super().__init__("Failed to set journal_mode to WAL")


class _State(StrEnum):
    IDLE = "idle"
    OPENED = "opened"
    CLOSED = "closed"


class Db:
    def __init__(self, sqlite: Path, *, should_create_schema: bool = False) -> None:
        self._engine = create_async_engine(f"sqlite+aiosqlite:///{sqlite}")
        self._sessionmaker = AsyncSessionmaker(self._engine, expire_on_commit=False)
        self._should_create_schema = should_create_schema
        self._state = _State.IDLE

    @property
    def engine(self) -> AsyncEngine:
        self._require_opened(self._state)
        return self._engine

    @property
    def sessionmaker(self) -> AsyncSessionmaker:
        self._require_opened(self._state)
        return self._sessionmaker

    async def open(self) -> None:
        self._require_idle(self._state)

        try:
            event.listen(self._engine.sync_engine, "connect", _on_connect)

            async with self._engine.connect() as connection:
                result = await connection.exec_driver_sql("PRAGMA journal_mode=WAL;")
                mode = str(result.scalar_one())
                self._check_journal_mode(mode)

            await self._create_schema(should_create_schema=self._should_create_schema)
        except Exception:
            await self.close()
            raise

        self._state = _State.OPENED

    def _check_journal_mode(self, mode: str) -> None:
        if mode.lower() != "wal":
            raise JournalModeError(mode)

    async def _create_schema(self, *, should_create_schema: bool) -> None:
        if not should_create_schema:
            return

        async with self._engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        await self._close(self._state)

    async def _close(self, state: _State) -> None:
        if state is _State.CLOSED:
            return

        self._state = _State.CLOSED
        self._remove_connect_listener(
            contains=event.contains(self._engine.sync_engine, "connect", _on_connect)
        )
        await self._engine.dispose()

    def _remove_connect_listener(self, *, contains: bool) -> None:
        if not contains:
            return

        event.remove(self._engine.sync_engine, "connect", _on_connect)

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

    def _require_idle(self, state: _State) -> None:
        if state is _State.OPENED:
            raise RuntimeError("Db is already opened.")
        if state is _State.CLOSED:
            raise RuntimeError("Db is already closed.")

    def _require_opened(self, state: _State) -> None:
        if state is _State.IDLE:
            raise RuntimeError("Db is not opened.")
        if state is _State.CLOSED:
            raise RuntimeError("Db is already closed.")


class _DBAPICursorProtocol(Protocol):
    def close(self) -> None: ...
    def execute(
        self,
        operation: object,
    ) -> object: ...


class _DBAPIConnectionProtocol(Protocol):
    def cursor(self) -> _DBAPICursorProtocol: ...


def _on_connect(dbapi_connection: _DBAPIConnectionProtocol, _: object) -> None:
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS};")
    finally:
        cursor.close()
