import asyncio
import logging
import signal
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import override

import uvicorn
import websockets
from fastapi import FastAPI

logger = logging.getLogger(__name__)

_DB_PATH = Path.home() / ".sts" / "proxy.db"

_SQL_INIT = """
CREATE TABLE IF NOT EXISTS command_id_counter (
    command_id INTEGER NOT NULL DEFAULT 0
)
"""
_SQL_NEXT = """
INSERT OR IGNORE INTO command_id_counter (rowid) VALUES (1);
UPDATE command_id_counter SET command_id = command_id + 1 RETURNING command_id
"""


def next_command_id(db: sqlite3.Connection) -> int:
    row = db.execute(_SQL_NEXT).fetchone()
    db.commit()
    return row[0]


app = FastAPI()


@dataclass(slots=True, kw_only=True)
class AppState:
    db: sqlite3.Connection
    pending: dict[int, asyncio.Future[str]] = field(
        default_factory=dict[int, asyncio.Future[str]],
    )
    ws: websockets.ClientConnection | None = None


async def _ws_loop(app_state: AppState) -> None:
    async for message in app_state.ws:  # type: ignore[union-attr]:
        logger.debug("received from bridge: %s", message)


async def _run(server: uvicorn.Server, app_state: AppState) -> None:
    async with websockets.connect("ws://127.0.0.1:8765/ws") as ws:
        app_state.ws = ws
        ws_task = asyncio.create_task(_ws_loop(app_state))
        server_task = asyncio.create_task(server.serve())

        done, _ = await asyncio.wait(
            [ws_task, server_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        if server_task not in done:
            server.should_exit = True
            await server_task

        ws_task.cancel()
        await asyncio.gather(ws_task, return_exceptions=True)


def init_logger() -> None:
    class Formatter(logging.Formatter):
        @override
        def formatTime(
            self,
            record: logging.LogRecord,
            datefmt: str | None = None,
        ) -> str:
            return (
                datetime.fromtimestamp(record.created)
                .astimezone()
                .isoformat(timespec="milliseconds")
            )

    handler = RotatingFileHandler(
        Path.home() / ".sts" / "logs" / "proxy.log",
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(
        Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"),
    )

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)


def main() -> None:
    init_logger()

    logger.info("started.")
    with closing(sqlite3.connect(_DB_PATH)) as db:
        with db:
            db.execute(_SQL_INIT)

        app_state = AppState(db=db)
        app.state.app_state = app_state

        with asyncio.Runner() as runner:
            loop = runner.get_loop()
            config = uvicorn.Config(app, host="127.0.0.1", port=8766, log_config=None)
            server = uvicorn.Server(config)

            def _shutdown() -> None:
                server.should_exit = True

            loop.add_signal_handler(signal.SIGINT, _shutdown)
            loop.add_signal_handler(signal.SIGTERM, _shutdown)

            runner.run(_run(server, app_state))

    logger.info("stopped.")


if __name__ == "__main__":
    main()
