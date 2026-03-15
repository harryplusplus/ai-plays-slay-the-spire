import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, WebSocket

from bridge.command import ThreadedSender
from bridge.connection import ConnectionManager
from bridge.message import (
    ThreadedReceiver,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    sender = ThreadedSender()
    connection_manager = ConnectionManager(sender)
    app.state.connection_manager = connection_manager
    receiver = ThreadedReceiver(connection_manager)
    receiver.start()
    await sender.send("ready")

    yield

    await connection_manager.close()
    sender.close()


def get_connection_manager(websocket: WebSocket) -> ConnectionManager:
    return websocket.app.state.connection_manager


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health() -> str:
    return "ok"


@app.websocket("/ws")
async def on_connect(
    websocket: WebSocket,
    connection_manager: Annotated[ConnectionManager, Depends(get_connection_manager)],
) -> None:
    await connection_manager.on_connect(websocket)
