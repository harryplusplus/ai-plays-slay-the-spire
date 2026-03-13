import logging
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request, Response
from pydantic import BaseModel

if TYPE_CHECKING:
    from bridge.bridge import Bridge

logger = logging.getLogger(__name__)

app = FastAPI()


@app.get("/health")
async def health() -> str:
    return "ok"


class Execute(BaseModel):
    command: str


@app.post("/execute")
async def execute(
    dto: Execute,
    req: Request,
) -> Response:
    app: FastAPI = req.app
    bridge: Bridge = app.state.bridge
    message = await bridge.execute(dto.command)
    return Response(content=message, media_type="application/json")
