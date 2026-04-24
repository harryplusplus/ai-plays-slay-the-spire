# pyright: reportUnknownVariableType=none
"""AI agent constants and configuration."""

import os
from pathlib import Path
from typing import Any

OPENAI_BASE_URL = "https://ollama.com/v1"
OPENAI_API_KEY = os.environ["OLLAMA_API_KEY"]
MODEL = "deepseek-v4-flash:cloud"
MAX_OUTPUT = 20_000
MAX_MESSAGES_CHARS = 1_000_000
RETRY_DELAY = 10.0
RUN_LOG = Path.home() / ".sts" / "logs" / "runs.log"
LLM_DUMP_DIR = Path.home() / ".sts" / "logs" / "llm_dump"
MAX_DUMPS = 10

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
- You MUST retain when a meaningful event concludes: after
  ending your turn (END), after finishing a combat, after making
  an event or shop choice, or after acquiring a card/relic/potion.
  Do NOT retain after individual card plays, potion uses, or
  STATE commands.
- When retaining, focus on strategic decisions, lessons learned,
  and new patterns discovered. Do NOT list raw state changes
  like HP, energy, or block numbers.
- When a run ends (in_game=false), retain the outcome summary \
  then start a new game.
- Be decisive. Don't ask for clarification.
- Prefer safe plays when uncertain."""

TOOLS: list[dict[str, Any]] = [
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
            "description": (
                "Store a strategic lesson or key decision. "
                "Only after turn end, combat end, event/shop choice, "
                "or card/relic acquisition. "
                "NEVER after individual card plays or STATE. "
                "Describe WHY and WHAT was learned, not raw numbers."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": (
                            "Strategic lesson or decision rationale. "
                            "Focus: build direction, enemy patterns, "
                            "card synergies, why a choice was made, "
                            "what to remember later. "
                            "Avoid HP/energy/block or play-by-play."
                        ),
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

RUN_ENDED_PROMPT = (
    "The run has ended (in_game=false). "
    "Check if you defeated the Heart "
    "or died. retain a summary of "
    "this run's outcome, then start "
    "a new game."
)

TURN_ENDED_PROMPT = (
    "\n\nYou have ended your turn. "
    "You MUST call retain NOW with a strategic summary. "
    "Format:\n"
    "- Situation: [enemy/room and key patterns]\n"
    "- Decision: [what you did and why]\n"
    "- Outcome: [what worked, 1-2 sentences]\n"
    "- Lesson: [remember for next time]\n"
    "NEVER include raw HP/energy/block numbers."
)
