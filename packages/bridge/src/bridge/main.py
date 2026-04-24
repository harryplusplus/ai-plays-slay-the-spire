import asyncio
import contextlib
import logging
import signal
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import override

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect


class _Formatter(logging.Formatter):
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


logger = logging.getLogger(__name__)

app = FastAPI()


@dataclass(slots=True, kw_only=True)
class AppState:
    clients: set[WebSocket] = field(default_factory=set[WebSocket])
    shutting_down: bool = False


@app.websocket("/ws")
async def on_client(client: WebSocket) -> None:
    app: FastAPI = client.app
    app_state: AppState = app.state.app_state
    if app_state.shutting_down:
        await client.close()
        return

    await client.accept()
    app_state.clients.add(client)
    await client_to_game(client, app_state)


async def client_to_game(client: WebSocket, app_state: AppState) -> None:
    try:
        async for text in client.iter_text():
            sys.stdout.write(text + "\n")
            sys.stdout.flush()
            logger.info("received from client: %s", text)
    finally:
        app_state.clients.discard(client)


async def game_to_client(app_state: AppState) -> None:
    loop = asyncio.get_running_loop()
    executor = ThreadPoolExecutor(max_workers=1)
    while True:
        line = await loop.run_in_executor(executor, sys.stdin.readline)
        if not line:
            break
        text = line.rstrip("\n")
        if not text:
            continue
        for client in app_state.clients.copy():
            try:
                await client.send_text(text)
            except WebSocketDisconnect:
                app_state.clients.discard(client)
        logger.info("sent to clients: %s", text)


async def run(server: uvicorn.Server, app_state: AppState) -> None:
    game_task = asyncio.create_task(game_to_client(app_state))
    server_task = asyncio.create_task(server.serve())

    sys.stdout.write("ready\n")
    sys.stdout.flush()

    done, _ = await asyncio.wait(
        [game_task, server_task],
        return_when=asyncio.FIRST_COMPLETED,
    )

    if server_task not in done:
        server.should_exit = True
        await server_task

    game_task.cancel()
    await asyncio.gather(game_task, return_exceptions=True)


def main() -> None:
    handler = RotatingFileHandler(
        Path.home() / ".sts" / "logs" / "bridge.log",
        maxBytes=10_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(
        _Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"),
    )

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)

    logger.info("started.")
    app_state = AppState()
    app.state.app_state = app_state

    with asyncio.Runner() as runner:
        loop = runner.get_loop()
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=8765,
            log_config=None,
            timeout_graceful_shutdown=0,
        )
        server = uvicorn.Server(config)

        async def _shutdown_async() -> None:
            to_close = app_state.clients.copy()
            app_state.clients.clear()
            for client in to_close:
                with contextlib.suppress(Exception):
                    await client.close()
            server.should_exit = True

        def _shutdown() -> None:
            app_state.shutting_down = True
            loop.create_task(_shutdown_async())

        loop.add_signal_handler(signal.SIGINT, _shutdown)
        loop.add_signal_handler(signal.SIGTERM, _shutdown)

        runner.run(run(server, app_state))
    logger.info("stopped.")


if __name__ == "__main__":
    main()
