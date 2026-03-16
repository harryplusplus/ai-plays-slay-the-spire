from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, WebSocket

from bridge.service import ServiceRegistry, ServiceRegistryImpl

router = APIRouter()


def _set_service_registry(
    app: FastAPI,
    service_registry: ServiceRegistry,
) -> None:
    app.state.service_registry = service_registry


def _get_service_registry(app: FastAPI) -> ServiceRegistry:
    return app.state.service_registry


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
) -> None:
    await (
        _get_service_registry(websocket.app)
        .connection_manager_service()
        .on_websocket(websocket)
    )


def create_app(
    *,
    service_registry: ServiceRegistry | None = None,
) -> FastAPI:
    if service_registry is None:
        service_registry = ServiceRegistryImpl()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        _set_service_registry(app, service_registry)
        await service_registry.start()
        yield
        await service_registry.close()

    app = FastAPI(
        lifespan=lifespan,
    )
    app.include_router(router)

    return app
