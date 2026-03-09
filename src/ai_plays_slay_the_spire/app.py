import logging
from collections import deque

from pydantic import ValidationError

from ai_plays_slay_the_spire import log
from ai_plays_slay_the_spire.codex_common import CodexResponse
from ai_plays_slay_the_spire.codex_process import CodexProcess
from ai_plays_slay_the_spire.game_reader import GameReader
from ai_plays_slay_the_spire.game_writer import GameWriter
from ai_plays_slay_the_spire.message_reader import Kind, MessageQueue
from ai_plays_slay_the_spire.paths import PROJECT_FILE

logger = logging.getLogger("app")


def _check_project_dir() -> None:
    if not PROJECT_FILE.exists():
        raise RuntimeError("Not in project directory")


class App:
    def __init__(self) -> None:
        _check_project_dir()
        log.init()
        logger.info("starting...")

        self._msg_q = MessageQueue()

        self._game_w = GameWriter()
        self._game_w.ready()
        self._game_r = GameReader(self._msg_q)

        self._codex_p = CodexProcess()
        self._codex_w = self._codex_p.create_writer()
        self._codex_r = self._codex_p.create_reader(self._msg_q)

    def run(self) -> None:
        pending_game_msgs = deque[str]()
        initialized = False
        initialize_req_id = self._codex_w.initialize()

        while True:
            msg = self._msg_q.get()
            if msg.kind == Kind.GAME:
                if msg.data is None:
                    # NOTE: game exited.
                    break

                if not initialized:
                    pending_game_msgs.append(msg.data)
                    continue

                self._on_game_message(msg.data)

            else:
                assert msg.kind == Kind.CODEX
                if msg.data is None:
                    logger.error("Closed codex stdout.")
                    break

                try:
                    resp = CodexResponse.model_validate_json(msg.data)
                except ValidationError as e:
                    logger.error(f"Failed to parse codex response: {e}")
                    continue

                if resp.id == initialize_req_id:
                    if not resp.is_result():
                        logger.error("Failed to initialize codex.")
                        break

                    self._codex_w.initialized()

                    # TODO: handle pending game messages.
                    initialized = True

        self._codex_w.close()
        self._codex_p.close()
        self._codex_r.wait()
        self._game_r.wait()
        logger.info("exited.")

    def _on_game_message(self, msg: str) -> None:
        pass
