import threading
from typing import Annotated

import uvicorn
from fastapi import Depends, FastAPI, Request
from pydantic import BaseModel

from bridge import command, message

app = FastAPI()


def get_message_accessor(request: Request) -> message.Accessor:
    return request.app.state.message_accessor


def get_command_writer(request: Request) -> command.Writer:
    return request.app.state.command_writer


@app.get("/health")
async def health() -> None:
    pass


@app.get("/messages")
async def get_messages(
    message_accessor: Annotated[message.Accessor, Depends(get_message_accessor)],
) -> list[message.Message]:
    return message_accessor.get_all()


class WriteCommand(BaseModel):
    command: str


@app.post("/command")
async def write_command(
    command_writer: Annotated[command.Writer, Depends(get_command_writer)],
    write_command: WriteCommand,
) -> None:
    await command_writer.write(write_command.command)


def _main(server: uvicorn.Server) -> None:
    server.run()


class ThreadRunner:
    def __init__(
        self,
        message_accessor: message.Accessor,
        command_writer: command.Writer,
    ) -> None:
        app.state.message_accessor = message_accessor
        app.state.command_writer = command_writer

        config = uvicorn.Config(app, access_log=False, log_config=None)
        self._server = uvicorn.Server(config)

        self._thread = threading.Thread(
            name="api_thread",
            target=_main,
            args=(self._server,),
        )
        self._running = False
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self._running:
                raise RuntimeError(
                    "API runner is already running.",
                )

            self._thread.start()
            self._running = True

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                raise RuntimeError(
                    "API runner is not running.",
                )

            self._server.should_exit = True
            self._running = False

        self._thread.join()
