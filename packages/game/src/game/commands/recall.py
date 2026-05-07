import logging
from datetime import UTC, datetime
from typing import Any

from game.hindsight import BANK_ID, create_hindsight_client

logger = logging.getLogger(__name__)


def recall(query: str) -> dict[str, Any]:
    """Recall memories from Hindsight. Returns the response dict."""
    logger.info("recall executed", extra={"event": "recall", "query": query})
    client = create_hindsight_client()
    response = client.recall(
        bank_id=BANK_ID,
        query=query,
        types=["world", "experience", "observation"],
        max_tokens=2048,
        query_timestamp=datetime.now(UTC).isoformat(),
    )

    results = response.results
    logger.info(
        "recall result",
        extra={
            "event": "recall_result",
            "result_count": len(results),
            "types": list({r.type for r in results if r.type}),
            "results": [
                {
                    "id": r.id,
                    "type": r.type,
                    "text": r.text[:200],
                    "occurred": r.occurred_start,
                }
                for r in results
            ],
        },
    )

    return response.to_dict()
