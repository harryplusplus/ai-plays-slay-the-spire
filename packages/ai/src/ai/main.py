import base64
import io
import json
import logging
import subprocess
import time
from typing import TYPE_CHECKING, Any

from PIL import Image

if TYPE_CHECKING:
    from openai.types.chat import (
        ChatCompletionContentPartParam,
        ChatCompletionMessageParam,
    )


from .constants import (
    MODEL,
    PLAY_AGENT_PROMPT,
    REASONING_EFFORT,
    RETRY_DELAY,
    RUN_ENDED_PROMPT,
    TOOLS,
)
from .llm import (
    build_assistant_message,
    build_multimodal_content,
    call_llm,
    parse_llm_response,
)
from .log import (
    dump_messages,
    init_ai_logger,
    init_reasoning_logger,
    init_run_logger,
)
from .recall_agent import run_recall_agent
from .retain_agent import run_retain_agent
from .window import capture, find_window

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
    return f"error: unknown tool {name}"


_MAX_SCREENSHOT_DIMENSION = 800
_SCREENSHOT_JPEG_QUALITY = 70


def _capture_screenshot() -> str:
    """Capture, resize, and return base64-encoded JPEG.

    Resizes to at most 800px on the longest edge to keep context small.
    Raises on failure — no fallback. Screenshot is mandatory.
    """
    window = find_window("Modded Slay the Spire")
    if window is None:
        msg = "Slay the Spire window not found"
        raise RuntimeError(msg)
    raw_b64 = capture(window["id"])
    img = Image.open(io.BytesIO(base64.b64decode(raw_b64)))
    w, h = img.size
    if w > _MAX_SCREENSHOT_DIMENSION or h > _MAX_SCREENSHOT_DIMENSION:
        ratio = _MAX_SCREENSHOT_DIMENSION / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.Resampling.LANCZOS)  # pyright: ignore[reportUnknownMemberType,reportAttributeAccessIssue]
    buf = io.BytesIO()
    img = img.convert("RGB")
    img.save(buf, format="JPEG", quality=_SCREENSHOT_JPEG_QUALITY)
    b64 = base64.b64encode(buf.getvalue()).decode()
    logger.info(
        "screenshot captured",
        extra={
            "event": "screenshot",
            "window_id": window["id"],
            "original_size": len(raw_b64),
            "resized_size": len(b64),
            "original_dims": f"{w}x{h}",
        },
    )
    return b64


def _build_document_id(state: dict[str, Any]) -> str | None:
    """Build a stable document_id from game state for combat-scoped memory grouping."""
    gs = state.get("game_state", {})
    seed = gs.get("seed")
    act = gs.get("act")
    floor = gs.get("floor")
    if seed is not None and act is not None and floor is not None:
        return f"combat-{seed}-{act}-{floor}"
    return None


def trim_messages(messages: list[ChatCompletionMessageParam]) -> None:
    """Keep only the last 2 complete turns (assistant + tool pairs).

    A turn = one assistant message + all following tool messages.
    Older state JSONs (~24KB each) are discarded to keep context
    small and focused on recent actions.
    """
    keep_turns = 2

    if len(messages) <= 1:
        return

    assistant_positions = [
        i for i, m in enumerate(messages) if m.get("role") == "assistant"
    ]

    if len(assistant_positions) <= keep_turns:
        return

    keep_from = assistant_positions[-keep_turns]
    logger.info(
        "message trim",
        extra={
            "event": "message_trim",
            "dropped_count": keep_from,
            "dropped_roles": [m.get("role") for m in messages[:keep_from]],
            "kept": len(messages) - keep_from,
            "total_before": len(messages),
        },
    )
    del messages[:keep_from]


def _detect_trigger(
    prev_state: dict[str, Any] | None,
    new_state: dict[str, Any],
) -> str | None:
    """Detect what kind of retain-worthy event just occurred."""
    if new_state.get("in_game") is False:
        logger.info(
            "run_end detected",
            extra={"event": "retain_trigger", "trigger": "run_end"},
        )
        return "run_end"
    if prev_state is None:
        return None

    prev_screen = prev_state.get("game_state", {}).get("screen_type", "")
    new_screen = new_state.get("game_state", {}).get("screen_type", "")
    prev_room = prev_state.get("game_state", {}).get("room_type", "")
    new_room = new_state.get("game_state", {}).get("room_type", "")

    logger.debug(
        "screen_transition",
        extra={
            "event": "screen_transition",
            "prev_screen": prev_screen,
            "new_screen": new_screen,
            "prev_room": prev_room,
            "new_room": new_room,
            "floor": new_state.get("game_state", {}).get("floor"),
        },
    )

    if new_screen == prev_screen and new_room == prev_room:
        logger.debug(
            "no screen change",
            extra={"event": "screen_transition", "reason": "no_change"},
        )
        return None

    # GRID entry suppress: REST/SHOP_SCREEN→GRID fires retain prematurely.
    if new_screen == "GRID":
        logger.debug(
            "no trigger on enter GRID",
            extra={
                "event": "screen_transition",
                "reason": "enter_grid",
                "prev_screen": prev_screen,
                "new_screen": new_screen,
                "prev_room": prev_room,
            },
        )
        return None

    if prev_screen == "GRID":
        grid_trigger = {
            "RestRoom": "campfire",
            "ShopRoom": "shop",
            "EventRoom": "event",
        }.get(prev_room)
        logger.info(
            "trigger detected",
            extra={
                "event": "retain_trigger",
                "trigger": grid_trigger,
                "matched_by": "grid_transition",
                "prev_screen": prev_screen,
                "new_screen": new_screen,
                "prev_room": prev_room,
                "new_room": new_room,
            },
        )
        return grid_trigger

    transitions: dict[str, str] = {
        "EVENT": "event",
        "SHOP_SCREEN": "shop",
        "SHOP_ROOM": "shop",
        "REST": "campfire",
        "CHEST": "chest",
        "CARD_REWARD": "card_pick",
    }
    if prev_screen in transitions:
        trigger = transitions[prev_screen]
        logger.info(
            "trigger detected",
            extra={
                "event": "retain_trigger",
                "trigger": trigger,
                "matched_by": "transition_map",
                "prev_screen": prev_screen,
                "new_screen": new_screen,
            },
        )
        return trigger
    if prev_screen in ("NONE", "HAND_SELECT") and new_screen == "COMBAT_REWARD":
        logger.info(
            "trigger detected",
            extra={
                "event": "retain_trigger",
                "trigger": "combat_end",
                "matched_by": "combat_end_transition",
                "prev_screen": prev_screen,
                "new_screen": new_screen,
            },
        )
        return "combat_end"

    logger.debug(
        "no trigger matched",
        extra={
            "event": "screen_transition",
            "reason": "unmatched",
            "prev_screen": prev_screen,
            "new_screen": new_screen,
            "prev_room": prev_room,
            "new_room": new_room,
        },
    )
    return None


