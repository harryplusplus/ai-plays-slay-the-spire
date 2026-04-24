# pyright: reportArgumentType=none, reportUnknownArgumentType=none, reportUnknownMemberType=none, reportUnknownVariableType=none
import json
import logging
import os
import subprocess
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, override

import httpx
from openai import OpenAI

logger = logging.getLogger(__name__)

OLLAMA_API_KEY = os.environ["OLLAMA_API_KEY"]
MODEL = "gpt-4o-mini"

BANK_ID = "sts"
PROXY_URL = "http://127.0.0.1:8766/command"
TIMEOUT = 30.0

SYSTEM_PROMPT = """You are an AI playing Slay the Spire.

Available tools:
- send_command: Send a command to the game
  (start, play, end, choose, potion, key, click, wait, state, proceed, return)
- recall: Search your memory for relevant game knowledge
- retain: Store an observation or lesson in your memory for future reference

Guidelines:
- After each state update, analyze the situation carefully before acting.
- Use recall proactively to check relevant knowledge before important decisions.
- Use retain frequently to store observations worth remembering:
  - After combat: what worked, what didn't
  - After events: outcomes of choices
  - When discovering card synergies or relic interactions
  - Boss patterns and strategies
- Be decisive. Don't ask for clarification — make the best choice you can.
- Prefer safe plays when uncertain."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "send_command",
            "description": "Send a command to the game and receive the updated state.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": (
                            "Game command "
                            "(e.g. 'start DEFECT 0', 'play 1', "
                            "'end', 'choose 0', 'state')"
                        ),
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall",
            "description": "Search your memory for relevant game knowledge.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Search query "
                            "(e.g. 'jaw worm strategy', 'relic priority')"
                        ),
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "retain",
            "description": (
                "Store an observation or lesson in memory for future reference."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The observation or lesson to remember",
                    },
                },
                "required": ["content"],
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


def send_command(cmd: str) -> dict[str, Any]:
    response = httpx.post(PROXY_URL, content=cmd, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def recall(query: str) -> str:
    result = subprocess.run(
        ["hindsight", "memory", "recall", BANK_ID, query, "--output", "json"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def retain(content: str) -> str:
    result = subprocess.run(
        [
            "hindsight",
            "memory",
            "retain",
            BANK_ID,
            content,
            "--output",
            "json",
            "--context",
            "Slay the Spire gameplay",
            "--async",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


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
    return recall(query)


def execute_tool(name: str, arguments: dict[str, Any]) -> str:
    if name == "send_command":
        result = send_command(arguments["command"])
        return json.dumps(result)
    if name == "recall":
        return recall(arguments["query"])
    if name == "retain":
        return retain(arguments["content"])
    msg = f"unknown tool: {name}"
    raise ValueError(msg)


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
    state = send_command("state")
    auto_recall_result = auto_recall(state)
    messages.append(
        {
            "role": "user",
            "content": (
                f"Current game state:\n"
                f"{json.dumps(state, indent=2)}\n\n"
                f"Relevant memories:\n{auto_recall_result}"
            ),
        },
    )
    logger.info("initial state: %s", json.dumps(state, indent=2))

    while True:
        response = client.chat.completions.create(  # pyright: ignore[reportArgumentType]
            model=MODEL,
            messages=messages,
            tools=TOOLS,
        )

        choice = response.choices[0]
        assistant_msg = choice.message

        messages.append(assistant_msg.to_dict())

        if assistant_msg.tool_calls:
            for tool_call in assistant_msg.tool_calls:
                fn_name: str = tool_call.function.name  # type: ignore[union-attr]
                fn_args = json.loads(tool_call.function.arguments)  # type: ignore[union-attr]
                logger.info("tool call: %s(%s)", fn_name, fn_args)

                result = execute_tool(fn_name, fn_args)
                logger.info("tool result: %s", result[:500])

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    },
                )

                # Auto recall after game command
                if fn_name == "send_command":
                    try:
                        new_state = json.loads(result)
                        auto_recall_result = auto_recall(new_state)
                        messages.append(
                            {
                                "role": "user",
                                "content": (
                                f"Updated state:\n"
                                f"{json.dumps(new_state, indent=2)}\n\n"
                                f"Relevant memories:\n{auto_recall_result}"
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
            # No tool call — shouldn't happen in this loop, but log it
            logger.warning("no tool call in response: %s", assistant_msg.content)
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "You must use a tool. "
                        "Call send_command, recall, or retain."
                    ),
                },
            )


if __name__ == "__main__":
    main()
