from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import typer
from core import paths as core_paths
from tools import build_mod
from typer.testing import CliRunner

runner = CliRunner()


@dataclass(frozen=True)
class CommandCall:
    args: tuple[str, ...]
    cwd: Path
    env: Mapping[str, str] | None


class RecordingCommandRunner:
    def __init__(self, *, staged_mod_jar: Path | None = None) -> None:
        self.calls: list[CommandCall] = []
        self._staged_mod_jar = staged_mod_jar

    def run(
        self,
        args: tuple[str, ...],
        *,
        cwd: Path,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self.calls.append(CommandCall(args=args, cwd=cwd, env=env))

        if self._staged_mod_jar is not None and args[:1] == ("mvn",):
            self._staged_mod_jar.parent.mkdir(parents=True, exist_ok=True)
            self._staged_mod_jar.write_text("jar")


class RecordingMessageWriter:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def __call__(self, message: str) -> None:
        self.messages.append(message)


def _create_java_home(java_home: Path) -> None:
    (java_home / "bin").mkdir(parents=True)


def _create_build_inputs(root_dir: Path) -> dict[str, Path]:
    communication_mod_dir = root_dir / "third_party" / "CommunicationMod"
    game_dir = root_dir / "game"
    workshop_dir = root_dir / "workshop"
    sts_mods_dir = root_dir / "sts_mods"
    java_home = root_dir / "java8"
    desktop_jar = core_paths.get_build_mod_slay_the_spire_jar(game_dir)
    modthespire_jar = core_paths.get_build_mod_modthespire_jar(workshop_dir)
    basemod_jar = core_paths.get_build_mod_basemod_jar(workshop_dir)

    communication_mod_dir.mkdir(parents=True)
    sts_mods_dir.mkdir()

    (communication_mod_dir / "pom.xml").write_text("<project />")
    desktop_jar.parent.mkdir(parents=True)
    modthespire_jar.parent.mkdir(parents=True)
    basemod_jar.parent.mkdir(parents=True)
    desktop_jar.write_text("desktop")
    modthespire_jar.write_text("mts")
    basemod_jar.write_text("basemod")

    _create_java_home(java_home)

    return {
        "communication_mod_dir": communication_mod_dir,
        "desktop_jar": desktop_jar,
        "modthespire_jar": modthespire_jar,
        "basemod_jar": basemod_jar,
        "sts_mods_dir": sts_mods_dir,
        "java_home": java_home,
    }


def _create_environment() -> dict[str, str]:
    return {
        "PATH": "/usr/bin",
    }


def test_resolve_paths_uses_working_dir_and_production_defaults(tmp_path: Path) -> None:
    config = build_mod.Config(
        working_dir=tmp_path,
        environment={"PATH": "/usr/bin"},
        command_runner=RecordingCommandRunner(),
        message_writer=RecordingMessageWriter(),
    )

    paths = build_mod.resolve_paths(config)

    assert paths.communication_mod_dir == tmp_path / "third_party" / "CommunicationMod"
    assert paths.staged_mod_jar == core_paths.BUILD_MOD_STAGED_MOD_JAR
    assert paths.slay_the_spire_jar == core_paths.BUILD_MOD_DEFAULT_SLAY_THE_SPIRE_JAR
    assert paths.modthespire_jar == core_paths.BUILD_MOD_DEFAULT_MODTHESPIRE_JAR
    assert paths.basemod_jar == core_paths.BUILD_MOD_DEFAULT_BASEMOD_JAR
    assert paths.installed_mod_jar == core_paths.BUILD_MOD_DEFAULT_INSTALLED_MOD_JAR
    assert paths.java_home == core_paths.BUILD_MOD_DEFAULT_JAVA_HOME


def test_run_builds_and_installs_communication_mod(tmp_path: Path) -> None:
    inputs = _create_build_inputs(tmp_path)
    paths = build_mod.BuildPaths(
        communication_mod_dir=inputs["communication_mod_dir"],
        staged_mod_jar=core_paths.get_build_mod_staged_mod_jar(tmp_path),
        slay_the_spire_jar=inputs["desktop_jar"],
        modthespire_jar=inputs["modthespire_jar"],
        basemod_jar=inputs["basemod_jar"],
        installed_mod_jar=core_paths.get_build_mod_installed_mod_jar(
            inputs["sts_mods_dir"]
        ),
        java_home=inputs["java_home"],
    )
    command_runner = RecordingCommandRunner(staged_mod_jar=paths.staged_mod_jar)
    message_writer = RecordingMessageWriter()
    config = build_mod.Config(
        working_dir=tmp_path,
        environment=_create_environment(),
        command_runner=command_runner,
        message_writer=message_writer,
        build_paths=paths,
    )

    build_mod.run(config, paths=paths)

    assert message_writer.messages == [
        "Resolve required game and mod artifacts.",
        "Prepare build workspace.",
        "Build CommunicationMod with Maven.",
        "Install CommunicationMod jar.",
    ]
    assert command_runner.calls == [
        CommandCall(
            args=(
                "mvn",
                f"-Dcommunicationmod.slaythespire.jar={inputs['desktop_jar']}",
                f"-Dcommunicationmod.modthespire.jar={inputs['modthespire_jar']}",
                "-Dcommunicationmod.staged.jar="
                f"{core_paths.get_build_mod_staged_mod_jar(tmp_path)}",
                f"-Dcommunicationmod.basemod.jar={inputs['basemod_jar']}",
                "clean",
                "package",
            ),
            cwd=inputs["communication_mod_dir"],
            env={
                **_create_environment(),
                "JAVA_HOME": str(inputs["java_home"]),
                "PATH": f"{inputs['java_home'] / 'bin'}:/usr/bin",
            },
        )
    ]
    assert paths.installed_mod_jar.is_symlink()
    assert paths.installed_mod_jar.resolve() == paths.staged_mod_jar.resolve()


def test_build_mod_command_outputs_ready_message(tmp_path: Path) -> None:
    inputs = _create_build_inputs(tmp_path)
    command_runner = RecordingCommandRunner(
        staged_mod_jar=(
            tmp_path / ".work" / "build_mod" / "mods" / "CommunicationMod.jar"
        )
    )
    config = build_mod.Config(
        working_dir=tmp_path,
        environment=_create_environment(),
        command_runner=command_runner,
        message_writer=typer.echo,
        build_paths=build_mod.BuildPaths(
            communication_mod_dir=inputs["communication_mod_dir"],
            staged_mod_jar=core_paths.get_build_mod_staged_mod_jar(tmp_path),
            slay_the_spire_jar=inputs["desktop_jar"],
            modthespire_jar=inputs["modthespire_jar"],
            basemod_jar=inputs["basemod_jar"],
            installed_mod_jar=core_paths.get_build_mod_installed_mod_jar(
                inputs["sts_mods_dir"]
            ),
            java_home=inputs["java_home"],
        ),
    )

    result = runner.invoke(build_mod.app, [], obj=config)

    assert result.exit_code == 0
    assert result.output.endswith("CommunicationMod build is complete.\n")


def test_build_mod_help_is_available() -> None:
    result = runner.invoke(build_mod.app, ["--help"])

    assert result.exit_code == 0
    assert "Build CommunicationMod for local testing." in result.output
    assert "COMMAND [ARGS]..." not in result.output
