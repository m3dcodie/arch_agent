"""
LLM invocation utilities shared across all agent nodes.

Provides a single, provider-agnostic entry point for structured LLM output
with exponential-backoff retry on rate-limit errors and a plain-JSON fallback
for providers that do not support tool/function calling.
"""

import json
import logging
import re
import time
from typing import Type, TypeVar

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from core.cost_tracker import log_llm_cost

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Signals that indicate a transient rate-limit or throttle response from any provider.
# GitHub Copilot API sometimes returns HTTP 403 "forbidden" instead of 429 when
# temporarily throttled, so we treat those as retriable too.
_RATE_LIMIT_SIGNALS = (
    "429",
    "rate limit",
    "too many requests",
    "ratelimit",
    "access to this endpoint is forbidden",  # GitHub Copilot transient 403
)

# Signals that definitively identify a *permanent* denial — never retry these
# even if the message would otherwise match a rate-limit signal.
# E.g. openai.PermissionDeniedError: "Access to this endpoint is forbidden.
# Please review our Terms of Service."
_PERMANENT_DENIAL_SIGNALS = (
    "your account",
    "account has been",
    "suspended",
    "billing",
)

# Maximum number of attempts before giving up.
_MAX_RETRIES = 3

# Base wait time in seconds; doubles on each subsequent attempt (5 → 10 → 20).
# Kept short because GitHub Copilot transient 403s typically resolve in seconds.
_RETRY_BASE_WAIT = 5

# Try to import ChatOpenAI once at module load so the check is free in the
# hot retry loop.  If langchain-openai is not installed, fall back gracefully.
try:
    from langchain_openai import ChatOpenAI as _ChatOpenAI  # noqa: F401
except ImportError:  # pragma: no cover
    _ChatOpenAI = None  # type: ignore[assignment,misc]


def _is_permanent_denial(exc: Exception) -> bool:
    """Return True when the exception signals a non-retriable permanent denial.

    Permanent denials include Terms-of-Service violations, account suspensions,
    and billing issues.  Retrying these wastes time and quota.
    """
    msg = str(exc).lower()
    return any(signal in msg for signal in _PERMANENT_DENIAL_SIGNALS)


def _is_rate_limit(exc: Exception) -> bool:
    """Return True when the exception is a transient throttle that warrants a retry.

    Excludes permanent denials (e.g. ToS violations) even when the HTTP status
    code or message text would otherwise look like a rate-limit signal.
    """
    if _is_permanent_denial(exc):
        return False
    msg = str(exc).lower()
    return any(signal in msg for signal in _RATE_LIMIT_SIGNALS)


def _plain_invoke(
    llm: BaseChatModel,
    prompt: ChatPromptTemplate,
    inputs: dict,
    schema: Type[T],
) -> tuple[T, dict, str]:
    """
    Invoke the LLM without structured-output support and parse the raw JSON
    response into `schema`.

    Used as a fallback for providers that do not support tool/function calling
    (e.g. Ollama, HuggingFace router models).

    Returns:
        A ``(parsed_schema, usage_metadata, response_text)`` tuple.
        ``usage_metadata`` is the LangChain-normalised dict from
        ``AIMessage.usage_metadata`` (may be an empty dict if the provider
        does not expose it).  ``response_text`` is the raw model output after
        stripping chain-of-thought tags and markdown fences.

    Raises:
        ValueError: if no valid JSON object is found in the model output.
    """
    chain = prompt | llm
    response = chain.invoke(inputs)
    usage: dict = getattr(response, "usage_metadata", None) or {}
    raw = response.content if hasattr(response, "content") else str(response)
    # Strip chain-of-thought tags produced by some reasoning models.
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    # Strip markdown code fences.
    raw = re.sub(r"```(?:json)?", "", raw).strip()
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in model output: {raw[:300]}")
    return schema(**json.loads(match.group())), usage, raw


