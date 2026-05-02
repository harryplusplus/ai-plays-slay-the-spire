"""AI agent constants and configuration."""

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionToolUnionParam

OPENAI_BASE_URL = "https://crof.ai/v1"
OPENAI_API_KEY = os.environ["CROF_API_KEY"]
MODEL = "glm-5.1-precision"
REASONING_EFFORT = "high"
MAX_MESSAGES_CHARS = 500_000
RETRY_DELAY = 10.0
MAX_ATTEMPTS = 5
RUN_LOG = Path.home() / ".sts" / "logs" / "runs.log"
LLM_DUMP_DIR = Path.home() / ".sts" / "logs" / "llm_dump"
MAX_DUMPS = 10
REASONING_LOG = Path.home() / ".sts" / "logs" / "reasoning.jsonl"

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

State awareness:
- The game state includes your relics and potions. Check them every turn.
- In combat, check draw_pile and discard_pile to anticipate upcoming draws
  and know what's available for recursion (e.g., Headbutt, Hologram).
- Use the deck tool to see your full deck when planning builds.
- Use the map tool at path choice screens to plan your route.

Guidelines:
- After each state update, analyze carefully before acting.
- Be decisive. Don't ask for clarification.
- Prefer safe plays when uncertain."""

TOOLS: list[ChatCompletionToolUnionParam] = [
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
            "name": "deck",
            "description": "Show the current deck.",
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

RUN_ENDED_PROMPT = "The run has ended (in_game=false). Start a new game."
