from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import APIRouter, FastAPI, Request
from pydantic import BaseModel, ConfigDict

from bridge.common import Message
from bridge.container import Container


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    container = get_container(app)
    try:
        await container.init()
        yield
    finally:
        await container.close()


def create_app(container: Container) -> FastAPI:
    app = FastAPI(lifespan=_lifespan)
    app.state.container = container
    app.include_router(router)
    return app


def get_container(app: FastAPI) -> Container:
    return app.state.container


router = APIRouter()


class ExecuteDto(BaseModel):
    command: str


@router.post("/execute")
async def execute(request: Request, dto: ExecuteDto) -> Message:
    return await get_container(request.app).execution_service.execute(dto.command)


class EventDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    data: str
    created_at: datetime
    updated_at: datetime


@router.get("/events")
async def events(request: Request, limit: int = 3) -> list[EventDto]:
    items = await get_container(request.app).event_service.list_recent_events(
        limit=limit
    )
    return [EventDto.model_validate(item) for item in items]
