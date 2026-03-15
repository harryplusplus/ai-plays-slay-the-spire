import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, WebSocket

from bridge import command, connection, message

logger = logging.getLogger(__name__)


def get_connection_manager(websocket: WebSocket) -> connection.Manager:
    return websocket.app.state.connection_manager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    command_sender = command.ThreadedSender()
    connection_manager = connection.Manager(command_sender.sender())
    app.state.connection_manager = connection_manager
    message_receiver = message.ThreadedReceiver(connection_manager.message_handler())
    message_receiver.start()
    await command_sender.sender()("ready")

    yield

    await connection_manager.close()
    command_sender.close()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health() -> str:
    return "ok"


@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    connection_manager: Annotated[connection.Manager, Depends(get_connection_manager)],
) -> None:
    await connection_manager.on_websocket(websocket)
