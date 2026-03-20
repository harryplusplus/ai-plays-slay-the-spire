from typing import Annotated

import typer

from sts import log

app = typer.Typer()


@app.command()
def command(command: Annotated[str, typer.Argument()]) -> None:
    # TODO: add to pending_commands
    pass


@app.command()
def events() -> None:
    # TODO: read events from events
    pass


def main() -> None:
    log.init()
    app()
