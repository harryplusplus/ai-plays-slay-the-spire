# pyright: reportUnknownVariableType=none, reportUnknownArgumentType=none, reportUnknownMemberType=none, reportMissingTypeArgument=none
"""Migrate high-quality memories from sts to sts-v2 bank."""

import logging
import sys
from datetime import UTC, datetime
from typing import Any

from hindsight_client import Hindsight

logger = logging.getLogger(__name__)

SOURCE_BANK = "sts"
TARGET_BANK = "sts-v2"
CUTOFF_DATE = datetime(2026, 4, 24, 9, 0, 0, tzinfo=UTC)
MIGRATE_TYPES = {"experience", "observation"}
MAX_MIGRATE = 500
RETAIN_CONTEXT = (
    "Slay the Spire gameplay: strategic decisions, build directions, "
    "enemy patterns, card synergies, combat lessons. "
    "Ignore raw state snapshots."
)


def _fetch_all_memories(client: Hindsight) -> list[dict[str, Any]]:
    all_memories: list[dict] = []
    offset = 0
    limit = 100
    while True:
        page = client.list_memories(bank_id=SOURCE_BANK, limit=limit, offset=offset)
        items = page.items if hasattr(page, "items") else []
        if not items:
            break
        all_memories.extend(items)
        offset += len(items)
        if len(all_memories) >= MAX_MIGRATE * 2:
            logger.warning("Reached safety limit, stopping fetch")
            break
    return all_memories


def _parse_date(raw: str | datetime | None) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    return datetime.fromisoformat(raw)


def _filter_memories(memories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    filtered: list[dict] = []
    for mem in memories:
        mem_date = _parse_date(mem.get("date") or mem.get("mentioned_at"))
        if mem_date is None or mem_date < CUTOFF_DATE:
            continue
        fact_type = mem.get("fact_type") or mem.get("type")
        if fact_type not in MIGRATE_TYPES:
            continue
        text = mem.get("text", "")
        if text:
            filtered.append({"text": text, "date": mem_date, "type": fact_type})
    return filtered


def _migrate_batch(client: Hindsight, items: list[dict[str, Any]]) -> tuple[int, int]:
    migrated = 0
    skipped = 0
    for item in items:
        try:
            client.retain(
                bank_id=TARGET_BANK,
                content=item["text"],
                timestamp=item["date"],
                context=RETAIN_CONTEXT,
            )
            migrated += 1
            if migrated % 10 == 0:
                logger.info("  ... migrated %d/%d", migrated, len(items))
        except Exception:
            logger.exception("Failed to migrate: %s", item["text"][:60])
            skipped += 1
    return migrated, skipped


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    client = Hindsight(base_url="http://localhost:8888")

    logger.info("=== Migration: %s -> %s ===", SOURCE_BANK, TARGET_BANK)
    logger.info("Cutoff: %s", CUTOFF_DATE.isoformat())

    all_memories = _fetch_all_memories(client)
    logger.info("Total memories fetched: %d", len(all_memories))

    to_migrate = _filter_memories(all_memories)
    logger.info("Memories matching criteria: %d", len(to_migrate))

    if not to_migrate:
        logger.info("Nothing to migrate.")
        return 0

    to_migrate.sort(key=lambda x: x["date"])
    migrated, skipped = _migrate_batch(client, to_migrate[:MAX_MIGRATE])

    logger.info("=== Migration complete ===")
    logger.info("Migrated: %d, Skipped: %d", migrated, skipped)
    return 0


if __name__ == "__main__":
    sys.exit(main())