def invoke_structured(
    llm: BaseChatModel,
    prompt: ChatPromptTemplate,
    inputs: dict,
    schema: Type[T],
    agent_role: str = "unknown",
) -> T:
    """
    Invoke the LLM and parse the result into a Pydantic model.

    Strategy:
    1. Attempt ``llm.with_structured_output(schema, include_raw=True)`` (native
       tool/function calling).  ``include_raw=True`` returns
       ``{"raw": AIMessage, "parsed": T | None, "parsing_error": ...}`` so
       token-usage metadata can be extracted from the raw message.
       OpenAI-compatible providers (including GitHub Copilot) require
       ``method="function_calling"`` to avoid strict-mode validation errors in
       langchain-openai >= 0.3.
    2. On any non-rate-limit failure, or when ``parsed`` is ``None`` (parse
       error despite a successful API call), fall back to plain-invoke + JSON
       extraction.
    3. Retry up to ``_MAX_RETRIES`` times with exponential backoff on 429 errors.
    4. Log token usage and estimated cost via :func:`core.cost_tracker.log_llm_cost`
       after every successful invocation.

    Args:
        llm:        Configured LangChain chat model.
        prompt:     ChatPromptTemplate to apply.
        inputs:     Template variable values.
        schema:     Pydantic model class to deserialise the response into.
        agent_role: Name of the calling agent node used in cost log lines
                    (e.g. ``"auditor"``).  Defaults to ``"unknown"``.

    Returns:
        An instance of ``schema`` populated from the LLM response.

    Raises:
        The last exception encountered after all retries are exhausted.
    """
    last_exc: Exception = RuntimeError("No attempts made")

    # Render prompt text once so local tokenizer can count tokens without
    # repeating the formatting work inside the retry loop.
    try:
        rendered_messages = prompt.format_messages(**inputs)
        prompt_text: str | None = "\n".join(
            m.content if isinstance(m.content, str) else str(m.content)
            for m in rendered_messages
        )
    except Exception:
        prompt_text = None

    from core.audit_logger import audit_event as _audit_event

    for attempt in range(_MAX_RETRIES):
        # === Structured output path ===
        try:
            structured_kwargs: dict = {"include_raw": True}
            if _ChatOpenAI is not None and isinstance(llm, _ChatOpenAI):
                structured_kwargs["method"] = "function_calling"

            chain = prompt | llm.with_structured_output(schema, **structured_kwargs)
            t0 = time.perf_counter()
            raw_result = chain.invoke(inputs)
            llm_duration_ms = round((time.perf_counter() - t0) * 1000, 2)

            parsed = raw_result.get("parsed") if isinstance(raw_result, dict) else None
            if parsed is not None:
                raw_msg = raw_result.get("raw")
                usage: dict = getattr(raw_msg, "usage_metadata", None) or {}
                # When function calling is used the model response payload sits
                # in tool_calls, leaving raw_msg.content as "" (empty string).
                # Fall back to the serialised Pydantic output so the local
                # tokenizer can estimate response tokens instead of logging N/A.
                response_text: str | None = getattr(raw_msg, "content", None) or None
                if not response_text and hasattr(parsed, "model_dump"):
                    response_text = json.dumps(parsed.model_dump())
                log_llm_cost(
                    llm, usage, agent_role,
                    prompt_text=prompt_text, response_text=response_text,
                    duration_ms=llm_duration_ms,
                )
                return parsed
            # parsed is None (parse error despite successful API call) —
            # fall through to the plain-invoke fallback below.

        except Exception as exc:
            if _is_permanent_denial(exc):
                # Non-retriable: log clearly and re-raise immediately.
                logger.error(
                    "[LLM] Permanent API denial — not retrying. agent=%s error=%s",
                    agent_role,
                    exc,
                )
                _audit_event(
                    "llm.denied",
                    level=40,  # logging.ERROR
                    agent=agent_role,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                raise

            if _is_rate_limit(exc):
                wait = _RETRY_BASE_WAIT * (2 ** attempt)
                logger.warning(
                    "[LLM] Throttled (transient) — retrying in %ds (attempt %d/%d) agent=%s",
                    wait,
                    attempt + 1,
                    _MAX_RETRIES,
                    agent_role,
                )
                _audit_event(
                    "llm.retry",
                    agent=agent_role,
                    attempt=attempt + 1,
                    max_attempts=_MAX_RETRIES,
                    wait_seconds=wait,
                    error=str(exc),
                )
                time.sleep(wait)
                last_exc = exc
                continue
            # Non-rate-limit, non-permanent error — fall through to plain-invoke fallback.

        # === Plain-invoke fallback ===
        try:
            t0 = time.perf_counter()
            parsed, usage, response_text = _plain_invoke(llm, prompt, inputs, schema)
            llm_duration_ms = round((time.perf_counter() - t0) * 1000, 2)
            log_llm_cost(
                llm, usage, agent_role,
                prompt_text=prompt_text, response_text=response_text,
                duration_ms=llm_duration_ms,
            )
            return parsed
        except Exception as plain_exc:
            if _is_permanent_denial(plain_exc):
                logger.error(
                    "[LLM] Permanent API denial — not retrying. agent=%s error=%s",
                    agent_role,
                    plain_exc,
                )
                _audit_event(
                    "llm.denied",
                    level=40,  # logging.ERROR
                    agent=agent_role,
                    error=str(plain_exc),
                    error_type=type(plain_exc).__name__,
                )
                raise

            if _is_rate_limit(plain_exc):
                wait = _RETRY_BASE_WAIT * (2 ** attempt)
                logger.warning(
                    "[LLM] Throttled (transient, plain fallback) — retrying in %ds (attempt %d/%d) agent=%s",
                    wait,
                    attempt + 1,
                    _MAX_RETRIES,
                    agent_role,
                )
                _audit_event(
                    "llm.retry",
                    agent=agent_role,
                    attempt=attempt + 1,
                    max_attempts=_MAX_RETRIES,
                    wait_seconds=wait,
                    error=str(plain_exc),
                    path="plain_fallback",
                )
                time.sleep(wait)
                last_exc = plain_exc
                continue
            raise plain_exc

    raise last_exc
