import asyncio
import concurrent.futures
import logging
import sys
import threading
from typing import TextIO

from bridge.connection import ConnectionManager

logger = logging.getLogger(__name__)


class Receiver:
    def __init__(self, in_: TextIO | None = None) -> None:
        self._in: TextIO = in_ if in_ is not None else sys.stdin

    def receive(self) -> str:
        line = self._in.readline()
        if line == "":
            raise EOFError("message.Receiver reached EOF.")
        return line.rstrip()


class ThreadedReceiver:
    def __init__(
        self,
        connection: ConnectionManager,
        receiver: Receiver | None = None,
    ) -> None:
        self._connection = connection
        self._receiver = receiver if receiver is not None else Receiver()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        loop = asyncio.get_running_loop()
        self._thread = threading.Thread(
            target=self._run,
            args=(loop,),
            daemon=True,
        )
        self._thread.start()

    def _run(self, loop: asyncio.AbstractEventLoop) -> None:
        while True:
            try:
                message = self._receiver.receive()
            except EOFError:
                logger.info(
                    "Stopping ThreadedReceiver loop due to EOFError.",
                )
                break

            future = asyncio.run_coroutine_threadsafe(
                self._connection.send(message),
                loop,
            )
            future.add_done_callback(self._on_future_done)

    def _on_future_done(self, future: concurrent.futures.Future[None]) -> None:
        try:
            future.result()
        except Exception:
            logger.exception("Error sending message to connection.")
