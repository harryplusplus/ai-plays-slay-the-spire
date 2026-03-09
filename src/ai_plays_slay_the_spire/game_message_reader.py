import logging
import queue
import sys
from threading import Thread

logger = logging.getLogger(__name__)

MessageQueue = queue.Queue[str | None]


def _main(q: MessageQueue) -> None:
    logger.info("started.")

    for line in sys.stdin:
        msg = line.rstrip()
        logger.debug(msg)
        q.put(msg)

    q.put(None)
    logger.info("exited.")


class GameMessageReader:
    def __init__(self, q: MessageQueue) -> None:
        self._t = Thread(target=_main, args=(q,), name="game_message_reader")
        self._t.start()

    def wait(self) -> None:
        self._t.join()