def _build_user_message(
    state_json: str, recall_analysis: str, screenshot_b64: str
) -> list[ChatCompletionContentPartParam]:
    text = f"State:\n```json\n{state_json}\n```\n\nRecall Analysis:\n{recall_analysis}"
    return build_multimodal_content(text, screenshot_b64)


def _run_agent() -> None:  # noqa: PLR0915
    """Main agent loop."""
    messages: list[ChatCompletionMessageParam] = []

    current_state_json = game_cli("command", "state")
    current_state = json.loads(current_state_json)

    while True:
        trim_messages(messages)

        # 1. Screenshot (before action — for Recall + Play)
        screenshot_before = _capture_screenshot()

        # 2. Recall
        recall_analysis = run_recall_agent(
            messages, current_state_json, screenshot_b64=screenshot_before
        )

        # 3. Build play prompt with system prompt + history + state
        play_messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": PLAY_AGENT_PROMPT},
            *messages,
            {
                "role": "user",
                "content": _build_user_message(
                    current_state_json,
                    recall_analysis,
                    screenshot_b64=screenshot_before,
                ),
            },
        ]

        # 4. Play
        logger.debug(
            "llm call",
            extra={"event": "call_llm", "message_count": len(play_messages)},
        )
        start_time = time.monotonic()
        dump_messages(play_messages)
        response = call_llm(
            play_messages,
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
                "caller": "play",
                "has_tool_calls": bool(parsed.tool_calls),
                "tool_names": tool_names,
                "content_preview": str(parsed.content or "")[:200],
                "duration_ms": duration_ms,
            },
        )

        # 5. Reasoning log
        if parsed.reasoning_content:
            reasoning_logger.debug(
                "reasoning",
                extra={
                    "event": "reasoning",
                    "recall_analysis": recall_analysis,
                    "reasoning_content": parsed.reasoning_content,
                    "message_count": len(messages),
                    "duration_ms": duration_ms,
                },
            )

        # 6. Assistant message
        messages.append(build_assistant_message(parsed.content, parsed.tool_calls))

        # 7. Execute tools
        if not parsed.tool_calls:
            logger.warning(
                "no tool call",
                extra={
                    "event": "warning",
                    "warning_type": "no_tool_call",
                    "content_preview": str(parsed.content or "")[:200],
                },
            )
            messages.append(
                {"role": "user", "content": "You must use a tool."},
            )
            continue

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
                new_state = json.loads(result)

                if new_state.get("in_game") is False:
                    logger.info(
                        "run ended",
                        extra={"event": "run_end", "state": _state_summary(result)},
                    )
                    run_logger.info(result)
                    messages.append(
                        {"role": "user", "content": RUN_ENDED_PROMPT},
                    )

                # 8. Retain
                trigger = _detect_trigger(current_state, new_state)
                if trigger:
                    screenshot_after = _capture_screenshot()
                    retain_content = run_retain_agent(
                        messages, trigger, screenshot_b64=screenshot_after
                    )
                    doc_id = _build_document_id(new_state)
                    if doc_id:
                        game_cli("retain", retain_content, "--document-id", doc_id)
                    else:
                        game_cli("retain", retain_content)
                    logger.info(
                        "retain agent",
                        extra={
                            "event": "retain_agent",
                            "trigger": trigger,
                            "prev_screen": current_state.get("game_state", {}).get(
                                "screen_type"
                            ),
                            "new_screen": new_state.get("game_state", {}).get(
                                "screen_type"
                            ),
                            "floor": new_state.get("game_state", {}).get("floor"),
                        },
                    )

                current_state = new_state
                current_state_json = result


def main() -> None:
    init_ai_logger()
    init_run_logger()
    init_reasoning_logger()
    _run_agent()
