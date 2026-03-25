from typing import Any

from pydantic import BaseModel


class Message(BaseModel):
    command_id: str | None = None
    ready_for_command: bool = False

    # error
    error: str | None = None

    # result
    available_commands: list[str] | None = None
    in_game: bool | None = None
    game_state: dict[str, Any] | None = None
