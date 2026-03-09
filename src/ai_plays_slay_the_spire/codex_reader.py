from typing import IO

from ai_plays_slay_the_spire.message_reader import Kind, MessageQueue, MessageReader


class CodexReader:
    def __init__(self, io: IO[str], q: MessageQueue) -> None:
        self._r = MessageReader("codex_reader", Kind.CODEX, io, q)

    def wait(self) -> None:
        self._r.wait()
