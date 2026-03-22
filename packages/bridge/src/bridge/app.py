import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from pydantic import BaseModel

from bridge.container import Container


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with Container.get(app):
        yield


app = FastAPI(lifespan=_lifespan)


class ExecuteDto(BaseModel):
    command: str


@app.post("/execute")
async def execute(dto: ExecuteDto, request: Request) -> Response:
    _container = Container.get(request.app)
    res = {"command": dto.command}
    return Response(content=json.dumps(res), media_type="application/json")
