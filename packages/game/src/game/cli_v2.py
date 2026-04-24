# pyright: reportArgumentType=none, reportUnknownArgumentType=none, reportUnknownVariableType=none, reportUnknownMemberType=none
import json
import logging
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, override

import httpx
import typer
from hindsight_client import Hindsight

logger = logging.getLogger(__name__)


class JsonlFormatter(logging.Formatter):
    """Format log records as JSON Lines."""

    _STANDARD_ATTRS = frozenset({
        "name", "msg", "args", "levelname", "levelno", "pathname",
        "filename", "module", "exc_info", "exc_text", "stack_info",
        "lineno", "funcName", "created", "msecs", "relativeCreated",
        "thread", "threadName", "processName", "process", "message",
        "asctime", "taskName",
    })

    @override
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "ts": (
                datetime.fromtimestamp(record.created)
                .astimezone()
                .isoformat(timespec="milliseconds")
            ),
            "lvl": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        entry |= {
            key: value
            for key, value in record.__dict__.items()
            if key not in self._STANDARD_ATTRS and not key.startswith("_")
        }
        return json.dumps(entry, ensure_ascii=False, default=str)

BANK_ID = "sts-v2"
RETAIN_CONTEXT = (
    "Slay the Spire gameplay: strategic decisions, build directions, "
    "enemy patterns, card synergies, combat lessons. "
    "Ignore raw state snapshots."
)
PROXY_URL = "http://127.0.0.1:8766/command"
TIMEOUT = 30.0

NOISE_KEYS = {"deck", "relics", "potions", "map"}

# Initialize Hindsight client once at module level
_hindsight_client: Hindsight | None = None


class _HindsightClient:
    """Lazy-initialized singleton for Hindsight client."""

    _instance: Hindsight | None = None

    @classmethod
    def get(cls) -> Hindsight:
        if cls._instance is None:
            cls._instance = Hindsight(base_url="http://localhost:8888")
        return cls._instance


def init_logger() -> None:
    handler = RotatingFileHandler(
        Path.home() / ".sts" / "logs" / "game.jsonl",
        maxBytes=10_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(JsonlFormatter())

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)

    # Package logger at DEBUG for detailed output
    logging.getLogger("game").setLevel(logging.DEBUG)


app = typer.Typer(no_args_is_help=True, add_completion=False)


def send_command(cmd: str) -> dict[str, Any]:
    response = httpx.post(PROXY_URL, content=cmd, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def filter_game_state(data: dict[str, Any]) -> dict[str, Any]:
    game_state = data.get("game_state")
    if game_state is None:
        return data
    for key in NOISE_KEYS:
        game_state.pop(key, None)
    return data


def extract_game_state_field(data: dict[str, Any], key: str) -> Any:  # noqa: ANN401
    game_state = data.get("game_state", {})
    return game_state.get(key)


@app.command()
def command(cmd: str) -> None:
    """Send a raw command to the game."""
    logger.info("command executed", extra={"event": "command", "cmd": cmd})
    result = send_command(cmd)
    result = filter_game_state(result)
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
    client = _HindsightClient.get()
    result = client.recall(
        bank_id=BANK_ID,
        query=query,
        types=["world", "experience", "observation"],
    )
    # Convert RecallResponse to JSON
    output = result.to_dict() if hasattr(result, "to_dict") else str(result)
    typer.echo(json.dumps(output, indent=2, default=str))
    results = output.get("results", []) if isinstance(output, dict) else []
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
    client = _HindsightClient.get()
    item: dict[str, Any] = {
        "content": content,
        "context": RETAIN_CONTEXT,
        "timestamp": datetime.now(timezone.utc),  # noqa: UP017
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
