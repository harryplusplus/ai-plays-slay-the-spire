import json
import logging
from datetime import UTC, datetime
from typing import Any

import httpx
import typer
from game.log import init_logger
from hindsight_client import Hindsight

logger = logging.getLogger(__name__)


BANK_ID = "sts-v2"
RETAIN_CONTEXT = (
    "Slay the Spire gameplay: strategic decisions, build directions, "
    "enemy patterns, card synergies, combat lessons. "
    "Ignore raw state snapshots."
)
PROXY_URL = "http://127.0.0.1:8766/command"
TIMEOUT = 30.0
HINDSIGHT_URL = "http://localhost:8888"


app = typer.Typer(no_args_is_help=True, add_completion=False)


def send_command(cmd: str) -> dict[str, Any]:
    response = httpx.post(PROXY_URL, content=cmd, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def extract_game_state_field(data: dict[str, Any], key: str) -> Any:  # noqa: ANN401
    game_state = data.get("game_state", {})
    return game_state.get(key)


def _check_start_class(cmd: str) -> bool:
    """Block START commands for classes other than DEFECT. Returns True if blocked."""
    parts = cmd.strip().split()
    if len(parts) >= 2 and parts[0].upper() == "START" and parts[1].upper() != "DEFECT":  # noqa: PLR2004
        error = {
            "error": f"Only DEFECT class is allowed. Got: {parts[1].upper()}",
            "valid_classes": ["DEFECT"],
        }
        typer.echo(json.dumps(error, indent=2))
        logger.warning(
            "blocked non-DEFECT start",
            extra={"event": "start_blocked", "attempted_class": parts[1].upper()},
        )
        return True
    return False


@app.command()
def command(cmd: str) -> None:
    """Send a raw command to the game."""
    if _check_start_class(cmd):
        return
    logger.info("command executed", extra={"event": "command", "cmd": cmd})
    result = send_command(cmd)
    typer.echo(json.dumps(result, indent=2))


@app.command()
def deck() -> None:
    """Show the current deck."""
    result = send_command("state")
    typer.echo(json.dumps(extract_game_state_field(result, "deck"), indent=2))


@app.command()
def relics() -> None:
    """Show the current relics."""
    result = send_command("state")
    typer.echo(json.dumps(extract_game_state_field(result, "relics"), indent=2))


@app.command()
def potions() -> None:
    """Show the current potions."""
    result = send_command("state")
    typer.echo(json.dumps(extract_game_state_field(result, "potions"), indent=2))


@app.command("map")
def map_cmd() -> None:
    """Show the current map."""
    result = send_command("state")
    typer.echo(json.dumps(extract_game_state_field(result, "map"), indent=2))


@app.command()
def recall(query: str) -> None:
    """Recall memories from Hindsight."""
    logger.info("recall executed", extra={"event": "recall", "query": query})
    client = Hindsight(base_url=HINDSIGHT_URL)
    result = client.recall(
        bank_id=BANK_ID,
        query=query,
        types=["world", "experience", "observation"],
        max_tokens=2048,
        query_timestamp=datetime.now(UTC).isoformat(),
    )
    # Convert RecallResponse to JSON
    output = result.to_dict() if hasattr(result, "to_dict") else str(result)
    typer.echo(json.dumps(output, indent=2, default=str))
    results: list[dict[str, Any]] = (
        output.get("results", []) if isinstance(output, dict) else []
    )
    logger.info(
        "recall result",
        extra={
            "event": "recall_result",
            "result_count": len(results),
            "types": list({r.get("type") for r in results if r.get("type")}),
            "results": [
                {
                    "id": r.get("id"),
                    "type": r.get("type"),
                    "text": r.get("text", "")[:200],
                    "occurred": r.get("occurred_start"),
                }
                for r in results
            ],
        },
    )


@app.command()
def retain(content: str, document_id: str | None = None) -> None:
    """Store a memory in Hindsight."""
    client = Hindsight(base_url=HINDSIGHT_URL)
    item: dict[str, Any] = {
        "content": content,
        "context": RETAIN_CONTEXT,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    if document_id:
        item["document_id"] = document_id
        item["update_mode"] = "append"
    result = client.retain_batch(
        bank_id=BANK_ID,
        items=[item],
        retain_async=True,
    )
    output: dict[str, Any] = {
        "success": result.success,
        "items_count": result.items_count,
    }
    extra: dict[str, Any] = {"event": "retain", "content": content}
    if result.operation_id:
        op_id = str(result.operation_id)
        extra["op_id"] = op_id
        output["operation_id"] = op_id
    logger.info("retain executed", extra=extra)
    typer.echo(json.dumps(output, indent=2, default=str))


def main() -> None:
    init_logger()
    app()


if __name__ == "__main__":
    main()
