import asyncio
import json
import logging
import signal
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, override

import uvicorn
import websockets
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

DB_PATH = Path.home() / ".sts" / "proxy.db"

SQL_INIT = """
CREATE TABLE IF NOT EXISTS command_id_counter (
    command_id INTEGER NOT NULL DEFAULT 0
)
"""
COMMAND_TIMEOUT = 30.0


SQL_ENSURE_ROW = "INSERT OR IGNORE INTO command_id_counter (rowid) VALUES (1)"
SQL_NEXT = (
    "UPDATE command_id_counter "
    "SET command_id = command_id + 1 "
    "RETURNING command_id"
)


def next_command_id(db: sqlite3.Connection) -> int:
    db.execute(SQL_ENSURE_ROW)
    row = db.execute(SQL_NEXT).fetchone()
    db.commit()
    return row[0]


app = FastAPI()


@dataclass(slots=True, kw_only=True)
class AppState:
    db: sqlite3.Connection
    pending: dict[int, asyncio.Future[dict[str, Any]]] = field(
        default_factory=dict[int, asyncio.Future[dict[str, Any]]],
    )
    ws: websockets.ClientConnection | None = None


@app.post("/command")
async def command(request: Request) -> JSONResponse:
    app_state: AppState = request.app.state.app_state
    body = (await request.body()).decode()

    cmd_id = next_command_id(app_state.db)
    loop = asyncio.get_running_loop()
    future: asyncio.Future[dict[str, Any]] = loop.create_future()
    app_state.pending[cmd_id] = future

    try:
        if app_state.ws is None:
            return JSONResponse({"error": "bridge not connected"}, status_code=503)
        await app_state.ws.send(f"--command-id={cmd_id} {body}")
        try:
            result = await asyncio.wait_for(future, timeout=COMMAND_TIMEOUT)
        except TimeoutError:
            return JSONResponse(
                {"error": "command timed out", "command_id": cmd_id},
                status_code=504,
            )
    finally:
        app_state.pending.pop(cmd_id, None)

    return JSONResponse(result)


async def ws_loop(ws: websockets.ClientConnection, app_state: AppState) -> None:
    async for message in ws:
        logger.debug("received from bridge: %s", message)
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            logger.warning("invalid json from bridge: %s", message)
            continue
        cmd_id = data.get("command_id")
        if cmd_id is not None and cmd_id in app_state.pending:
            app_state.pending[cmd_id].set_result(data)


async def run(server: uvicorn.Server, app_state: AppState) -> None:
    server_task = asyncio.create_task(server.serve())

    async for ws in websockets.connect("ws://127.0.0.1:8765/ws"):
        logger.info("connected to bridge.")
        app_state.ws = ws
        ws_task = asyncio.create_task(ws_loop(ws, app_state))

        done, _ = await asyncio.wait(
            [ws_task, server_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        if server_task in done:
            ws_task.cancel()
            await asyncio.gather(ws_task, return_exceptions=True)
            await ws.close()
            app_state.ws = None
            return

        app_state.ws = None
        logger.info("disconnected from bridge, reconnecting...")


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
    with closing(sqlite3.connect(DB_PATH)) as db:
        with db:
            db.execute(SQL_INIT)

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

            runner.run(run(server, app_state))

    logger.info("stopped.")


if __name__ == "__main__":
    main()
