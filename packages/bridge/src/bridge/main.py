import asyncio
import contextlib
import logging
import signal
import sys
from concurrent.futures import ThreadPoolExecutor
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
    loop = asyncio.get_running_loop()
    executor = ThreadPoolExecutor(max_workers=1)
    while True:
        line = await loop.run_in_executor(executor, sys.stdin.readline)
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


async def _run(server: uvicorn.Server) -> None:
    game_task = asyncio.create_task(game_to_client())
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

    logger.info("started.")
    with asyncio.Runner() as runner:
        loop = runner.get_loop()
        config = uvicorn.Config(app, host="127.0.0.1", port=8765, log_config=None)
        server = uvicorn.Server(config)

        async def _close_clients() -> None:
            for client in list(clients):
                with contextlib.suppress(Exception):
                    await client.close()

        def _shutdown() -> None:
            server.should_exit = True
            loop.create_task(_close_clients())

        loop.add_signal_handler(signal.SIGINT, _shutdown)
        loop.add_signal_handler(signal.SIGTERM, _shutdown)

        runner.run(_run(server))
    logger.info("stopped.")


if __name__ == "__main__":
    main()
