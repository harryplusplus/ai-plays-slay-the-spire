import logging
import subprocess

from core.paths import AGENT_DIR, OUTPUT_LAST_MESSAGE, OUTPUT_SCHEMA
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)


class OutputSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command: str


def execute_codex(env: dict[str, str], prompt: str) -> None:
    proc = subprocess.Popen(  # noqa: S603
        [  # noqa: S607
            "codex",
            "exec",
            # "resume",
            # "--last",
            "--json",
            "--skip-git-repo-check",
            "--model",
            "gpt-5.4",
            "--color",
            "never",
            "--output-schema",
            str(OUTPUT_SCHEMA),
            "--output-last-message",
            str(OUTPUT_LAST_MESSAGE),
            "-",
        ],
        cwd=AGENT_DIR,
        env=env,
        text=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )

    try:
        if proc.stdin is None:
            raise RuntimeError("Failed to open stdin for codex process.")

        proc.stdin.write(prompt)
        proc.stdin.close()

        if proc.stdout is None:
            raise RuntimeError("Failed to open stdout for codex process.")

        for line in proc.stdout:
            json_str = line.rstrip()
            logger.info(json_str)

        rc = proc.wait()
        if rc != 0:
            logger.error("Failed to run codex process.", extra={"returncode": rc})

    finally:
        if proc.stdin and not proc.stdin.closed:
            proc.stdin.close()
        if proc.stdout and not proc.stdout.closed:
            proc.stdout.close()
        if proc.poll() is None:
            proc.kill()
            proc.wait()
