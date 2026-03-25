import json

from bridge.common import Message


def test_message_defaults() -> None:
    message = Message()

    assert message.command_id is None
    assert message.ready_for_command is False
    assert message.error is None
    assert message.available_commands is None
    assert message.in_game is None
    assert message.game_state is None


def test_message_model_validate_json_preserves_payload() -> None:
    payload = {
        "command_id": "42",
        "ready_for_command": True,
        "error": "invalid command",
        "available_commands": ["play", "end"],
        "in_game": True,
        "game_state": {"floor": 7, "hp": 63},
    }

    message = Message.model_validate_json(json.dumps(payload))

    assert message.model_dump() == payload
