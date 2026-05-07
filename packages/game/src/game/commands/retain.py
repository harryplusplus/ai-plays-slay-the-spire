import logging
from datetime import UTC, datetime
from typing import Any

from game.hindsight import BANK_ID, create_hindsight_client

logger = logging.getLogger(__name__)

RETAIN_CONTEXT = (
    "Slay the Spire gameplay: strategic decisions, build directions, "
    "enemy patterns, card synergies, combat lessons. "
    "Ignore raw state snapshots."
)


def retain(content: str, document_id: str | None = None) -> dict[str, Any]:
    """Store a memory in Hindsight. Returns the result dict."""
    client = create_hindsight_client()

    result = client.retain(
        bank_id=BANK_ID,
        content=content,
        context=RETAIN_CONTEXT,
        timestamp=datetime.now(UTC),
        document_id=document_id,
        update_mode="append" if document_id else None,
        retain_async=True,
    )

    output: dict[str, Any] = {
        "success": result.success,
        "items_count": result.items_count,
    }
    if result.operation_id:
        output["operation_id"] = result.operation_id

    extra: dict[str, Any] = {"event": "retain", "content": content}
    if result.operation_id:
        extra["op_id"] = result.operation_id
    logger.info("retain executed", extra=extra)

    return output
