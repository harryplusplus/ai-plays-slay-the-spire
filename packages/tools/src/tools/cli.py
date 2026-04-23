import typer

from .commands import git_submodules, mod

app = typer.Typer(no_args_is_help=True)


@app.command("git-submodules")
def run_git_submodules() -> None:
    git_submodules.run()


@app.command("mod")
def run_mod() -> None:
    mod.run()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
