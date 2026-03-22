import sys
from dataclasses import dataclass
from pathlib import Path

import pytest
import typer
from tools import build_mod
from typer.testing import CliRunner

runner = CliRunner()


@dataclass(frozen=True)
class RecordedCommand:
    args: tuple[str, ...]
    cwd: Path
    env: dict[str, str]


class RecordingCommandRunner:
    def __init__(self, *, should_create_build_jar: bool = False) -> None:
        self.calls: list[RecordedCommand] = []
        self._should_create_build_jar = should_create_build_jar

    def __call__(self, args: list[str], *, cwd: Path, env: dict[str, str]) -> None:
        recorded_command = RecordedCommand(
            args=tuple(args),
            cwd=cwd,
            env=env,
        )
        self.calls.append(recorded_command)

        if not self._should_create_build_jar:
            return

        build_jar = _extract_build_jar(recorded_command.args)
        build_jar.parent.mkdir(parents=True, exist_ok=True)
        build_jar.write_text("jar")


class RecordingMessageWriter:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def __call__(self, message: str) -> None:
        self.messages.append(message)


def _extract_build_jar(args: tuple[str, ...]) -> Path:
    prefix = "-Dcommunicationmod.build.jar="
    for arg in args:
        if arg.startswith(prefix):
            return Path(arg.removeprefix(prefix))

    raise AssertionError("Missing build jar argument.")


def _create_config(
    root_dir: Path,
    *,
    command_runner: build_mod.CommandRunner,
    message_writer: build_mod.MessageWriter,
    env: dict[str, str] | None = None,
) -> build_mod.Config:
    communication_mod_dir = root_dir / "CommunicationMod"
    resources_dir = root_dir / "resources"
    workshop_dir = root_dir / "workshop"

    communication_mod_dir.mkdir(parents=True)
    resources_dir.mkdir(parents=True)
    workshop_dir.mkdir(parents=True)

    desktop_jar = resources_dir / "desktop-1.0.jar"
    mod_the_spire_jar = workshop_dir / "ModTheSpire.jar"
    base_mod_jar = workshop_dir / "BaseMod.jar"

    desktop_jar.write_text("desktop")
    mod_the_spire_jar.write_text("mts")
    base_mod_jar.write_text("basemod")

    return build_mod.Config(
        command_runner=command_runner,
        message_writer=message_writer,
        working_dir=root_dir,
        desktop_jar=desktop_jar,
        mod_the_spire_jar=mod_the_spire_jar,
        base_mod_jar=base_mod_jar,
        build_jar=root_dir / ".work" / "CommunicationMod.jar",
        communication_mod_jar=resources_dir / "mods" / "CommunicationMod.jar",
        communication_mod_dir=communication_mod_dir,
        env={"PATH": "/usr/bin", "JAVA_HOME": "/java8"} if env is None else env,
    )


def test__run_command_executes_process_with_working_dir_and_environment(
    tmp_path: Path,
) -> None:
    output_file = tmp_path / "command.txt"
    script = (
        "import os\n"
        "from pathlib import Path\n"
        f"Path({str(output_file)!r}).write_text("
        "str(Path.cwd()) + '\\n' + os.environ['BUILD_ENV']"
        ")\n"
    )

    build_mod._run_command(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env={"BUILD_ENV": "configured"},
    )

    assert output_file.read_text() == f"{tmp_path}\nconfigured"


def test__run_invokes_maven_command_and_installs_mod_jar(tmp_path: Path) -> None:
    command_runner = RecordingCommandRunner(should_create_build_jar=True)
    message_writer = RecordingMessageWriter()
    config = _create_config(
        tmp_path,
        command_runner=command_runner,
        message_writer=message_writer,
    )

    build_mod._run(config)

    assert message_writer.messages == [
        "Resolve required game and mod artifacts.",
        "Prepare build workspace.",
        "Build CommunicationMod with Maven.",
        "Install CommunicationMod jar.",
    ]
    assert command_runner.calls == [
        RecordedCommand(
            args=(
                "mvn",
                f"-Dcommunicationmod.desktop.jar={config.desktop_jar}",
                f"-Dcommunicationmod.modthespire.jar={config.mod_the_spire_jar}",
                f"-Dcommunicationmod.basemod.jar={config.base_mod_jar}",
                f"-Dcommunicationmod.build.jar={config.build_jar}",
                "clean",
                "package",
            ),
            cwd=config.communication_mod_dir,
            env=config.env,
        )
    ]
    assert config.build_jar.exists()
    assert config.communication_mod_jar.is_symlink()
    assert config.communication_mod_jar.resolve() == config.build_jar.resolve()


def test__run_replaces_existing_installed_jar(tmp_path: Path) -> None:
    command_runner = RecordingCommandRunner(should_create_build_jar=True)
    config = _create_config(
        tmp_path,
        command_runner=command_runner,
        message_writer=RecordingMessageWriter(),
    )
    config.communication_mod_jar.parent.mkdir(parents=True, exist_ok=True)
    config.communication_mod_jar.write_text("old jar")

    build_mod._run(config)

    assert config.communication_mod_jar.is_symlink()
    assert config.communication_mod_jar.resolve() == config.build_jar.resolve()


def test__run_requires_all_game_and_mod_artifacts(tmp_path: Path) -> None:
    command_runner = RecordingCommandRunner()
    message_writer = RecordingMessageWriter()
    config = _create_config(
        tmp_path,
        command_runner=command_runner,
        message_writer=message_writer,
    )
    config.base_mod_jar.unlink()

    with pytest.raises(
        RuntimeError,
        match=r"Required file does not exist: .*BaseMod\.jar",
    ):
        build_mod._run(config)

    assert message_writer.messages == ["Resolve required game and mod artifacts."]
    assert command_runner.calls == []
    assert not config.communication_mod_jar.exists()


def test_build_mod_command_outputs_complete_message(tmp_path: Path) -> None:
    config = _create_config(
        tmp_path,
        command_runner=RecordingCommandRunner(should_create_build_jar=True),
        message_writer=typer.echo,
    )

    result = runner.invoke(build_mod.app, [], obj=config)

    assert result.exit_code == 0
    assert result.output.endswith("CommunicationMod build is complete.\n")


def test_build_mod_help_is_available() -> None:
    result = runner.invoke(build_mod.app, ["--help"])

    assert result.exit_code == 0
    assert "Build CommunicationMod for local testing." in result.output
    assert "COMMAND [ARGS]..." not in result.output
