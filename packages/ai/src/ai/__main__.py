import asyncio
import copy
import json
import logging
import os
import shutil
from typing import Any

import websockets
from core.paths import (
    AUTH_JSON_FILE,
    CODEX_HOME_DIR,
    OUTPUT_SCHEMA_FILE,
)
from pydantic import BaseModel, ConfigDict
from websockets.asyncio.client import connect

from ai import log

logger = logging.getLogger(__name__)


BRIDGE_WS_URL = "ws://localhost:8000/ws"


class OutputSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command: str


def _prettify_json(json_obj: dict[str, Any]) -> str:
    return json.dumps(json_obj, indent=2)


def state_for_logging(state: dict[str, Any]) -> dict[str, Any]:
    filtered_state = copy.deepcopy(state)
    filtered_state.pop("game_state", None)
    return filtered_state


async def main() -> None:
    env = os.environ.copy()
    env["CODEX_HOME"] = str(CODEX_HOME_DIR)

    async for websocket in connect(BRIDGE_WS_URL):
        await websocket.send("state")
        try:
            async for data in websocket:
                message = data.decode() if isinstance(data, bytes) else data
                print(message)
            break
        except websockets.exceptions.ConnectionClosedError:
            continue


#     async with api.connect() as session:
#         state = await session.communicate("state")

#         while True:
#             resume = any(SESSIONS_DIR.rglob("*.jsonl"))
#             prompt = f"""Previous state:
# {_prettify_json(previous_state) if previous_state is not None else "N/A"}

# Command: {command if command is not None else "N/A"}

# State:
# {_prettify_json(state)}

# What is the next command to play in Slay the Spire?
# """

#             command = codex.execute(
#                 env,
#                 prompt,
#                 resume=resume,
#             )

#             previous_state = state
#             state = await session.communicate(command)

#             logger.info(
#                 "\nPrevious state:\n%s\nCommand: %s\nState:\n%s",
#                 _prettify_json(state_for_logging(previous_state)),
#                 command,
#                 _prettify_json(state_for_logging(state)),
#             )


if __name__ == "__main__":
    log.init()

    if not AUTH_JSON_FILE.exists():
        raise FileNotFoundError(
            f"Please login using `codex login` and ensure {AUTH_JSON_FILE} exists.",
        )

    CODEX_HOME_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(AUTH_JSON_FILE, CODEX_HOME_DIR)

    with OUTPUT_SCHEMA_FILE.open("w") as f:
        f.write(json.dumps(OutputSchema.model_json_schema(), indent=2))

    asyncio.run(main())
