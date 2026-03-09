import logging
import queue
import sys
from collections import deque
from typing import Self

from pydantic import BaseModel, ValidationError, model_validator

from ai_plays_slay_the_spire import log, message_reader_thread
from ai_plays_slay_the_spire.codex import Codex
from ai_plays_slay_the_spire.message_reader_thread import Kind, Message
from ai_plays_slay_the_spire.paths import PROJECT_FILE

logger = logging.getLogger("app")


def check_project_dir() -> None:
    if not PROJECT_FILE.exists():
        raise RuntimeError("Not in project directory")


def send_game_message(msg: str) -> None:
    print(msg, flush=True)


class CodexRequestId:
    def __init__(self) -> None:
        self._id = 0

    def next(self) -> int:
        id = self._id
        self._id += 1
        return id


class CodexError(BaseModel):
    code: int
    message: str


class CodexResponse(BaseModel):
    id: int
    error: CodexError | None = None
    result: dict | None = None

    @model_validator(mode="after")
    def check_result_or_error(self) -> Self:
        if (self.result is not None and self.error is not None) or (
            self.result is None and self.error is None
        ):
            raise ValueError("Exactly one of result or error must be provided")
        return self

    def is_result(self) -> bool:
        return self.result is not None


def main() -> None:
    check_project_dir()
    log.init()

    logger.info("started.")
    send_game_message("ready")

    msg_q = queue.Queue[Message]()
    game_msg_reader = message_reader_thread.start(
        "game_message_reader", Kind.GAME, sys.stdin, msg_q
    )

    pending_game_msgs = deque[str]()
    initialized = False
    req_id = CodexRequestId()
    initialize_req_id = req_id.next()

    codex = Codex(msg_q)
    codex.send_initialize(initialize_req_id)

    while True:
        msg = msg_q.get()
        if msg.kind == Kind.GAME:
            if msg.data is None:
                # NOTE: game exited.
                break

            if not initialized:
                pending_game_msgs.append(msg.data)
                continue

            # TODO: handle game messages

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

                codex.send_initialized()

                # TODO: handle pending game messages
                initialized = True

    codex.close()
    game_msg_reader.join()
    logger.info("exited.")


if __name__ == "__main__":
    main()
