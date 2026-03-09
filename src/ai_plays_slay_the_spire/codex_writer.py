import json
from typing import IO


class CodexWriter:
    def __init__(self, io: IO[str]) -> None:
        self._io = io

    def close(self) -> None:
        self._io.close()

    def _write(self, data: dict) -> None:
        self._io.write(f"{json.dumps(data)}\n")
        self._io.flush()

    def initialize(self, msg_id: int) -> None:
        self._write(
            {
                "method": "initialize",
                "id": msg_id,
                "params": {
                    "clientInfo": {
                        "name": "ai_plays_slay_the_spire",
                        "version": "0.0.0",
                    }
                },
            }
        )

    def initialized(self) -> None:
        self._write({"method": "initialized", "params": {}})
