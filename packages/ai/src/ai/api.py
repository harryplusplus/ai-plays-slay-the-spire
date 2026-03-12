import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 60
BRIDGE_BASE_URL = "http://localhost:8000"


def health() -> None:
    requests.get(
        f"{BRIDGE_BASE_URL}/health",
        timeout=REQUEST_TIMEOUT,
    ).raise_for_status()


def execute(command: str) -> dict[str, Any]:
    response = requests.post(
        f"{BRIDGE_BASE_URL}/execute",
        json={"command": command},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()
