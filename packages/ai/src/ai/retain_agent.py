"""Retain agent — generates strategic retain content from conversation history."""

import logging
from typing import TYPE_CHECKING

from .constants import MODEL, REASONING_EFFORT
from .llm import build_multimodal_content, call_llm

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionMessageParam

logger = logging.getLogger(__name__)

RETAIN_AGENT_PROMPT = """\
You are a Retain agent for Slay the Spire. Your job is to write a concise
strategic memory based on what just happened in the game.

Read the conversation history to understand the situation, then output
a single paragraph of retain content. Focus on:

- Strategic decisions and their rationale
- Enemy patterns and counter-strategies
- Build direction and card synergies
- Lessons learned (what worked, what didn't)
- Key tradeoffs (why X over Y)

Do NOT include:
- Raw HP, energy, or block numbers
- Turn-by-turn play descriptions
- Generic statements like "played cards and won"

Output ONLY the retain content — no preamble, no formatting."""

TRIGGER_PROMPTS: dict[str, str] = {
    "combat_end": (
        "A combat just ended. Summarize the overall strategy used, "
        "what worked well, and what could be improved."
    ),
    "event": (
        "An event choice was just made. Explain why this choice was made "
        "and what was gained or lost."
    ),
    "shop": (
        "A shop visit just concluded. Describe what was bought (or why "
        "nothing was bought), what was skipped, and the reasoning."
    ),
    "campfire": (
        "A campfire action was just taken. Explain what was upgraded "
        "(or why rest was chosen) and how it fits the build."
    ),
    "chest": (
        "A chest was just opened. Describe the relic obtained and how "
        "it synergizes with the current build."
    ),
    "card_pick": (
        "A card reward was just chosen. Explain why this card was picked "
        "over the alternatives and how it fits the deck."
    ),
    "run_end": (
        "The run just ended. Summarize the overall outcome: what killed "
        "you (or how you won), what build decisions defined the run, "
        "and the key lesson to remember."
    ),
}


def run_retain_agent(
    messages: list[ChatCompletionMessageParam],
    trigger: str,
    screenshot_b64: str,
    model: str = MODEL,
    reasoning_effort: str = REASONING_EFFORT,
) -> str:
    """Generate retain content from conversation history.

    Args:
        messages: Recent conversation history.
        trigger: What triggered the retain (turn_end, combat_end, etc.).
        screenshot_b64: Base64-encoded PNG screenshot of the result screen.
        model: LLM model name.
        reasoning_effort: Reasoning effort level.

    Returns:
        Retain content string.
    """
    trigger_prompt = TRIGGER_PROMPTS.get(trigger, "")
    prompt: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": RETAIN_AGENT_PROMPT},
        *messages,
        {
            "role": "user",
            "content": build_multimodal_content(trigger_prompt, screenshot_b64),
        },
    ]

    response = call_llm(prompt, [], model, reasoning_effort, caller="retain")
    return response.choices[0].message.content or ""
