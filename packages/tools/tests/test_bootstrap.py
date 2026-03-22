import sys
from dataclasses import dataclass
from pathlib import Path

import typer
from tools import bootstrap
from typer.testing import CliRunner

runner = CliRunner()


@dataclass(frozen=True)
class RecordedCommand:
    args: tuple[str, ...]
    cwd: Path


class RecordingCommandRunner:
    def __init__(self) -> None:
        self.calls: list[RecordedCommand] = []

    def __call__(self, args: list[str], *, cwd: Path) -> None:
        self.calls.append(RecordedCommand(args=tuple(args), cwd=cwd))


class RecordingMessageWriter:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def __call__(self, message: str) -> None:
        self.messages.append(message)


def test__run_executes_git_submodule_commands_in_order(tmp_path: Path) -> None:
    command_runner = RecordingCommandRunner()
    message_writer = RecordingMessageWriter()

    bootstrap._run(
        bootstrap.Config(
            working_dir=tmp_path,
            command_runner=command_runner,
            message_writer=message_writer,
        )
    )

    assert command_runner.calls == [
        RecordedCommand(
            args=("git", "submodule", "sync", "--recursive"),
            cwd=tmp_path,
        ),
        RecordedCommand(
            args=("git", "submodule", "update", "--init", "--recursive"),
            cwd=tmp_path,
        ),
    ]


def test__run_emits_step_messages(tmp_path: Path) -> None:
    command_runner = RecordingCommandRunner()
    message_writer = RecordingMessageWriter()

    bootstrap._run(
        bootstrap.Config(
            working_dir=tmp_path,
            command_runner=command_runner,
            message_writer=message_writer,
        )
    )

    assert message_writer.messages == ["Initialize git submodules."]


def test__run_command_executes_process_in_working_dir(tmp_path: Path) -> None:
    output_file = tmp_path / "cwd.txt"
    bootstrap._run_command(
        [
            sys.executable,
            "-c",
            (
                "from pathlib import Path; "
                f"Path({str(output_file)!r}).write_text(str(Path.cwd()))"
            ),
        ],
        cwd=tmp_path,
    )

    assert output_file.read_text() == str(tmp_path)


def test_bootstrap_command_outputs_success_message(tmp_path: Path) -> None:
    command_runner = RecordingCommandRunner()

    result = runner.invoke(
        bootstrap.app,
        [],
        obj=bootstrap.Config(
            working_dir=tmp_path,
            command_runner=command_runner,
            message_writer=typer.echo,
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
