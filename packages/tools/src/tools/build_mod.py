import os
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import typer
from core import paths

app = typer.Typer(
    add_completion=False,
    help="Build CommunicationMod.",
)


class CommandRunner(Protocol):
    def run(
        self,
        args: tuple[str, ...],
        *,
        cwd: Path,
        env: Mapping[str, str] | None = None,
    ) -> None: ...


@dataclass(frozen=True, kw_only=True)
class BuildPaths:
    communication_mod_dir: Path
    staged_mod_jar: Path
    slay_the_spire_jar: Path
    modthespire_jar: Path
    basemod_jar: Path
    installed_mod_jar: Path
    java_home: Path


@dataclass(frozen=True, kw_only=True)
class Config:
    working_dir: Path
    environment: Mapping[str, str]
    command_runner: CommandRunner
    message_writer: Callable[[str], None]
    build_paths: BuildPaths | None = None


class BuildModError(Exception):
    pass


class SubprocessCommandRunner:
    def run(
        self,
        args: tuple[str, ...],
        *,
        cwd: Path,
        env: Mapping[str, str] | None = None,
    ) -> None:
        subprocess.run(  # noqa: S603 - fixed command tuples from this module only
            args,
            cwd=cwd,
            env=None if env is None else dict(env),
            check=True,
        )


def resolve_paths(config: Config) -> BuildPaths:
    communication_mod_dir = paths.get_communication_mod_dir(config.working_dir)

    return BuildPaths(
        communication_mod_dir=communication_mod_dir,
        staged_mod_jar=paths.BUILD_MOD_STAGED_MOD_JAR,
        slay_the_spire_jar=paths.BUILD_MOD_DEFAULT_SLAY_THE_SPIRE_JAR,
        modthespire_jar=paths.BUILD_MOD_DEFAULT_MODTHESPIRE_JAR,
        basemod_jar=paths.BUILD_MOD_DEFAULT_BASEMOD_JAR,
        installed_mod_jar=paths.BUILD_MOD_DEFAULT_INSTALLED_MOD_JAR,
        java_home=paths.BUILD_MOD_DEFAULT_JAVA_HOME,
    )


def _require_file(path: Path, *, label: str) -> None:
    if not path.is_file():
        raise BuildModError(f"Missing {label}: {path}")


def validate_artifacts(build_paths: BuildPaths) -> None:
    _require_file(build_paths.slay_the_spire_jar, label="Slay the Spire desktop JAR")
    _require_file(build_paths.modthespire_jar, label="ModTheSpire JAR")
    _require_file(build_paths.basemod_jar, label="BaseMod JAR")


def _link_file(source_path: Path, destination_path: Path) -> None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    if destination_path.is_symlink() or destination_path.exists():
        destination_path.unlink()

    destination_path.symlink_to(source_path)


def prepare_build_workspace(build_paths: BuildPaths) -> None:
    build_paths.staged_mod_jar.parent.mkdir(parents=True, exist_ok=True)
    build_paths.installed_mod_jar.parent.mkdir(parents=True, exist_ok=True)


def _build_maven_environment(config: Config, build_paths: BuildPaths) -> dict[str, str]:
    path_entries = [str(build_paths.java_home / "bin")]
    existing_path = config.environment.get("PATH")
    if existing_path:
        path_entries.append(existing_path)

    return {
        **config.environment,
        "JAVA_HOME": str(build_paths.java_home),
        "PATH": ":".join(path_entries),
    }


def build_with_maven(config: Config, build_paths: BuildPaths) -> None:
    config.command_runner.run(
        (
            "mvn",
            f"-Dcommunicationmod.slaythespire.jar={build_paths.slay_the_spire_jar}",
            f"-Dcommunicationmod.modthespire.jar={build_paths.modthespire_jar}",
            f"-Dcommunicationmod.staged.jar={build_paths.staged_mod_jar}",
            f"-Dcommunicationmod.basemod.jar={build_paths.basemod_jar}",
            "clean",
            "package",
        ),
        cwd=build_paths.communication_mod_dir,
        env=_build_maven_environment(config, build_paths),
    )


def install_mod(build_paths: BuildPaths) -> None:
    _require_file(build_paths.staged_mod_jar, label="built CommunicationMod JAR")
    _link_file(build_paths.staged_mod_jar, build_paths.installed_mod_jar)


def run(config: Config, *, paths: BuildPaths | None = None) -> None:
    build_paths = config.build_paths if paths is None else paths
    if build_paths is None:
        build_paths = resolve_paths(config)

    config.message_writer("Resolve required game and mod artifacts.")
    validate_artifacts(build_paths)

    config.message_writer("Prepare build workspace.")
    prepare_build_workspace(build_paths)

    config.message_writer("Build CommunicationMod with Maven.")
    build_with_maven(config, build_paths)

    config.message_writer("Install CommunicationMod jar.")
    install_mod(build_paths)


@app.command(help="Build CommunicationMod for local testing.")
def build_mod_command(context: typer.Context) -> None:
    config: Config = context.obj

    try:
        run(config)
    except BuildModError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1) from e

    config.message_writer("CommunicationMod build is complete.")


def main() -> None:
    app(
        obj=Config(
            working_dir=paths.ROOT_DIR,
            environment=os.environ,
            command_runner=SubprocessCommandRunner(),
            message_writer=typer.echo,
        )
    )
