import json
import logging
import os
import shutil

from core.paths import (
    AUTH_JSON,
    CODEX_HOME,
    OUTPUT_SCHEMA,
    SESSIONS_DIR,
)
from pydantic import BaseModel, ConfigDict

from ai import api, codex, log

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

    env = os.environ.copy()
    env["CODEX_HOME"] = str(CODEX_HOME)

    api.health()
    message = api.execute("state")

    while True:
        resume = any(SESSIONS_DIR.rglob("*.jsonl"))
        prompt = f"""The current game state is:
```
{message}
```

What is the next command to play in Slay the Spire?
"""

        command = codex.execute(
            env,
            prompt,
            resume=resume,
        )
        message = api.execute(command)


if __name__ == "__main__":
    main()
