import asyncio
import logging
import signal
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import override

import uvicorn
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


def init_db() -> sqlite3.Connection:
    return sqlite3.connect(_DB_PATH)


def next_command_id(db: sqlite3.Connection) -> int:
    row = db.execute(_SQL_NEXT).fetchone()
    db.commit()
    return row[0]


app = FastAPI()


@dataclass(slots=True, kw_only=True)
class AppState:
    db: sqlite3.Connection


async def _run(server: uvicorn.Server, db: sqlite3.Connection) -> None:  # noqa: ARG001
    await server.serve()


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
    with closing(init_db()) as db:
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

            runner.run(_run(server, db))

    logger.info("stopped.")


if __name__ == "__main__":
    main()
