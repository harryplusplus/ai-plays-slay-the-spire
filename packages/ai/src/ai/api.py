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


def communicate(command: str) -> dict[str, Any]:
    response = requests.post(
        f"{BRIDGE_BASE_URL}/communicate",
        data=command,
        headers={"Content-Type": "text/plain"},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()
