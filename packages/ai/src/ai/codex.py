import logging
import subprocess

from core.paths import AGENT_DIR, OUTPUT_LAST_MESSAGE, OUTPUT_SCHEMA

logger = logging.getLogger(__name__)


def build_cmd(*, has_session: bool) -> list[str]:
    cmd = ["codex", "exec"]

    if has_session:
        cmd += [
            "resume",
            "--last",
        ]
    else:
        cmd += [
            "--color",
            "never",
            "--sandbox",
            "workspace-write",
            "--output-schema",
            str(OUTPUT_SCHEMA),
        ]

    cmd += [
        "--json",
        "--skip-git-repo-check",
        "--model",
        "gpt-5.4",
        "--output-last-message",
        str(OUTPUT_LAST_MESSAGE),
        "-",
    ]

    return cmd


def execute_codex(env: dict[str, str], prompt: str, *, has_session: bool) -> None:
    proc = subprocess.Popen(  # noqa: S603
        build_cmd(has_session=has_session),
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
            logger.debug("Received JSON from codex: %s", json_str)

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
