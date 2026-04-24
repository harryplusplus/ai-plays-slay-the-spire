# pyright: reportArgumentType=none, reportUnknownArgumentType=none, reportUnknownMemberType=none, reportUnknownVariableType=none
import json
import logging
import os
import subprocess
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, override

from openai import OpenAI

logger = logging.getLogger(__name__)

OLLAMA_API_KEY = os.environ["OLLAMA_API_KEY"]
MODEL = "glm-5.1"
MAX_OUTPUT = 20_000
MAX_MESSAGES_CHARS = 500_000
RETRY_DELAY = 10.0

SYSTEM_PROMPT = """\
You are an AI playing Slay the Spire. You have a bash shell.

Game CLI commands:
- uv run game command <cmd>  Send a game command, get filtered state JSON
- uv run game recall <query> Search memory for game knowledge
- uv run game retain <text>  Store an observation in memory
- uv run game deck           Show current deck
- uv run game relics         Show current relics
- uv run game potions        Show current potions
- uv run game map            Show current map

Game commands: start, play, end, choose, potion, key, click, wait, \
state, proceed, return

Use jq, python3, or any tool to process data before deciding.

Guidelines:
- After each state update, analyze carefully before acting.
- Use recall proactively before important decisions.
- Use retain frequently: after combat, events, card synergies, \
boss patterns.
- Be decisive. Don't ask for clarification.
- Prefer safe plays when uncertain."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Run a bash command.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Bash command to execute",
                    },
                },
                "required": ["command"],
            },
        },
    },
]


def init_logger() -> None:
    class Formatter(logging.Formatter):
        @override
        def formatTime(
            self,
            record: logging.LogRecord,
            datefmt: str | None = None,
        ) -> str:
            return (
                datetime.fromtimestamp(record.created)
                .astimezone()
                .isoformat(timespec="milliseconds")
            )

    handler = RotatingFileHandler(
        Path.home() / ".sts" / "logs" / "ai.log",
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(
        Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"),
    )

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)


def run_bash(command: str) -> str:
    result = subprocess.run(
        ["bash", "-c", command],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    output = result.stdout
    if result.returncode != 0:
        output += result.stderr
    if len(output) > MAX_OUTPUT:
        output = output[:MAX_OUTPUT] + f"\n... truncated ({len(output)} chars)"
    return output


def auto_recall(state: dict[str, Any]) -> str:
    """Build a recall query from current game state."""
    parts: list[str] = []
    game_state = state.get("game_state")
    if game_state:
        screen = game_state.get("screen_type", "")
        if screen:
            parts.append(screen)
        room = game_state.get("room_type", "")
        if room:
            parts.append(room)
        act = game_state.get("act")
        if act is not None:
            parts.append(f"act {act}")
        combat = game_state.get("combat_state")
        if combat:
            monsters = combat.get("monsters", [])
            parts.extend(m.get("name", "") for m in monsters[:3])
    query = " ".join(parts) if parts else "slay the spire general"
    logger.info("auto recall query: %s", query)
    return run_bash(f"uv run game recall '{query}'")


def trim_messages(messages: list[dict[str, Any]]) -> None:
    """Drop oldest non-system messages until total chars under limit."""
    while True:
        total = sum(
            len(str(m.get("content", "")))
            for m in messages
        )
        if total <= MAX_MESSAGES_CHARS or len(messages) <= 1:
            break
        # Remove the oldest non-system message
        for i, m in enumerate(messages):
            if m.get("role") != "system":
                logger.info(
                    "trimming message %d (role=%s, %d chars)",
                    i,
                    m.get("role"),
                    len(str(m.get("content", ""))),
                )
                del messages[i]
                break
        else:
            break


def main() -> None:
    init_logger()

    client = OpenAI(
        api_key=OLLAMA_API_KEY,
        base_url="https://ollama.com/v1",
    )

    messages: list[dict[str, Any]] = [  # type: ignore[type-arg]
        {"role": "system", "content": SYSTEM_PROMPT},
    ]

    # Initial state
    initial = run_bash("uv run game command state")
    auto_recall_result = auto_recall(json.loads(initial))
    messages.append(
        {
            "role": "user",
            "content": (
                f"Current game state:\n{initial}\n\n"
                f"Relevant memories:\n{auto_recall_result}"
            ),
        },
    )
    logger.info("initial state: %s", initial)

    while True:
        trim_messages(messages)

        try:
            response = client.chat.completions.create(  # pyright: ignore[reportArgumentType]
                model=MODEL,
                messages=messages,
                tools=TOOLS,
            )
        except Exception:
            logger.exception("LLM API call failed, retrying in %ss", RETRY_DELAY)
            time.sleep(RETRY_DELAY)
            continue

        choice = response.choices[0]
        assistant_msg = choice.message

        messages.append(assistant_msg.to_dict())

        if assistant_msg.tool_calls:
            for tool_call in assistant_msg.tool_calls:
                fn_name: str = tool_call.function.name  # type: ignore[union-attr]
                fn_args = json.loads(tool_call.function.arguments)  # type: ignore[union-attr]
                command = fn_args.get("command", "")
                logger.info("tool call: %s(%s)", fn_name, command)

                result = run_bash(command)
                logger.info("tool result: %s", result[:500])

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    },
                )

                # Auto recall after game command
                if "uv run game command" in command:
                    try:
                        new_state = json.loads(result)
                        in_game = new_state.get("in_game", False)
                        if not in_game:
                            logger.info("RUN ENDED - in_game=false")
                        auto_recall_result = auto_recall(new_state)
                        messages.append(
                            {
                                "role": "user",
                                "content": (
                                    f"Updated state:\n{result}\n\n"
                                    f"Relevant memories:\n{auto_recall_result}"
                                ),
                            },
                        )
                        if not in_game:
                            messages.append(
                                {
                                    "role": "user",
                                    "content": (
                                        "The run has ended (in_game=false). "
                                        "Check if you defeated the Heart "
                                        "or died. retain a summary of "
                                        "this run's outcome, then start "
                                        "a new game."
                                    ),
                                },
                            )
                    except json.JSONDecodeError:
                        messages.append(
                            {
                                "role": "user",
                                "content": f"Command result:\n{result}",
                            },
                        )
        else:
            logger.warning("no tool call in response: %s", assistant_msg.content)
            messages.append(
                {
                    "role": "user",
                    "content": "You must use the bash tool.",
                },
            )


if __name__ == "__main__":
    main()
