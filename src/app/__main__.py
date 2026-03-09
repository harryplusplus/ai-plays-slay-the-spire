import logging

from app import input_receiver, log
from app.input_receiver import Eof, InputQueue
from app.paths import PROJECT_FILE

logger = logging.getLogger(__name__)


def check_project_dir() -> None:
    if not PROJECT_FILE.exists():
        raise RuntimeError("Not in project directory")


def send(message: str) -> None:
    print(message, flush=True)


def main() -> None:
    check_project_dir()
    log.init()

    logger.info("started.")

    input_q = InputQueue()
    input_receiver_t = input_receiver.start_thread(input_q)

    send("ready")

    while True:
        input = input_q.get()
        if isinstance(input, Eof):
            break

        logger.debug(input)

    input_receiver_t.join()
    logger.info("exited.")


if __name__ == "__main__":
    main()
