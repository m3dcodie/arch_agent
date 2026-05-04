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

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Signals that indicate a 429 / rate-limit response from any provider.
_RATE_LIMIT_SIGNALS = ("429", "rate limit", "too many requests", "ratelimit")

# Maximum number of attempts before giving up.
_MAX_RETRIES = 3

# Base wait time in seconds; doubles on each subsequent attempt (15 → 30 → 60).
_RETRY_BASE_WAIT = 15

# Try to import ChatOpenAI once at module load so the check is free in the
# hot retry loop.  If langchain-openai is not installed, fall back gracefully.
try:
    from langchain_openai import ChatOpenAI as _ChatOpenAI  # noqa: F401
except ImportError:  # pragma: no cover
    _ChatOpenAI = None  # type: ignore[assignment,misc]


def _is_rate_limit(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(signal in msg for signal in _RATE_LIMIT_SIGNALS)


def _plain_invoke(
    llm: BaseChatModel,
    prompt: ChatPromptTemplate,
    inputs: dict,
    schema: Type[T],
) -> T:
    """
    Invoke the LLM without structured-output support and parse the raw JSON
    response into `schema`.

    Used as a fallback for providers that do not support tool/function calling
    (e.g. Ollama, HuggingFace router models).

    Raises:
        ValueError: if no valid JSON object is found in the model output.
    """
    chain = prompt | llm
    response = chain.invoke(inputs)
    raw = response.content if hasattr(response, "content") else str(response)
    # Strip chain-of-thought tags produced by some reasoning models.
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    # Strip markdown code fences.
    raw = re.sub(r"```(?:json)?", "", raw).strip()
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in model output: {raw[:300]}")
    return schema(**json.loads(match.group()))


def invoke_structured(
    llm: BaseChatModel,
    prompt: ChatPromptTemplate,
    inputs: dict,
    schema: Type[T],
) -> T:
    """
    Invoke the LLM and parse the result into a Pydantic model.

    Strategy:
    1. Attempt ``llm.with_structured_output(schema)`` (native tool/function calling).
       OpenAI-compatible providers (including GitHub Copilot) require
       ``method="function_calling"`` to avoid strict-mode validation errors in
       langchain-openai >= 0.3.
    2. On any non-rate-limit failure, fall back to plain-invoke + JSON extraction.
    3. Retry up to ``_MAX_RETRIES`` times with exponential backoff on 429 errors.

    Args:
        llm:    Configured LangChain chat model.
        prompt: ChatPromptTemplate to apply.
        inputs: Template variable values.
        schema: Pydantic model class to deserialise the response into.

    Returns:
        An instance of ``schema`` populated from the LLM response.

    Raises:
        The last exception encountered after all retries are exhausted.
    """
    last_exc: Exception = RuntimeError("No attempts made")

    for attempt in range(_MAX_RETRIES):
        try:
            structured_kwargs = (
                {"method": "function_calling"}
                if (_ChatOpenAI is not None and isinstance(llm, _ChatOpenAI))
                else {}
            )
            chain = prompt | llm.with_structured_output(schema, **structured_kwargs)
            return chain.invoke(inputs)

        except Exception as exc:
            if _is_rate_limit(exc):
                wait = _RETRY_BASE_WAIT * (2 ** attempt)
                logger.warning(
                    "[LLM] Rate limited — retrying in %ds (attempt %d/%d)",
                    wait,
                    attempt + 1,
                    _MAX_RETRIES,
                )
                time.sleep(wait)
                last_exc = exc
                continue

            # Non-rate-limit error: fall back to plain JSON invoke immediately.
            try:
                return _plain_invoke(llm, prompt, inputs, schema)
            except Exception as plain_exc:
                if _is_rate_limit(plain_exc):
                    wait = _RETRY_BASE_WAIT * (2 ** attempt)
                    logger.warning(
                        "[LLM] Rate limited (plain fallback) — retrying in %ds (attempt %d/%d)",
                        wait,
                        attempt + 1,
                        _MAX_RETRIES,
                    )
                    time.sleep(wait)
                    last_exc = plain_exc
                    continue
                raise plain_exc

    raise last_exc
