import os
import subprocess
from pathlib import Path

from rich.console import Console

console = Console()

repo_root = Path(__file__).parents[5]
work_dir = repo_root / ".work"
steamapps_dir = Path.home() / "Library" / "Application Support" / "Steam" / "steamapps"
resources_dir = (
    steamapps_dir
    / "common"
    / "SlayTheSpire"
    / "SlayTheSpire.app"
    / "Contents"
    / "Resources"
)
desktop_jar_path = resources_dir / "desktop-1.0.jar"
mods_dir = resources_dir / "mods"
communication_mod_jar_path = mods_dir / "CommunicationMod.jar"
workshop_dir = steamapps_dir / "workshop" / "content" / "646570"
mod_the_spire_jar_path = workshop_dir / "1605060445" / "ModTheSpire.jar"
base_mod_jar_path = workshop_dir / "1605833019" / "BaseMod.jar"
build_jar_path = work_dir / "CommunicationMod.jar"
communication_mod_dir = repo_root / "external" / "CommunicationMod"
java_home = Path.home() / ".sdkman" / "candidates" / "java" / "8.0.482-zulu"


def run() -> None:
    console.print("Building and linking mod...", style="bold green")
    if not (repo_root / ".python-version").exists():
        msg = f"Could not find .python-version file in repo root at {repo_root}"
        raise FileNotFoundError(msg)

    work_dir.mkdir(exist_ok=True)

    env = os.environ.copy()
    env["JAVA_HOME"] = str(java_home)
    java_bin_dir = java_home / "bin"
    if env.get("PATH"):
        env["PATH"] = f"{java_bin_dir}{os.pathsep}{env['PATH']}"
    else:
        env["PATH"] = str(java_bin_dir)

    subprocess.run(
        [
            "mvn",
            f"-Dcommunicationmod.desktop.jar={desktop_jar_path}",
            f"-Dcommunicationmod.modthespire.jar={mod_the_spire_jar_path}",
            f"-Dcommunicationmod.basemod.jar={base_mod_jar_path}",
            f"-Dcommunicationmod.build.jar={build_jar_path}",
            "clean",
            "package",
        ],
        check=True,
        cwd=communication_mod_dir,
        env=env,
    )

    mods_dir.mkdir(exist_ok=True)
    if communication_mod_jar_path.exists():
        communication_mod_jar_path.unlink()
    communication_mod_jar_path.symlink_to(build_jar_path)
    console.print(
        f'Linked "{build_jar_path}" to "{communication_mod_jar_path}"',
        style="bold green",
    )

    console.print("Mod built and linked successfully!", style="bold green")
