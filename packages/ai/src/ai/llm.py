"""LLM API call with retry logic."""

import logging
import time
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
        ChatCompletionMessageParam,
        ChatCompletionToolUnionParam,
    )

logger = logging.getLogger(__name__)


def _backoff(attempt: int, max_seconds: float) -> float:
    """Exponential backoff: RETRY_DELAY * 2^(attempt-1), capped at max_seconds."""
    return min(RETRY_DELAY * (2 ** (attempt - 1)), max_seconds)


def call_llm(  # noqa: PLR0913
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
        try:
            return client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                temperature=temperature,
                reasoning_effort=reasoning_effort,  # pyright: ignore[reportArgumentType]
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
        finally:
            client.close()
