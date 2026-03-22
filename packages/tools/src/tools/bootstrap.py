import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import typer
from core.paths import ROOT_DIR

app = typer.Typer(add_completion=False, help="Bootstrap the workspace after checkout.")

READY_MESSAGE = "Workspace bootstrap is complete."

_SYNC_SUBMODULES_COMMAND = ("git", "submodule", "sync", "--recursive")
_UPDATE_SUBMODULES_COMMAND = ("git", "submodule", "update", "--init", "--recursive")


@dataclass(frozen=True)
class Step:
    message: str
    commands: tuple[tuple[str, ...], ...]


class CommandRunner(Protocol):
    def run(self, args: tuple[str, ...], *, cwd: Path) -> None: ...


@dataclass(frozen=True, kw_only=True)
class Config:
    working_dir: Path
    command_runner: CommandRunner
    message_writer: Callable[[str], None]


class SubprocessCommandRunner:
    def run(self, args: tuple[str, ...], *, cwd: Path) -> None:
        subprocess.run(  # noqa: S603 - fixed command tuples from this module only
            args,
            cwd=cwd,
            check=True,
        )


def _get_config(context: typer.Context) -> Config:
    if not isinstance(context.obj, Config):
        raise TypeError("bootstrap app requires Config in context.obj")
    return context.obj


def _iter_bootstrap_commands() -> tuple[tuple[str, ...], ...]:
    return (_SYNC_SUBMODULES_COMMAND, _UPDATE_SUBMODULES_COMMAND)


def _iter_steps() -> tuple[Step, ...]:
    return (
        Step(
            message="Initialize git submodules.",
            commands=_iter_bootstrap_commands(),
        ),
    )


def _run_step(step: Step, config: Config) -> None:
    for command in step.commands:
        config.command_runner.run(command, cwd=config.working_dir)


def run(config: Config) -> None:
    for step in _iter_steps():
        config.message_writer(step.message)
        _run_step(step, config)


@app.command(help="Bootstrap the workspace after checkout.")
def bootstrap_workspace(context: typer.Context) -> None:
    config = _get_config(context)
    run(config)
    config.message_writer(READY_MESSAGE)


def main() -> None:
    app(
        obj=Config(
            working_dir=ROOT_DIR,
            command_runner=SubprocessCommandRunner(),
            message_writer=typer.echo,
        )
    )
