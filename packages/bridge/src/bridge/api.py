from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, WebSocket

from bridge import service

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
) -> None:
    registry: service.Registry = websocket.app.state.registry
    await registry.connection_manager().on_websocket(websocket)


def create_app(
    *,
    registry: service.Registry | None = None,
) -> FastAPI:
    if registry is None:
        registry = service.RegistryImpl()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.registry = registry
        await registry.start()
        yield
        await registry.close()

    app = FastAPI(
        lifespan=lifespan,
    )
    app.include_router(router)

    return app


app = create_app()
