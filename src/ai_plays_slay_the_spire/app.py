import logging
import sys

from ai_plays_slay_the_spire import codex, game, log

_logger = logging.getLogger(__name__)


def run() -> None:
    print("Press Ctrl+D to exit.", file=sys.stderr, flush=True)

    log.init()
    _logger.info("started.")

    game_msg_w = game.MessageWriter()
    game_msg_w.ready()
    game_msg_q = game.MessageQueue()
    game_msg_r = game.MessageReader(game_msg_q)
    codex_e = codex.Executor()

    while True:
        game_msg = game_msg_q.get()
        if game_msg is None:
            break

    game_msg_r.wait()
    _logger.info("exited.")
