import subprocess

from rich.console import Console

console = Console()


def run() -> None:
    console.print("Updating git submodules...", style="bold green")

    subprocess.run(["git", "submodule", "update", "--init", "--recursive"], check=True)

    console.print("Git submodules updated successfully!", style="bold green")
