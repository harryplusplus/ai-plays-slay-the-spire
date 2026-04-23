import typer

app = typer.Typer(no_args_is_help=True)


@app.command("state")
def run_state() -> None:
    pass


def main() -> None:
    app()


if __name__ == "__main__":
    main()
