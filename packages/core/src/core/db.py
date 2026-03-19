from collections.abc import Awaitable, Callable
from pathlib import Path

import aiosqlite
from aiosqlite import Connection


async def create(sqlite_file: Path) -> Connection:
    return await aiosqlite.connect(sqlite_file)


async def set_journal_mode(connection: Connection) -> str:
    async with connection.execute("PRAGMA journal_mode=WAL;") as cursor:
        row = await cursor.fetchone()

    mode = row[0] if row else None
    return str(mode)


def check_journal_mode(mode: str) -> None:
    if mode.lower() != "wal":
        raise RuntimeError(f"Failed to set journal_mode to WAL, got {mode}")


async def configure(connection: Connection) -> None:
    mode = await set_journal_mode(connection)
    check_journal_mode(mode)
    await connection.execute("PRAGMA synchronous=NORMAL;")
    await connection.execute("PRAGMA busy_timeout=5000;")


Initializer = Callable[[Connection], Awaitable[None]]


class InitError(Exception):
    def __init__(self) -> None:
        super().__init__("Failed to initialize database")


async def try_init(connection: Connection, initializer: Initializer) -> None:
    try:
        await initializer(connection)
    except Exception as e:
        await connection.close()
        raise InitError from e
