import logging
import os
import subprocess

from ai_plays_slay_the_spire.codex_reader import CodexReader
from ai_plays_slay_the_spire.codex_writer import CodexWriter
from ai_plays_slay_the_spire.message_reader import MessageQueue
from ai_plays_slay_the_spire.paths import AGENT_DIR, CODEX_HOME

logger = logging.getLogger("codex_process")


class CodexProcess:
    def __init__(self) -> None:
        env = os.environ.copy()
        env["CODEX_HOME"] = str(CODEX_HOME)

        AGENT_DIR.mkdir(exist_ok=True, parents=True)

        self._p = subprocess.Popen(
            ["codex", "app-server"],
            cwd=AGENT_DIR,
            env=env,
            text=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )

        logger.info("started.")

    def close(self) -> None:
        self._p.terminate()
        try:
            self._p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._p.kill()
            self._p.wait()

        logger.info("exited.")

    def create_writer(self) -> CodexWriter:
        assert self._p.stdin
        return CodexWriter(self._p.stdin)

    def create_reader(self, msg_q: MessageQueue) -> CodexReader:
        assert self._p.stdout
        return CodexReader(self._p.stdout, msg_q)
