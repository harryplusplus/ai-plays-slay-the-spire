from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, WebSocket
from starlette.datastructures import State

from bridge.connection import WebSocketConnection
from bridge.service import ServiceRegistry, ServiceRegistryImpl

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
) -> None:
    state_accessor = _StateAccessor(websocket.app.state)
    await (
        state_accessor.get_service_registry()
        .connection_manager_service()
        .on_connection(WebSocketConnection(websocket))
    )


class _StateAccessor:
    def __init__(self, state: State) -> None:
        self._state = state

    def set_service_registry(self, service_registry: ServiceRegistry) -> None:
        self._state.service_registry = service_registry

    def get_service_registry(self) -> ServiceRegistry:
        return self._state.service_registry


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    service_registry = _StateAccessor(app.state).get_service_registry()
    await service_registry.start()
    yield
    await service_registry.close()


class AppFactory:
    def __init__(
        self,
        service_registry: ServiceRegistry | None = None,
    ) -> None:
        self._service_registry = (
            service_registry if service_registry is not None else ServiceRegistryImpl()
        )

    def __call__(
        self,
    ) -> FastAPI:
        app = FastAPI(
            lifespan=_lifespan,
        )
        _StateAccessor(app.state).set_service_registry(self._service_registry)
        app.include_router(router)

        return app
