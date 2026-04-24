# pyright: reportArgumentType=none, reportUnknownArgumentType=none, reportUnknownMemberType=none, reportUnknownVariableType=none
import json
import logging
import subprocess
import time
from datetime import datetime, timezone
from typing import Any

from openai import OpenAI

from .constants import (
    LLM_DUMP_DIR,
    MAX_DUMPS,
    MAX_MESSAGES_CHARS,
    MAX_OUTPUT,
    MODEL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    RETRY_DELAY,
    SYSTEM_PROMPT,
    TOOLS,
)
from .log import init_logger, log_run_end

logger = logging.getLogger(__name__)


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


def auto_recall(state: dict[str, Any], last_query: str = "") -> str:
    """Build a recall query from current game state.
    Returns empty string if query is same as last_query.
    """
    parts: list[str] = []
    game_state = state.get("game_state")
    if game_state:
        cls = game_state.get("class", "")
        if cls:
            parts.append(cls)
        room = game_state.get("room_type", "")
        if room:
            parts.append(f"room={room}")
        act = game_state.get("act")
        if act is not None:
            parts.append(f"act={act}")
        screen = game_state.get("screen_type", "")
        if screen:
            parts.append(f"screen={screen}")
        combat = game_state.get("combat_state")
        if combat:
            monsters = combat.get("monsters", [])
            names = [m.get("name", "") for m in monsters[:3] if m.get("name")]
            if names:
                parts.append(f"monsters={','.join(names)}")
    query = " ".join(parts) if parts else "slay the spire general"
    if query == last_query:
        logger.debug("auto recall skipped (same query)")
        return ""
    logger.info("auto recall", extra={"event": "auto_recall", "query": query})
    return game_cli("recall", query)


def execute_tool(  # noqa: PLR0911
    name: str,
    arguments: dict[str, Any],
    game_state: dict[str, Any] | None = None,
) -> str:
    if name == "send_command":
        return game_cli("command", arguments["command"])
    if name == "recall":
        return game_cli("recall", arguments["query"])
    if name == "retain":
        doc_id = _build_document_id(game_state)
        if doc_id:
            return game_cli("retain", arguments["content"], "--document-id", doc_id)
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


