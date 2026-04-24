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
MAX_MESSAGES_CHARS = 400_000
RETRY_DELAY = 10.0
RUN_LOG = Path.home() / ".sts" / "logs" / "runs.log"

SYSTEM_PROMPT = """\
You are an AI playing Slay the Spire.

Game commands (case insensitive):
- START <Class> [Ascension] [Seed]
  Start a new run. Class: IRONCLAD, SILENT, DEFECT, WATCHER.
  Ascension: 0-20 (default 0). Seed: alphanumeric (optional).
  Only available in main menu.
- PLAY <CardIndex> [TargetIndex]
  Play a card from hand. CardIndex is 1-indexed.
  TargetIndex: monster array index (0-indexed), if card has target.
  Only available in combat.
- END
  End your turn. Only available in combat.
- CHOOSE <ChoiceIndex|ChoiceName>
  Make a choice on the current screen. Choice names are in game state.
  Available when PLAY is not available.
- POTION <Use|Discard> <SlotIndex> [TargetIndex]
  Use or discard a potion. SlotIndex: 0-indexed.
  TargetIndex: monster array index, if potion requires target.
- PROCEED
  Click right-side button (proceed/confirm). Equivalent to CONFIRM.
- RETURN
  Click left-side button (return/cancel/leave/skip).
- KEY <Keyname> [Timeout]
  Press a key. Keynames: Confirm, Cancel, Map, Deck, Draw_Pile,
  Discard_Pile, Exhaust_Pile, End_Turn, Up, Down, Left, Right,
  Drop_Card, Card_1..Card_10. Timeout: frames to wait (default 100).
- CLICK <Left|Right> <X> <Y>
  Click at coordinates. (0,0)=top-left, (1920,1080)=bottom-right.
- WAIT <Timeout>
  Wait for frames or until state change.
- STATE
  Get current state immediately. Always available.

Guidelines:
- After each state update, analyze carefully before acting.
- Use recall proactively before important decisions.
- Use retain frequently: after combat, events, card synergies, \
  boss patterns.
- When a run ends (in_game=false), retain the outcome summary \
  then start a new game.
- Be decisive. Don't ask for clarification.
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
                        "description": "Game command to execute",
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
            "description": "Search memory for relevant game knowledge.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
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
            "description": "Store an observation in memory for future reference.",
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
    {
        "type": "function",
        "function": {
            "name": "deck",
            "description": "Show the current deck.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "relics",
            "description": "Show the current relics.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "potions",
            "description": "Show the current potions.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "map",
            "description": "Show the current map.",
            "parameters": {"type": "object", "properties": {}},
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
        maxBytes=10_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(
        Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"),
    )

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)

    # Our logger at DEBUG for detailed output
    logging.getLogger("ai").setLevel(logging.DEBUG)


def game_cli(*args: str) -> str:
    try:
        result = subprocess.run(
            ["uv", "run", "game", *args],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        output = result.stdout
        if result.returncode != 0:
            output += result.stderr
    except subprocess.TimeoutExpired:
        output = "error: command timed out"
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
    return game_cli("recall", query)


def execute_tool(name: str, arguments: dict[str, Any]) -> str:  # noqa: PLR0911
    if name == "send_command":
        return game_cli("command", arguments["command"])
    if name == "recall":
        return game_cli("recall", arguments["query"])
    if name == "retain":
        return game_cli("retain", arguments["content"])
    if name == "deck":
        return game_cli("deck")
    if name == "relics":
        return game_cli("relics")
    if name == "potions":
        return game_cli("potions")
    if name == "map":
        return game_cli("map")
    return f"error: unknown tool {name}"


def trim_messages(messages: list[dict[str, Any]]) -> None:
    """Drop oldest complete turns until total chars under limit.

A turn is: user + assistant + tool(s). We remove whole turns
so tool_call/tool_result pairs stay intact.
"""
    while True:
        total = sum(
            len(str(m.get("content", "")))
            for m in messages
        )
        if total <= MAX_MESSAGES_CHARS or len(messages) <= 1:
            break

        # Find the end of the first complete turn after system
        # Turn boundary: a user message that starts a new turn
        start = 1  # skip system message
        end = start
        while end < len(messages):
            if messages[end].get("role") == "user" and end > start:
                break
            end += 1

        if end <= start:
            break

        removed = messages[start:end]
        logger.info(
            "trimming %d messages (roles: %s)",
            len(removed),
            [m.get("role") for m in removed],
        )
        del messages[start:end]


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
    initial = game_cli("command", "state")
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
        logger.debug("messages count: %d", len(messages))

        try:
            response = client.chat.completions.create(  # pyright: ignore[reportArgumentType]
                model=MODEL,
                messages=messages,
                tools=TOOLS,
                temperature=0,
                reasoning_effort="high",
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
                        in_game = new_state.get("in_game", False)
                        if not in_game:
                            logger.info("RUN ENDED - in_game=false")
                            run_handler = RotatingFileHandler(
                                RUN_LOG,
                                maxBytes=10_000_000,
                                backupCount=5,
                                encoding="utf-8",
                            )
                            run_handler.emit(
                                logging.LogRecord(
                                    name="run",
                                    level=logging.INFO,
                                    pathname="",
                                    lineno=0,
                                    msg=result,
                                    args=(),
                                    exc_info=None,
                                ),
                            )
                            run_handler.close()
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
                    "content": "You must use a tool.",
                },
            )


if __name__ == "__main__":
    main()
