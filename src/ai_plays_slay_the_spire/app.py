import logging

from ai_plays_slay_the_spire import log
from ai_plays_slay_the_spire.codex_executor import CodexExecutor
from ai_plays_slay_the_spire.game_message_reader import GameMessageReader, MessageQueue
from ai_plays_slay_the_spire.game_message_writer import GameMessageWriter

logger = logging.getLogger(__name__)


class App:
    def __init__(self) -> None:
        log.init()
        self._game_msg_w = GameMessageWriter()
        self._game_msg_w.ready()
        self._game_msg_q = MessageQueue()
        self._game_msg_r = GameMessageReader(self._game_msg_q)
        self._codex_e = CodexExecutor()
        logger.info("initialized.")

    def run(self) -> None:
        while True:
            game_msg = self._game_msg_q.get()
            if game_msg is None:
                break

        self._game_msg_r.wait()
        logger.info("exited.")
