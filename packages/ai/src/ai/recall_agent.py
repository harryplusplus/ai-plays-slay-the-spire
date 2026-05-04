"""Recall agent — mini agent loop with only the recall tool."""

import json
import logging
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openai.types.chat import (
        ChatCompletionFunctionToolParam,
        ChatCompletionMessageParam,
    )


from .constants import MODEL, REASONING_EFFORT, RECALL_MAX_TOKENS
from .llm import (
    build_multimodal_content,
    call_llm,
    parse_llm_response,
)

logger = logging.getLogger(__name__)

RECALL_AGENT_PROMPT = """\
You are a Recall agent for Slay the Spire. Your ONLY tool is recall.

Read the game state carefully, then use recall to search memory for
relevant past experiences, strategies, and lessons that could help
the current situation.

Use recall with targeted queries. You may call recall multiple times
with different queries to cover different aspects of the situation.

IMPORTANT: You MUST call the recall tool. Do NOT respond with analysis
text. Only use the recall tool to gather information."""

RECALL_TOOL: ChatCompletionFunctionToolParam = {
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
}


def _execute_recall(query_json: str) -> str:
    """Execute a recall via the game CLI."""
    result = subprocess.run(
        ["uv", "run", "game", "recall", query_json],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return result.stdout


NUDGE_MESSAGES = [
    "\n\nYou did not call the recall tool. Use it now.",
    "\n\nYou STILL did not call recall. Call recall() now.",
    "\n\nFinal attempt. You WILL call recall() immediately.",
]


def run_recall_agent(
    messages: list[ChatCompletionMessageParam],
    current_state_json: str,
    screenshot_b64: str,
    model: str = MODEL,
    reasoning_effort: str = REASONING_EFFORT,
    max_attempts: int = 10,
) -> str:
    """Run recall with retry. Returns raw recall results or ""."""
    for attempt in range(1, max_attempts + 1):
        nudge = (
            ""
            if attempt == 1
            else NUDGE_MESSAGES[min(attempt - 2, len(NUDGE_MESSAGES) - 1)]
        )
        prompt: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": RECALL_AGENT_PROMPT},
            *messages,
            {
                "role": "user",
                "content": build_multimodal_content(
                    f"Game state:\n```json\n{current_state_json}\n```\n\n"
                    "Search memory for relevant past experiences and strategies."
                    + nudge,
                    screenshot_b64,
                ),
            },
        ]

        response = call_llm(
            prompt,
            [RECALL_TOOL],
            model,
            reasoning_effort,
            caller="recall",
            max_tokens=RECALL_MAX_TOKENS,
        )
        parsed = parse_llm_response(response)

        if parsed.tool_calls:
            results: list[str] = []
            for tc in parsed.tool_calls:
                fn_args = json.loads(tc.function.arguments)
                query = fn_args.get("query", "")
                logger.info(
                    "recall query",
                    extra={"event": "recall_query", "query": query},
                )
                result = _execute_recall(query)
                results.append(f"--- Query: {query} ---\n{result}")
            return "\n\n".join(results)

        logger.warning(
            "recall: no tool calls, retry %d/%d",
            attempt,
            max_attempts,
            extra={"event": "recall_no_tool_calls", "attempt": attempt},
        )

    logger.warning(
        "recall exhausted all attempts",
        extra={"event": "recall_exhausted", "max_attempts": max_attempts},
    )
    return ""
