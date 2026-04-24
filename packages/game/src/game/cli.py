import json
from typing import Any

import httpx
import typer

PROXY_URL = "http://127.0.0.1:8766/command"
TIMEOUT = 30.0

NOISE_KEYS = {"deck", "relics", "potions", "map"}

app = typer.Typer(no_args_is_help=True)


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


@app.command()
def map_cmd() -> None:
    """Show the current map."""
    result = send_command("state")
    typer.echo(json.dumps(extract_game_state_field(result, "map"), indent=2))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
