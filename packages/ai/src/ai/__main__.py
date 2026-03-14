import copy
import json
import logging
import os
import shutil
import time
from typing import Any

from core.paths import (
    AUTH_JSON,
    CODEX_HOME,
    OUTPUT_SCHEMA,
    SESSIONS_DIR,
)
from pydantic import BaseModel, ConfigDict

from ai import api, codex, log

logger = logging.getLogger(__name__)


DELAY = 0


class OutputSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command: str


def _prettify_json(json_obj: dict[str, Any]) -> str:
    return json.dumps(json_obj, indent=2)


def state_for_logging(state: dict[str, Any]) -> dict[str, Any]:
    filtered_state = copy.deepcopy(state)
    filtered_state.pop("game_state", None)

    # game_state = filtered_state.get("game_state")

    # if isinstance(game_state, dict):
    #     gs = cast("dict[str, Any]", game_state)
    #     gs.pop("map", None)
    #     gs.pop("deck", None)
    #     gs.pop("relics", None)
    #     gs.pop("potions", None)
    #     gs.pop("combat_state", None)

    return filtered_state


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

    env = os.environ.copy()
    env["CODEX_HOME"] = str(CODEX_HOME)

    api.health()

    previous_state: dict[str, Any] | None = None
    command: str | None = None
    state = api.communicate("state")

    while True:
        resume = any(SESSIONS_DIR.rglob("*.jsonl"))
        prompt = f"""Previous state:
{_prettify_json(previous_state) if previous_state is not None else "N/A"}

Command: {command if command is not None else "N/A"}

State:
{_prettify_json(state)}

What is the next command to play in Slay the Spire?
"""

        command = codex.execute(
            env,
            prompt,
            resume=resume,
        )

        previous_state = state
        state = api.communicate(command)

        logger.info(
            "\nPrevious state:\n%s\nCommand: %s\nState:\n%s",
            _prettify_json(state_for_logging(previous_state)),
            command,
            _prettify_json(state_for_logging(state)),
        )

        time.sleep(DELAY)


if __name__ == "__main__":
    main()
