import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import typer
from core import paths

app = typer.Typer(
    add_completion=False,
    help="Build CommunicationMod.",
)


class MessageWriter(Protocol):
    def __call__(self, message: str) -> None: ...


class CommandRunner(Protocol):
    def __call__(
        self,
        args: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
    ) -> None: ...


@dataclass(frozen=True, kw_only=True)
class Config:
    command_runner: CommandRunner
    message_writer: MessageWriter
    working_dir: Path
    desktop_jar: Path
    mod_the_spire_jar: Path
    base_mod_jar: Path
    build_jar: Path
    communication_mod_jar: Path
    communication_mod_dir: Path
    env: dict[str, str]


def _run_command(
    args: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
) -> None:
    subprocess.run(
        args,
        cwd=cwd,
        env=env,
        check=True,
    )


def _require_file(path: Path) -> None:
    if not path.is_file():
        raise RuntimeError(f"Required file does not exist: {path}")


def _unlink_if_exists(path: Path) -> None:
    if path.is_symlink() or path.exists():
        path.unlink()


def _run(config: Config) -> None:
    config.message_writer("Resolve required game and mod artifacts.")
    _require_file(config.desktop_jar)
    _require_file(config.mod_the_spire_jar)
    _require_file(config.base_mod_jar)

    config.message_writer("Prepare build workspace.")
    config.build_jar.parent.mkdir(parents=True, exist_ok=True)

    config.message_writer("Build CommunicationMod with Maven.")
    config.command_runner(
        [
            "mvn",
            f"-Dcommunicationmod.desktop.jar={config.desktop_jar}",
            f"-Dcommunicationmod.modthespire.jar={config.mod_the_spire_jar}",
            f"-Dcommunicationmod.basemod.jar={config.base_mod_jar}",
            f"-Dcommunicationmod.build.jar={config.build_jar}",
            "clean",
            "package",
        ],
        cwd=config.communication_mod_dir,
        env=config.env,
    )

    config.message_writer("Install CommunicationMod jar.")
    config.communication_mod_jar.parent.mkdir(parents=True, exist_ok=True)
    _unlink_if_exists(config.communication_mod_jar)

    config.communication_mod_jar.symlink_to(config.build_jar)


@app.command(help="Build CommunicationMod for local testing.")
def build_mod(context: typer.Context) -> None:
    config: Config = context.obj
    _run(config)
    config.message_writer("CommunicationMod build is complete.")


def main() -> None:  # pragma: no cover
    env = os.environ.copy()
    env["PATH"] = str(paths.JAVA_HOME_DIR / "bin") + os.pathsep + env.get("PATH", "")
    env["JAVA_HOME"] = str(paths.JAVA_HOME_DIR)

    app(
        obj=Config(
            command_runner=_run_command,
            message_writer=typer.echo,
            working_dir=paths.ROOT_DIR,
            desktop_jar=paths.DESKTOP_JAR,
            mod_the_spire_jar=paths.MOD_THE_SPIRE_JAR,
            base_mod_jar=paths.BASE_MOD_JAR,
            build_jar=paths.BUILD_JAR,
            communication_mod_jar=paths.COMMUNICATION_MOD_JAR,
            communication_mod_dir=paths.COMMUNICATION_MOD_DIR,
            env=env,
        )
    )
