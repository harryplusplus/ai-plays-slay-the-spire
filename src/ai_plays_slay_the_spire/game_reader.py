import sys

from ai_plays_slay_the_spire.message_reader import Kind, MessageQueue, MessageReader


class GameReader:
    def __init__(self, q: MessageQueue) -> None:
        self._r = MessageReader("game_reader", Kind.GAME, sys.stdin, q)

    def wait(self) -> None:
        self._r.wait()
