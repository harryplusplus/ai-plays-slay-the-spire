import logging
import queue
import sys
from threading import Thread

MessageQueue = queue.Queue[str | None]


def _message_reader_main(q: MessageQueue) -> None:
    logger = logging.getLogger(f"{__name__}.message_reader")
    logger.info("Thread started.")

    for line in sys.stdin:
        msg = line.rstrip()
        logger.debug(msg)
        q.put(msg)

    q.put(None)
    logger.info("Thread exited.")


class MessageReader:
    def __init__(self, q: MessageQueue) -> None:
        self._t = Thread(
            target=_message_reader_main, args=(q,), name="game_message_reader"
        )
        self._t.start()

    def wait(self) -> None:
        self._t.join()


class MessageWriter:
    def _write(self, msg: str) -> None:
        print(msg, flush=True)

    def ready(self) -> None:
        self._write("ready")
