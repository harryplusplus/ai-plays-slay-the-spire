from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, WebSocket

from bridge import command, connection, message

SenderServiceFactory = Callable[[], command.SenderService]
ConnectionManagerFactory = Callable[[command.Sender], connection.Manager]
ReceiverServiceFactory = Callable[[message.Handler], message.ReceiverService]
LifespanFactory = Callable[[FastAPI], AbstractAsyncContextManager[None]]


@dataclass(frozen=True)
class RuntimeFactories:
    command_sender: SenderServiceFactory = command.ThreadedSenderService
    connection_manager: ConnectionManagerFactory = connection.Manager
    message_receiver: ReceiverServiceFactory = message.ThreadedReceiverService


router = APIRouter()


def get_connection_manager(websocket: WebSocket) -> connection.Manager:
    return websocket.app.state.connection_manager


def _create_lifespan(factories: RuntimeFactories) -> LifespanFactory:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        command_sender = factories.command_sender()
        connection_manager = factories.connection_manager(command_sender.sender())
        app.state.connection_manager = connection_manager
        message_receiver = factories.message_receiver(
            connection_manager.message_handler(),
        )
        message_receiver.start()
        await command_sender.sender()("ready")

        yield

        await connection_manager.close()
        command_sender.close()

    return lifespan


def create_app(
    *,
    factories: RuntimeFactories | None = None,
) -> FastAPI:
    resolved_factories = factories if factories is not None else RuntimeFactories()
    app = FastAPI(
        lifespan=_create_lifespan(resolved_factories),
    )
    app.include_router(router)
    return app


@router.get("/health")
async def health() -> str:
    return "ok"


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    connection_manager: Annotated[connection.Manager, Depends(get_connection_manager)],
) -> None:
    await connection_manager.on_websocket(websocket)


app = create_app()
