"""AI agent constants and configuration."""

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionToolUnionParam

OPENAI_BASE_URL = "https://crof.ai/v1"
OPENAI_API_KEY = os.environ["CROF_API_KEY"]
MODEL = "kimi-k2.6-precision"
REASONING_EFFORT = "high"
MAX_MESSAGES_CHARS = 500_000
RETRY_DELAY = 10.0
MAX_ATTEMPTS = 5
RUN_LOG = Path.home() / ".sts" / "logs" / "runs.log"
LLM_DUMP_DIR = Path.home() / ".sts" / "logs" / "llm_dump"
MAX_DUMPS = 10
REASONING_LOG = Path.home() / ".sts" / "logs" / "reasoning.jsonl"

PLAY_AGENT_PROMPT = """\
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
- WAIT <Timeout>
  Wait for frames or until state change.
- STATE
  Get current state immediately. Always available.

State awareness:
- The game state includes your full deck, relics, potions, and map.
  Check them every turn.
- In combat, check draw_pile and discard_pile to anticipate upcoming draws
  and know what's available for recursion (e.g., Headbutt, Hologram).

Command selection:
- The state JSON includes an "available_commands" array. Use ONLY those
  commands. If a command fails, check available_commands again — the
  available set changes with each screen transition.
- Do NOT guess or reuse commands from earlier screens.
- Consecutive errors mean you are using the wrong command set. Pause,
  send STATE, and read available_commands from the fresh response.

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
]

RUN_ENDED_PROMPT = "The run has ended (in_game=false). Start a new game."
