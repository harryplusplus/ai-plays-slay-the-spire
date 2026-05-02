import json
import logging
import subprocess
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openai.types.chat import (
        ChatCompletionMessageParam,
    )


from .constants import (
    MAX_MESSAGES_CHARS,
    MODEL,
    REASONING_EFFORT,
    RETRY_DELAY,
    RUN_ENDED_PROMPT,
    SYSTEM_PROMPT,
    TOOLS,
)
from .llm import build_assistant_message, call_llm, parse_llm_response
from .log import (
    dump_messages,
    init_ai_logger,
    init_reasoning_logger,
    init_run_logger,
)
from .recall_agent import run_recall_agent
from .retain_agent import run_retain_agent

logger = logging.getLogger(__name__)
run_logger = logging.getLogger("run")
reasoning_logger = logging.getLogger("reasoning")


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
    return output


def _state_summary(state_json: str) -> dict[str, Any]:
    """Extract summary fields from game state JSON string."""
    try:
        data = json.loads(state_json)
    except json.JSONDecodeError:
        return {"parse_error": True, "raw_preview": state_json[:200]}

    gs = data.get("game_state", {})
    combat = gs.get("combat_state")
    summary: dict[str, Any] = {
        "in_game": data.get("in_game"),
        "ready": data.get("ready_for_command"),
        "command_id": data.get("command_id"),
        "screen": gs.get("screen_type"),
        "room": gs.get("room_type"),
        "room_phase": gs.get("room_phase"),
        "floor": gs.get("floor"),
        "act": gs.get("act"),
        "hp": gs.get("current_hp"),
        "max_hp": gs.get("max_hp"),
        "gold": gs.get("gold"),
    }
    if combat:
        player = combat.get("player", {})
        summary["combat"] = {
            "turn": combat.get("turn"),
            "energy": player.get("energy"),
            "block": player.get("block"),
            "hand_size": len(combat.get("hand", [])),
            "monsters": [
                {
                    "name": m.get("name"),
                    "hp": m.get("current_hp"),
                    "max_hp": m.get("max_hp"),
                    "intent": m.get("intent"),
                }
                for m in combat.get("monsters", [])[:3]
            ],
        }
    return summary


def _tool_result_summary(name: str, result: str) -> dict[str, Any]:
    """Build a structured summary of a tool result for logging."""
    summary: dict[str, Any] = {"tool": name}
    if result.startswith("error:"):
        summary["status"] = "error"
        summary["error"] = result[6:].strip()
        return summary

    if name == "send_command":
        summary["state"] = _state_summary(result)
    elif name in ("recall", "retain"):
        try:
            data = json.loads(result)
            summary.update(data)
        except json.JSONDecodeError:
            summary["raw_preview"] = result[:200]
    else:
        summary["raw_preview"] = result[:200]
    return summary


def execute_tool(
    name: str,
    arguments: dict[str, Any],
) -> str:
    if name == "send_command":
        return game_cli("command", arguments["command"])
    if name == "deck":
        return game_cli("deck")
    if name == "map":
        return game_cli("map")
    return f"error: unknown tool {name}"


def _build_document_id(game_state: dict[str, Any] | None) -> str | None:
    """Build a stable document_id from game state for combat-scoped memory grouping."""
    if game_state is None:
        return None
    gs = game_state.get("game_state")
    if not gs:
        return None
    seed = gs.get("seed")
    act = gs.get("act")
    floor = gs.get("floor")
    if seed is not None and act is not None and floor is not None:
        return f"combat-{seed}-{act}-{floor}"
    return None


def trim_messages(messages: list[ChatCompletionMessageParam]) -> None:
    """Drop oldest complete turns until total chars under limit.

    A turn is: user + assistant + tool(s). We remove whole turns
    so tool_call/tool_result pairs stay intact.
    """
    while True:
        total = sum(len(str(m.get("content", ""))) for m in messages)
        if total <= MAX_MESSAGES_CHARS or len(messages) <= 1:
            break

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
            "message trim",
            extra={
                "event": "message_trim",
                "dropped_count": len(removed),
                "dropped_roles": [m.get("role") for m in removed],
            },
        )
        del messages[start:end]


def _detect_trigger(  # noqa: PLR0911
    command: str,
    prev_state: dict[str, Any] | None,
    new_state: dict[str, Any],
) -> str | None:
    """Detect what kind of retain-worthy event just occurred."""
    if not new_state.get("in_game", False):
        return "run_end"
    if command == "END":
        return "turn_end"
    if prev_state is None:
        return None

    prev_screen = prev_state.get("game_state", {}).get("screen_type", "")
    new_screen = new_state.get("game_state", {}).get("screen_type", "")
    if new_screen == prev_screen:
        return None

    transitions: dict[str, str] = {
        "EVENT": "event",
        "SHOP": "shop",
        "REST": "campfire",
        "CHEST": "chest",
        "CARD_REWARD": "card_pick",
    }
    if prev_screen in transitions:
        return transitions[prev_screen]
    if prev_screen in ("NONE", "HAND_SELECT") and new_screen == "COMBAT_REWARD":
        return "combat_end"

    return None