def dump_messages(messages: list[dict[str, Any]]) -> None:
    """Dump the messages array to a file before LLM API call.
    Keeps only the last MAX_DUMPS dumps (action-based rotation).
    """
    LLM_DUMP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")  # noqa: UP017
    filepath = LLM_DUMP_DIR / f"llm_dump_{timestamp}.json"

    with filepath.open("w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)

    dumps = sorted(LLM_DUMP_DIR.glob("llm_dump_*.json"))
    while len(dumps) > MAX_DUMPS:
        oldest = dumps.pop(0)
        oldest.unlink()


def trim_messages(messages: list[dict[str, Any]]) -> None:
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


def _handle_send_command(
    result: str,
    fn_args: dict[str, Any],
    messages: list[dict[str, Any]],
    last_game_state: dict[str, Any] | None,
    last_auto_query: str,
) -> tuple[dict[str, Any] | None, str]:
    """Handle the result of a send_command tool call.
    Updates game state, runs auto_recall, builds next user message.
    Returns (updated_last_game_state, updated_last_auto_query).
    """
    try:
        new_state = json.loads(result)
        in_game = new_state.get("in_game", False)
        if not in_game:
            logger.info(
                "run ended",
                extra={"event": "run_end", "state": _state_summary(result)},
            )
            log_run_end(result)
        auto_recall_result = auto_recall(new_state, last_auto_query)
        content = f"State after your last command:\n{result}"
        if auto_recall_result:
            last_auto_query = auto_recall_result
            try:
                recall_data = json.loads(auto_recall_result)
                results = (
                    recall_data.get("results", [])
                    if isinstance(recall_data, dict)
                    else []
                )
                logger.info(
                    "auto recall result",
                    extra={
                        "event": "auto_recall_result",
                        "result_count": len(results),
                        "types": list(
                            {r.get("type") for r in results if r.get("type")},
                        ),
                    },
                )
            except json.JSONDecodeError:
                pass
            content += f"\n\nRelevant memories:\n{auto_recall_result}"
        command = fn_args.get("command", "").strip().upper()
        if command == "END":
            content += (
                "\n\nYou have ended your turn. "
                "You MUST call retain NOW with a strategic summary. "
                "Format:\n"
                "- Situation: [enemy/room and key patterns]\n"
                "- Decision: [what you did and why]\n"
                "- Outcome: [what worked, 1-2 sentences]\n"
                "- Lesson: [remember for next time]\n"
                "NEVER include raw HP/energy/block numbers."
            )
        messages.append({"role": "user", "content": content})
        if not in_game:
            messages.append({
                "role": "user",
                "content": (
                    "The run has ended (in_game=false). "
                    "Check if you defeated the Heart "
                    "or died. retain a summary of "
                    "this run's outcome, then start "
                    "a new game."
                ),
            })
    except json.JSONDecodeError:
        logger.exception(
            "json decode error",
            extra={"event": "error", "error_type": "json_decode"},
        )
        messages.append({"role": "user", "content": f"Command result:\n{result}"})
        return last_game_state, last_auto_query
    else:
        return new_state, last_auto_query


def main() -> None:
    init_logger()

    client = OpenAI(
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
    )

    messages: list[dict[str, Any]] = [  # type: ignore[type-arg]
        {"role": "system", "content": SYSTEM_PROMPT},
    ]

    initial = game_cli("command", "state")
    auto_recall_result = auto_recall(json.loads(initial))
    last_auto_query = ""
    content = f"Current game state:\n{initial}"
    if auto_recall_result:
        last_auto_query = auto_recall_result
        content += f"\n\nRelevant memories:\n{auto_recall_result}"
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
            extra={"event": "llm_call", "message_count": len(messages)},
        )

        try:
            start_time = time.monotonic()
            dump_messages(messages)
            response = client.chat.completions.create(  # pyright: ignore[reportArgumentType]
                model=MODEL,
                messages=messages,
                tools=TOOLS,
                temperature=0,
                reasoning_effort="high",
            )
            duration_ms = int((time.monotonic() - start_time) * 1000)
        except Exception:
            logger.exception(
                "LLM API call failed",
                extra={"event": "error", "error_type": "llm_api"},
            )
            time.sleep(RETRY_DELAY)
            continue

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

        choice = response.choices[0]
        assistant_msg = choice.message
        tool_names = [
            tc.function.name  # type: ignore[union-attr]
            for tc in (assistant_msg.tool_calls or [])
        ]
        logger.debug(
            "llm response",
            extra={
                "event": "llm_response",
                "has_tool_calls": bool(assistant_msg.tool_calls),
                "tool_names": tool_names,
                "content_preview": (assistant_msg.content or "")[:200],
                "duration_ms": duration_ms,
            },
        )

        messages.append(assistant_msg.to_dict())

        if assistant_msg.tool_calls:
            for tool_call in assistant_msg.tool_calls:
                fn_name: str = tool_call.function.name  # type: ignore[union-attr]
                fn_args = json.loads(tool_call.function.arguments)  # type: ignore[union-attr]
                logger.info(
                    "tool call",
                    extra={"event": "tool_call", "tool": fn_name, "arguments": fn_args},
                )

                result = execute_tool(fn_name, fn_args, last_game_state)
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
                    last_game_state, last_auto_query = _handle_send_command(
                        result, fn_args, messages, last_game_state, last_auto_query,
                    )
        else:
            logger.warning(
                "no tool call",
                extra={
                    "event": "warning",
                    "warning_type": "no_tool_call",
                    "content_preview": (assistant_msg.content or "")[:200],
                },
            )
            messages.append(
                {
                    "role": "user",
                    "content": "You must use a tool.",
                },
            )


if __name__ == "__main__":
    main()
