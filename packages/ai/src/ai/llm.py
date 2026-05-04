"""LLM API call with retry logic."""

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from openai import (
    APIConnectionError,
    APIStatusError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)

from .constants import MAX_ATTEMPTS, OPENAI_API_KEY, OPENAI_BASE_URL, RETRY_DELAY

if TYPE_CHECKING:
    from openai.types.chat import (
        ChatCompletion,
        ChatCompletionAssistantMessageParam,
        ChatCompletionMessageParam,
        ChatCompletionToolUnionParam,
    )

from openai.types.chat import (
    ChatCompletionContentPartParam,
    ChatCompletionMessageToolCall,
)

logger = logging.getLogger(__name__)
llm_logger = logging.getLogger("llm")


@dataclass
class ParsedResponse:
    content: str | None
    tool_calls: list[ChatCompletionMessageToolCall]
    reasoning_content: str | None


def parse_llm_response(response: ChatCompletion) -> ParsedResponse:
    """Extract typed fields from an LLM response."""
    msg = response.choices[0].message
    return ParsedResponse(
        content=msg.content,
        tool_calls=[
            tc
            for tc in (msg.tool_calls or [])
            if isinstance(tc, ChatCompletionMessageToolCall)
        ],
        reasoning_content=getattr(msg, "reasoning_content", None),
    )


def build_multimodal_content(
    text: str, screenshot_b64: str
) -> list[ChatCompletionContentPartParam]:
    """Build user message content list with text and an image."""
    return [
        {"type": "text", "text": text},
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{screenshot_b64}"},
        },
    ]


def build_assistant_message(
    content: str | None,
    tool_calls: list[ChatCompletionMessageToolCall],
) -> ChatCompletionAssistantMessageParam:
    """Build an assistant message dict."""
    msg: ChatCompletionAssistantMessageParam = {
        "role": "assistant",
        "content": content,
    }
    if tool_calls:
        msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in tool_calls
        ]
    return msg


def _backoff(attempt: int, max_seconds: float) -> float:
    """Exponential backoff: RETRY_DELAY * 2^(attempt-1), capped at max_seconds."""
    return min(RETRY_DELAY * (2 ** (attempt - 1)), max_seconds)


def call_llm(
    messages: list[ChatCompletionMessageParam],
    tools: list[ChatCompletionToolUnionParam],
    model: str,
    reasoning_effort: str,
    temperature: float = 0.0,
    caller: str = "",
) -> ChatCompletion:
    """Call LLM with retry. Creates and closes client per request.

    Args:
        caller: Agent name for log context (e.g. "play", "recall", "retain").
    """
    attempt = 0
    while True:
        attempt += 1
        client = OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
            max_retries=0,
        )
        llm_logger.debug(
            "call_llm_before",
            extra={
                "event": "call_llm_before",
                "caller": caller,
                "messages": messages,
                "tools": tools,
            },
        )
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                temperature=temperature,
                reasoning_effort=reasoning_effort,  # pyright: ignore[reportArgumentType]
            )
            llm_logger.debug(
                "call_llm_after",
                extra={
                    "event": "call_llm_after",
                    "caller": caller,
                    "response": response.model_dump(),
                },
            )
        except InternalServerError:
            if attempt >= MAX_ATTEMPTS:
                logger.exception(
                    "LLM API 500 error persisted after max attempts",
                    extra={
                        "event": "error",
                        "error_type": "llm_500_max_attempts",
                        "caller": caller,
                    },
                )
                time.sleep(30)
                attempt = 0
            else:
                logger.warning(
                    "LLM API 500 error",
                    extra={
                        "event": "error",
                        "error_type": "llm_500",
                        "attempt": attempt,
                        "caller": caller,
                    },
                )
                time.sleep(_backoff(attempt, 60))
        except RateLimitError:
            logger.warning(
                "LLM API rate limited",
                extra={
                    "event": "error",
                    "error_type": "llm_429",
                    "attempt": attempt,
                    "caller": caller,
                },
            )
            time.sleep(_backoff(attempt, 120))
        except APIConnectionError:
            logger.warning(
                "LLM API connection error",
                extra={
                    "event": "error",
                    "error_type": "llm_connection",
                    "attempt": attempt,
                    "caller": caller,
                },
            )
            time.sleep(RETRY_DELAY)
        except APIStatusError as e:
            if attempt >= MAX_ATTEMPTS:
                logger.exception(
                    "LLM API status error persisted after max attempts",
                    extra={
                        "event": "error",
                        "error_type": "llm_status_max_attempts",
                        "status_code": e.status_code,
                        "caller": caller,
                    },
                )
                time.sleep(30)
                attempt = 0
            else:
                logger.warning(
                    "LLM API status error",
                    extra={
                        "event": "error",
                        "error_type": "llm_status",
                        "status_code": e.status_code,
                        "attempt": attempt,
                        "caller": caller,
                    },
                )
                time.sleep(_backoff(attempt, 60))
        except Exception:
            logger.exception(
                "LLM API call failed",
                extra={"event": "error", "error_type": "llm_api", "caller": caller},
            )
            time.sleep(RETRY_DELAY)
        else:
            return response
        finally:
            client.close()
