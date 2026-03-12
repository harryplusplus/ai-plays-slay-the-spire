import asyncio
import logging
import threading
from dataclasses import dataclass, field
from typing import cast

import uvicorn
from fastapi import FastAPI, Request
from pydantic import BaseModel

from bridge.common import Command, CommandQueue, MessageQueue

logger = logging.getLogger(__name__)

app = FastAPI()


@app.get("/health")
async def health() -> str:
    return "ok"


class Execute(BaseModel):
    command: str


class ExecuteResponse(BaseModel):
    id: int
    message: str


@app.post("/execute")
async def execute(
    dto: Execute,
    req: Request,
) -> ExecuteResponse:
    app: FastAPI = req.app
    return await _execute(app, dto)


@dataclass(kw_only=True)
class Context:
    message_queue: MessageQueue
    command_queue: CommandQueue
    command_id: int = 0
    executing: bool = False
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


async def _execute(app: FastAPI, dto: Execute) -> ExecuteResponse:
    context: Context = app.state.context

    async with context.lock:
        if context.executing:
            raise RuntimeError("Command is already executing.")

        context.executing = True

    try:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[None] = loop.create_future()
        command_id = context.command_id
        context.command_id += 1

        context.command_queue.put_nowait(
            Command(id=command_id, command=dto.command, future=future),
        )
        await future

        message = await context.message_queue.get()
        if message.id != command_id:
            raise RuntimeError(
                f"Unexpected message id: {message.id} (expected: {command_id})",
            )

        return ExecuteResponse(id=message.id, message=message.message)
    finally:
        async with context.lock:
            context.executing = False


async def _run(server: uvicorn.Server) -> None:
    app = cast("FastAPI", server.config.app)
    await _execute(app, Execute(command="ready"))
    await server.serve()


def _main(loop: asyncio.AbstractEventLoop, server: uvicorn.Server) -> None:
    logger.info("Started.")

    asyncio.set_event_loop(loop)
    loop.run_until_complete(_run(server))

    logger.info("Exited.")


def create_thread(
    loop: asyncio.AbstractEventLoop,
    message_queue: MessageQueue,
    command_queue: CommandQueue,
) -> tuple[uvicorn.Server, threading.Thread]:
    app.state.context = Context(
        message_queue=message_queue,
        command_queue=command_queue,
    )

    config = uvicorn.Config(app, access_log=False, log_config=None)
    server = uvicorn.Server(config)
    thread = threading.Thread(name="api_thread", target=_main, args=(loop, server))

    return server, thread
