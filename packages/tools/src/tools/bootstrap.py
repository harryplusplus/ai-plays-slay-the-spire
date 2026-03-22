import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import typer
from core.paths import ROOT_DIR
from typing_extensions import override

app = typer.Typer(add_completion=False, help="Bootstrap the workspace after checkout.")


@dataclass(frozen=True, kw_only=True)
class Step:
    message: str
    commands: list[list[str]]


_STEPS = [
    Step(
        message="Initialize git submodules.",
        commands=[
            ["git", "submodule", "sync", "--recursive"],
            ["git", "submodule", "update", "--init", "--recursive"],
        ],
    ),
]


class CommandRunner(Protocol):
    def __call__(self, args: list[str], *, cwd: Path) -> None: ...


class MessageWriter(Protocol):
    def __call__(self, message: str) -> None: ...


@dataclass(frozen=True, kw_only=True)
class Config:
    working_dir: Path
    command_runner: CommandRunner
    message_writer: MessageWriter


class SubprocessCommandRunner(CommandRunner):
    @override
    def __call__(self, args: list[str], *, cwd: Path) -> None:
        subprocess.run(  # noqa: S603
            args,
            cwd=cwd,
            check=True,
        )


def run(config: Config) -> None:
    for step in _STEPS:
        config.message_writer(step.message)
        for command in step.commands:
            config.command_runner(command, cwd=config.working_dir)


@app.command(help="Bootstrap the workspace after checkout.")
def bootstrap(context: typer.Context) -> None:
    config: Config = context.obj
    run(config)
    config.message_writer("Workspace bootstrap is complete.")


def main() -> None:
    app(
        obj=Config(
            working_dir=ROOT_DIR,
            command_runner=SubprocessCommandRunner(),
            message_writer=typer.echo,
        )
    )
