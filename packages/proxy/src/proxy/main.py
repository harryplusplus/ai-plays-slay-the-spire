import asyncio
import logging
import signal
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import override

import uvicorn
from fastapi import FastAPI


class _Formatter(logging.Formatter):
    @override
    def formatTime(
        self,
        record: logging.LogRecord,
        datefmt: str | None = None,
    ) -> str:
        return (
            datetime.fromtimestamp(record.created)
            .astimezone()
            .isoformat(timespec="milliseconds")
        )


logger = logging.getLogger(__name__)

app = FastAPI()


async def _run(server: uvicorn.Server) -> None:
    await server.serve()


def main() -> None:
    handler = RotatingFileHandler(
        Path.home() / ".sts" / "logs" / "proxy.log",
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(
        _Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"),
    )

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)

    logger.info("started.")
    with asyncio.Runner() as runner:
        loop = runner.get_loop()
        config = uvicorn.Config(app, host="127.0.0.1", port=8766, log_config=None)
        server = uvicorn.Server(config)

        def _shutdown() -> None:
            server.should_exit = True

        loop.add_signal_handler(signal.SIGINT, _shutdown)
        loop.add_signal_handler(signal.SIGTERM, _shutdown)

        runner.run(_run(server))
    logger.info("stopped.")


if __name__ == "__main__":
    main()
