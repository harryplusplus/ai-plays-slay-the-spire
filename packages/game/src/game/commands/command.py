import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

PROXY_URL = "http://127.0.0.1:8766/command"
TIMEOUT = 30.0


def _check_start_class(command: str) -> None:
    """Raise RuntimeError if command is a non-DEFECT START."""
    parts = command.strip().split()
    if len(parts) >= 2 and parts[0].upper() == "START" and parts[1].upper() != "DEFECT":  # noqa: PLR2004
        logger.warning(
            "blocked non-DEFECT start",
            extra={"event": "start_blocked", "attempted_class": parts[1].upper()},
        )
        msg = f"Only DEFECT class is allowed. Got: {parts[1].upper()}"
        raise RuntimeError(msg)


def command(command: str) -> dict[str, Any]:
    """Send a raw command to the game. Returns the response dict."""
    _check_start_class(command)
    logger.info("command executed", extra={"event": "command", "cmd": command})
    return (
        httpx.post(PROXY_URL, content=command, timeout=TIMEOUT)
        .raise_for_status()
        .json()
    )
