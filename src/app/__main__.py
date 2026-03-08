import logging
import signal
import sys
import threading
from logging import Logger
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Thread

PROJECT_DIR: Path = Path().resolve()
LOG_DIR: Path = PROJECT_DIR / "logs"
LOG_PATH: Path = LOG_DIR / "app.log"

app_logger: Logger = logging.getLogger("app")
input_logger: Logger = logging.getLogger("input")
stop_event = threading.Event()


def handle_signal(signum, *_) -> None:
    if stop_event.is_set():
        return

    app_logger.info(f"Received signal {signum}.")
    stop_event.set()


signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)


def check_project_dir() -> None:
    if not (PROJECT_DIR / "pyproject.toml").exists():
        raise RuntimeError("Not in project directory")


def init_logger() -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    LOG_DIR.mkdir(exist_ok=True, parents=True)

    handler = RotatingFileHandler(
        LOG_PATH,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)


def stdin_main() -> None:
    app_logger.info("Input thread started.")

    for line in sys.stdin:
        input_logger.info(line)

    app_logger.info("Input thread exited.")
    stop_event.set()


def send_command(command: str) -> None:
    print(command, flush=True)


def main() -> None:
    check_project_dir()
    init_logger()

    app_logger.info("App started.")
    Thread(target=stdin_main, daemon=True).start()
    send_command("ready")

    while not stop_event.is_set():
        pass

    app_logger.info("App exited.")


if __name__ == "__main__":
    main()
