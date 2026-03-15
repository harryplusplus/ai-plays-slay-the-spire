import asyncio
import io
import sys
from collections.abc import Iterator
from contextlib import contextmanager, redirect_stdout
from types import SimpleNamespace
from typing import Any, cast

import pytest
from bridge import api
from fastapi.testclient import TestClient

HTTP_OK = 200


@contextmanager
def _test_client() -> Iterator[tuple[TestClient, io.StringIO]]:
    original_stdin = sys.stdin
    stdout = io.StringIO()
    sys.stdin = io.StringIO("")

    try:
        with redirect_stdout(stdout), TestClient(api.app) as client:
            yield client, stdout
    finally:
        sys.stdin = original_stdin


def test_get_connection_manager_reads_app_state() -> None:
    manager = object()
    websocket = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(connection_manager=manager),
        ),
    )

    assert api.get_connection_manager(cast("Any", websocket)) is manager


def test_health_route_runs_lifespan_and_closes_connection_manager() -> None:
    with _test_client() as (client, stdout):
        response = client.get("/health")

    assert response.status_code == HTTP_OK
    assert response.json() == "ok"
    assert stdout.getvalue().splitlines() == ["ready"]

    with pytest.raises(RuntimeError, match=r"Connection manager is closed\."):
        asyncio.run(api.app.state.connection_manager.broadcast("after"))


def test_websocket_route_forwards_commands_to_stdout() -> None:
    with (
        _test_client() as (client, stdout),
        client.websocket_connect("/ws") as websocket,
    ):
        websocket.send_text("play")

    assert stdout.getvalue().splitlines() == ["ready", "play"]
