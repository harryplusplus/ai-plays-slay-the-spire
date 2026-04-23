import asyncio
import logging
import signal
import sys
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

clients: set[WebSocket] = set()


@app.websocket("/ws")
async def on_client(client: WebSocket) -> None:
    await client.accept()
    clients.add(client)
    await client_to_game(client)


async def client_to_game(client: WebSocket) -> None:
    try:
        async for text in client.iter_text():
            sys.stdout.write(text + "\n")
            sys.stdout.flush()
            logger.debug("received from client: %s", text)
    finally:
        clients.discard(client)


async def game_to_client() -> None:
    while True:
        line = await asyncio.to_thread(sys.stdin.readline)
        if not line:
            break
        text = line.rstrip("\n")
        if not text:
            continue
        for client in clients.copy():
            try:
                await client.send_text(text)
            except WebSocketDisconnect:
                clients.discard(client)
        logger.debug("sent to clients: %s", text)


async def _run() -> None:
    config = uvicorn.Config(app, host="127.0.0.1", port=8765, log_config=None)
    server = uvicorn.Server(config)

    game_task = asyncio.create_task(game_to_client())
    server_task = asyncio.create_task(server.serve())

    _done, _pending = await asyncio.wait(
        [game_task, server_task],
        return_when=asyncio.FIRST_COMPLETED,
    )
    server.should_exit = True
    await server_task
    game_task.cancel()
    await asyncio.gather(game_task, return_exceptions=True)


def main() -> None:
    handler = RotatingFileHandler(
        Path.home() / ".sts" / "logs" / "bridge.log",
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(
        _Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"),
    )

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)

    logger.info("bridge started.")
    loop = asyncio.new_event_loop()

    def _shutdown() -> None:
        for task in asyncio.all_tasks(loop):
            task.cancel()

    loop.add_signal_handler(signal.SIGINT, _shutdown)
    loop.add_signal_handler(signal.SIGTERM, _shutdown)

    try:
        loop.run_until_complete(_run())
    finally:
        loop.close()
    logger.info("bridge stopped.")


if __name__ == "__main__":
    main()
