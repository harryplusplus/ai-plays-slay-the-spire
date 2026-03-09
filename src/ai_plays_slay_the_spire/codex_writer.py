import json
from typing import IO

from ai_plays_slay_the_spire.codex_common import CodexRequestId


class CodexWriter:
    def __init__(self, io: IO[str]) -> None:
        self._io = io
        self._req_id = CodexRequestId()

    def close(self) -> None:
        self._io.close()

    def _write(self, data: dict) -> None:
        self._io.write(f"{json.dumps(data)}\n")
        self._io.flush()

    def initialize(self) -> int:
        req_id = self._req_id.next()
        self._write(
            {
                "method": "initialize",
                "id": req_id,
                "params": {
                    "clientInfo": {
                        "name": "ai_plays_slay_the_spire",
                        "version": "0.0.0",
                    }
                },
            }
        )

        return req_id

    def initialized(self) -> None:
        self._write({"method": "initialized", "params": {}})

    def thread_start(self) -> None:
        req_id = self._req_id.next()
        self._write(
            {
                "method": "thread/start",
                "id": req_id,
                "params": {
                    "model": "gpt-5.4",
                    "cwd": "/Users/me/project",
                    "approvalPolicy": "never",
                    "sandbox": "workspaceWrite",
                    "personality": "friendly",
                    "serviceName": "my_app_server_client",
                },
            }
        )
