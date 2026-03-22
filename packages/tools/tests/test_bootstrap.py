from dataclasses import dataclass
from pathlib import Path

from tools import bootstrap
from typer.testing import CliRunner

runner = CliRunner()


@dataclass(frozen=True)
class CommandCall:
    args: tuple[str, ...]
    cwd: Path


class RecordingCommandRunner:
    def __init__(self) -> None:
        self.calls: list[CommandCall] = []

    def run(self, args: tuple[str, ...], *, cwd: Path) -> None:
        self.calls.append(CommandCall(args=args, cwd=cwd))


class RecordingMessageWriter:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def __call__(self, message: str) -> None:
        self.messages.append(message)


def test_run_runs_git_submodule_commands_in_order(tmp_path: Path) -> None:
    command_runner = RecordingCommandRunner()
    message_writer = RecordingMessageWriter()

    bootstrap.run(
        bootstrap.Config(
            working_dir=tmp_path,
            command_runner=command_runner,
            message_writer=message_writer,
        )
    )

    assert command_runner.calls == [
        CommandCall(
            args=("git", "submodule", "sync", "--recursive"),
            cwd=tmp_path,
        ),
        CommandCall(
            args=("git", "submodule", "update", "--init", "--recursive"),
            cwd=tmp_path,
        ),
    ]


def test_run_reports_semantic_step_messages(tmp_path: Path) -> None:
    command_runner = RecordingCommandRunner()
    message_writer = RecordingMessageWriter()

    bootstrap.run(
        bootstrap.Config(
            working_dir=tmp_path,
            command_runner=command_runner,
            message_writer=message_writer,
        )
    )

    assert message_writer.messages == ["Initialize git submodules."]


def test_bootstrap_command_outputs_success_message(tmp_path: Path) -> None:
    command_runner = RecordingCommandRunner()
    message_writer = bootstrap.typer.echo

    result = runner.invoke(
        bootstrap.app,
        [],
        obj=bootstrap.Config(
            working_dir=tmp_path,
            command_runner=command_runner,
            message_writer=message_writer,
        ),
    )

    assert result.exit_code == 0
    assert result.output == (
        "Initialize git submodules.\nWorkspace bootstrap is complete.\n"
    )


def test_bootstrap_help_is_available() -> None:
    result = runner.invoke(bootstrap.app, ["--help"])

    assert result.exit_code == 0
    assert "Bootstrap the workspace after checkout." in result.output
    assert "COMMAND [ARGS]..." not in result.output
