import json
import logging
import os
import shutil

import requests
from core.paths import AUTH_JSON, CODEX_HOME, OUTPUT_LAST_MESSAGE, OUTPUT_SCHEMA

from ai import log
from ai.codex import OutputSchema, execute_codex

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 60
BRIDGE_BASE_URL = "http://localhost:8000"


def main() -> None:
    log.init()

    if not AUTH_JSON.exists():
        raise FileNotFoundError(
            f"Please login using `codex login` and ensure {AUTH_JSON} exists.",
        )

    CODEX_HOME.mkdir(parents=True, exist_ok=True)
    shutil.copy2(AUTH_JSON, CODEX_HOME)

    with OUTPUT_SCHEMA.open("w") as f:
        f.write(json.dumps(OutputSchema.model_json_schema(), indent=2))

    requests.get(
        f"{BRIDGE_BASE_URL}/health",
        timeout=REQUEST_TIMEOUT,
    ).raise_for_status()

    env = os.environ.copy()
    env["CODEX_HOME"] = str(CODEX_HOME)
    execute_codex(env, "What is the next command to play in Slay the Spire?")

    with OUTPUT_LAST_MESSAGE.open() as f:
        command = f.read()

    response = requests.post(
        f"{BRIDGE_BASE_URL}/execute",
        json={"command": command},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()


if __name__ == "__main__":
    main()