def _handle_send_command(
    result: str,
    fn_args: dict[str, Any],
    messages: list[ChatCompletionMessageParam],
    last_game_state: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Handle the result of a send_command tool call.
    Updates game state, runs recall agent, detects retain triggers.
    Returns updated last_game_state, or None on parse error.
    """
    try:
        new_state = json.loads(result)
        in_game = new_state.get("in_game", False)
        if not in_game:
            logger.info(
                "run ended",
                extra={"event": "run_end", "state": _state_summary(result)},
            )
            run_logger.info(result)
        analysis = run_recall_agent(result)
        content = (
            f"State after your last command:\n```json\n{result}\n```\n"
            f"Recall Analysis:\n{analysis}"
        )
        messages.append({"role": "user", "content": content})
        if not in_game:
            messages.append(
                {
                    "role": "user",
                    "content": RUN_ENDED_PROMPT,
                },
            )

        trigger = _detect_trigger(
            fn_args.get("command", "").strip().upper(),
            last_game_state,
            new_state,
        )
        if trigger:
            retain_content = run_retain_agent(messages, trigger)
            doc_id = _build_document_id(new_state)
            if doc_id:
                game_cli("retain", retain_content, "--document-id", doc_id)
            else:
                game_cli("retain", retain_content)
            logger.info(
                "retain agent",
                extra={"event": "retain_agent", "trigger": trigger},
            )
    except json.JSONDecodeError:
        logger.exception(
            "json decode error",
            extra={"event": "error", "error_type": "json_decode"},
        )
        messages.append(
            {"role": "user", "content": f"Command result:\n```json\n{result}\n```"}
        )
        return None
    else:
        return new_state


def _run_agent() -> None:
    """Main agent loop."""
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]

    initial = game_cli("command", "state")
    analysis = run_recall_agent(initial)
    content = (
        f"Current game state:\n```json\n{initial}\n```\n\nRecall Analysis:\n{analysis}"
    )
    messages.append(
        {
            "role": "user",
            "content": content,
        },
    )
    logger.info(
        "initial state",
        extra={"event": "init", "state": _state_summary(initial)},
    )

    last_game_state: dict[str, Any] | None = None

    while True:
        trim_messages(messages)
        logger.debug(
            "llm call",
            extra={"event": "call_llm", "message_count": len(messages)},
        )

        start_time = time.monotonic()
        dump_messages(messages)
        response = call_llm(
            messages,
            TOOLS,
            MODEL,
            REASONING_EFFORT,
            caller="play",
        )
        duration_ms = int((time.monotonic() - start_time) * 1000)

        if not response.choices:
            resp_str = (
                response.model_dump_json()
                if hasattr(response, "model_dump_json")
                else str(response)
            )
            logger.error(
                "LLM returned empty choices",
                extra={
                    "event": "error",
                    "error_type": "empty_choices",
                    "response_preview": resp_str[:500],
                },
            )
            time.sleep(RETRY_DELAY)
            continue

        parsed = parse_llm_response(response)
        tool_names: list[str] = [tc.function.name for tc in parsed.tool_calls]
        logger.debug(
            "llm response",
            extra={
                "event": "llm_response",
                "has_tool_calls": bool(parsed.tool_calls),
                "tool_names": tool_names,
                "content_preview": str(parsed.content or "")[:200],
                "duration_ms": duration_ms,
                "reasoning_length": len(parsed.reasoning_content),
            },
        )

        if parsed.reasoning_content:
            reasoning_logger.debug(
                "reasoning",
                extra={
                    "event": "reasoning",
                    "reasoning_content": parsed.reasoning_content,
                    "message_count": len(messages),
                    "duration_ms": duration_ms,
                },
            )

        assistant_msg = build_assistant_message(
            parsed.content, parsed.tool_calls, parsed.reasoning_content
        )
        messages.append(assistant_msg)

        if parsed.tool_calls:
            for tool_call in parsed.tool_calls:
                fn_name: str = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)
                logger.info(
                    "tool call",
                    extra={"event": "tool_call", "tool": fn_name, "arguments": fn_args},
                )

                result = execute_tool(fn_name, fn_args)
                logger.info(
                    "tool result",
                    extra={
                        "event": "tool_result",
                        **_tool_result_summary(fn_name, result),
                    },
                )

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    },
                )

                if fn_name == "send_command":
                    last_game_state = _handle_send_command(
                        result,
                        fn_args,
                        messages,
                        last_game_state,
                    )
        else:
            logger.warning(
                "no tool call",
                extra={
                    "event": "warning",
                    "warning_type": "no_tool_call",
                    "content_preview": str(parsed.content or "")[:200],
                },
            )
            messages.append(
                {
                    "role": "user",
                    "content": "You must use a tool.",
                },
            )


def main() -> None:
    init_ai_logger()
    init_run_logger()
    init_reasoning_logger()
    _run_agent()
