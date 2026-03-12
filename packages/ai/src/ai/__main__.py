import json
import logging
import os
import shutil

import requests
from core.paths import (
    AUTH_JSON,
    CODEX_HOME,
    OUTPUT_LAST_MESSAGE,
    OUTPUT_SCHEMA,
    SESSIONS_DIR,
)
from pydantic import BaseModel, ConfigDict

from ai import log
from ai.codex import execute_codex

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 60
BRIDGE_BASE_URL = "http://localhost:8000"


class OutputSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command: str


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

    command = "state"
    response = requests.post(
        f"{BRIDGE_BASE_URL}/execute",
        json={"command": command},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    histories = [{"command": command, "response": response.text}]

    while True:
        has_session = any(SESSIONS_DIR.rglob("*.jsonl"))
        prompt = ""
        if histories:
            prompt = (
                "Here is the history of commands and responses:\n\n"
                + "\n".join(
                    f"command: {history['command']}\nresponse: {history['response']}"
                    for history in histories
                )
                + "\n\n"
            )

        prompt += "What is the next command to play in Slay the Spire?"
        logger.info("Sending prompt to Codex. Prompt:\n%s", prompt)

        execute_codex(
            env,
            prompt,
            has_session=has_session,
        )

        with OUTPUT_LAST_MESSAGE.open() as f:
            command = f.read()

        response = requests.post(
            f"{BRIDGE_BASE_URL}/execute",
            json={"command": command},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        histories.append({"command": command, "response": response.text})


if __name__ == "__main__":
    main()
