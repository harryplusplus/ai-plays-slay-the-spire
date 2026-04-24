import json
import logging
import subprocess
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, override

import httpx
import typer

logger = logging.getLogger(__name__)

BANK_ID = "sts"
RETAIN_CONTEXT = "Slay the Spire gameplay"
PROXY_URL = "http://127.0.0.1:8766/command"
TIMEOUT = 30.0

NOISE_KEYS = {"deck", "relics", "potions", "map"}


def init_logger() -> None:
    class Formatter(logging.Formatter):
        @override
        def formatTime(
            self,
            record: logging.LogRecord,
            datefmt: str | None = None,
        ) -> str:
            return (
                datetime.fromtimestamp(record.created)
                .astimezone()
                .isoformat(timespec="milliseconds")
            )

    handler = RotatingFileHandler(
        Path.home() / ".sts" / "logs" / "game.log",
        maxBytes=10_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(
        Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"),
    )

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)


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
    logger.info("command: %s", cmd)
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
    logger.info("recall: %s", query)
    result = subprocess.run(
        [
            "hindsight",
            "memory",
            "recall",
            BANK_ID,
            query,
            "--output",
            "json",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    typer.echo(result.stdout)
    logger.info("recall result: %s", result.stdout[:200])


@app.command()
def retain(content: str) -> None:
    """Store a memory in Hindsight."""
    logger.info("retain: %s", content)
    result = subprocess.run(
        [
            "hindsight",
            "memory",
            "retain",
            BANK_ID,
            content,
            "--output",
            "json",
            "--context",
            RETAIN_CONTEXT,
            "--async",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    typer.echo(result.stdout)


def main() -> None:
    init_logger()
    app()


if __name__ == "__main__":
    main()
