import logging
import os
import shutil
import subprocess

from ai_plays_slay_the_spire.paths import AGENT_DIR, AUTH_JSON, CODEX_HOME

logger = logging.getLogger(__name__)


class CodexExecutor:
    def __init__(self) -> None:
        if not AUTH_JSON.exists():
            raise FileNotFoundError(AUTH_JSON)

        CODEX_HOME.mkdir(exist_ok=True, parents=True)
        shutil.copy2(AUTH_JSON, CODEX_HOME)

        AGENT_DIR.mkdir(exist_ok=True, parents=True)

        env = os.environ.copy()
        env["CODEX_HOME"] = str(CODEX_HOME)
        self._env = env
        self._cmd = [
            "codex",
            "exec",
            "resume",
            "--last",
            "--json",
            "--skip-git-repo-check",
            "--model",
            "gpt-5.4",
            "-",
        ]

    def exec(self, prompt: str) -> None:
        p = subprocess.Popen(
            self._cmd,
            cwd=AGENT_DIR,
            env=self._env,
            text=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )

        try:
            assert p.stdin
            p.stdin.write(prompt)
            p.stdin.close()

            assert p.stdout
            for line in p.stdout:
                line = line.rstrip()
                logger.debug(line)

            rc = p.wait()
            if rc != 0:
                logger.error(f"Failed to exec codex with exit code: {rc}")
        except Exception as e:
            logger.error(f"Failed to exec codex with error: {e}")
            raise
        finally:
            if p.stdin and not p.stdin.closed:
                p.stdin.close()
            if p.stdout and not p.stdout.closed:
                p.stdout.close()
            if p.poll() is None:
                p.kill()
                p.wait()
