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


from .constants import MODEL, REASONING_EFFORT
from .llm import build_assistant_message, call_llm, parse_llm_response

logger = logging.getLogger(__name__)

RECALL_AGENT_PROMPT = """\
You are a Recall agent for Slay the Spire. Your ONLY tool is recall.

Read the game state carefully, then use recall to search memory for
relevant past experiences, strategies, and lessons.

You may call recall multiple times with different queries to gather
enough context. When you have sufficient information, output a concise
analysis as plain text (no tool calls).

Output format:
- Situation: [1 sentence describing current game state]
- Key memories: [2-4 bullet points of relevant findings from recall]
- Considerations: [1-2 sentences on what to watch out for]

Do NOT suggest specific card plays. Focus on strategic context and
lessons from past runs."""

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


def run_recall_agent(
    game_state_json: str,
    model: str = MODEL,
    reasoning_effort: str = REASONING_EFFORT,
    max_turns: int = 3,
) -> str:
    """Run a mini agent loop with only the recall tool.

    Args:
        game_state_json: Raw JSON game state to analyze.
        model: LLM model name.
        reasoning_effort: Reasoning effort level.
        max_turns: Maximum recall calls before forcing output.

    Returns:
        Analysis text.
    """
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": RECALL_AGENT_PROMPT},
        {
            "role": "user",
            "content": (
                f"Game state:\n```json\n{game_state_json}\n```\n\n"
                "Analyze this state and recall relevant memories."
            ),
        },
    ]

    for _ in range(max_turns):
        response = call_llm(
            messages,
            [RECALL_TOOL],
            model,
            reasoning_effort,
            caller="recall",
        )
        parsed = parse_llm_response(response)

        messages.append(build_assistant_message(parsed.content, parsed.tool_calls))

        if not parsed.tool_calls:
            return parsed.content or ""

        for tc in parsed.tool_calls:
            fn_args = json.loads(tc.function.arguments)
            query = fn_args.get("query", "")
            logger.info(
                "recall agent query",
                extra={"event": "recall_agent_query", "query": query},
            )
            result = _execute_recall(query)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                },
            )

    # Max turns reached — force final analysis without tools
    response = call_llm(messages, [], model, reasoning_effort, caller="recall")
    final = response.choices[0].message
    return final.content or ""
