import logging

from ai_plays_slay_the_spire import codex, game, log

logger = logging.getLogger(__name__)


def run() -> None:
    log.init()
    logger.info("App started.")
    logger.info("Press Ctrl+D to exit.")

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
    logger.info("App exited.")
