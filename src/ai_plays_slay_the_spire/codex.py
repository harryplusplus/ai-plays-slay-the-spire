import json
import os
import queue
import subprocess

from ai_plays_slay_the_spire import message_reader_thread
from ai_plays_slay_the_spire.message_reader_thread import Kind, Message
from ai_plays_slay_the_spire.paths import AGENT_DIR, CODEX_HOME


class Codex:
    def __init__(self, msg_q: queue.Queue[Message]) -> None:
        env = os.environ.copy()
        env["CODEX_HOME"] = str(CODEX_HOME)

        AGENT_DIR.mkdir(exist_ok=True, parents=True)

        self._proc = subprocess.Popen(
            ["codex", "app-server"],
            cwd=AGENT_DIR,
            env=env,
            text=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )

        p = self._proc
        assert p.stdin is not None
        assert p.stdout is not None

        self._writer = p.stdin
        self._reader = message_reader_thread.start(
            "codex_message_reader", Kind.CODEX, p.stdout, msg_q
        )

    def close(self) -> None:
        self._writer.close()

        p = self._proc
        p.terminate()

        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()

        self._reader.join()

    def _send(self, msg: dict) -> None:
        self._writer.write(json.dumps(msg) + "\n")
        self._writer.flush()

    def send_initialize(self, msg_id: int) -> None:
        self._send(
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

    def send_initialized(self) -> None:
        self._send({"method": "initialized", "params": {}})
