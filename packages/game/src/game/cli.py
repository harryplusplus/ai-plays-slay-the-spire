import json
import logging
from typing import Any, override

import typer
from game.commands.command import command as execute_command
from game.commands.recall import recall as execute_recall
from game.commands.retain import retain as execute_retain
from game.commands.screenshot import screenshot as execute_screenshot
from game.log import init_logger
from typer.core import TyperGroup

logger = logging.getLogger(__name__)


class ErrorHandlerTyperGroup(TyperGroup):
    @override
    def invoke(self, ctx: Any) -> Any:
        try:
            return super().invoke(ctx)
        except typer.Exit:
            raise
        except Exception as e:
            typer.echo(json.dumps({"error": str(e)}))
            raise


app = typer.Typer(
    cls=ErrorHandlerTyperGroup, no_args_is_help=True, add_completion=False
)


@app.command()
def command(command: str) -> None:
    """Send a raw command to the game."""
    result = execute_command(command)
    typer.echo(json.dumps(result, indent=2))


@app.command()
def recall(query: str) -> None:
    """Recall memories from Hindsight."""
    result = execute_recall(query)
    typer.echo(json.dumps(result, indent=2, default=str))


@app.command()
def retain(content: str, document_id: str | None = None) -> None:
    """Store a memory in Hindsight."""
    result = execute_retain(content, document_id)
    typer.echo(json.dumps(result, indent=2, default=str))


@app.command()
def screenshot() -> None:
    """Capture Slay the Spire window and save as JPEG."""
    result = execute_screenshot()
    typer.echo(json.dumps(result))


def main() -> None:
    init_logger()
    app()


if __name__ == "__main__":
    main()
