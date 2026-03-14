import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Body, Depends, FastAPI, Request, Response

from bridge.communication import Orchestrator

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    orchestrator = Orchestrator()
    await orchestrator.communicate("ready")
    app.state.orchestrator = orchestrator
    yield
    orchestrator.close()


def get_orchestrator(request: Request) -> Orchestrator:
    return request.app.state.orchestrator


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health() -> str:
    return "ok"


@app.post("/communicate")
async def communicate(
    command: Annotated[str, Body(media_type="text/plain")],
    orchestrator: Annotated[Orchestrator, Depends(get_orchestrator)],
) -> Response:
    message = await orchestrator.communicate(command)
    return Response(content=message, media_type="application/json")
