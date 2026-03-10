import logging
import sys

from ai_plays_slay_the_spire import log
from ai_plays_slay_the_spire.codex_executor import CodexExecutor
from ai_plays_slay_the_spire.game_message_reader import GameMessageReader, MessageQueue
from ai_plays_slay_the_spire.game_message_writer import GameMessageWriter

logger = logging.getLogger(__name__)


def run() -> None:
    print("Press Ctrl+D to exit.", file=sys.stderr, flush=True)

    log.init()
    logger.info("started.")

    game_msg_w = GameMessageWriter()
    game_msg_w.ready()
    game_msg_q = MessageQueue()
    game_msg_r = GameMessageReader(game_msg_q)
    codex_e = CodexExecutor()

    while True:
        game_msg = game_msg_q.get()
        if game_msg is None:
            break

    game_msg_r.wait()
    logger.info("exited.")
