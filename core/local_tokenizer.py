"""
Local tokenizer utility: count tokens without making an API call.

Supports two backends:

- **tiktoken** (OpenAI and Claude models) — available whenever ``langchain-openai``
  is installed.  OpenAI GPT-4.x / GPT-4o use ``o200k_base`` exactly.
  Anthropic Claude models use a proprietary tokenizer; ``cl100k_base`` is used
  as a close approximation (typically within 5%).

- **transformers** ``AutoTokenizer`` (HuggingFace models) — optional; install
  with ``pip install transformers`` or ``pip install adag[hf]``.  Tokenizers
  are downloaded on first use and cached in memory for the process lifetime.

Models with no supported local tokenizer (Amazon Nova, Ollama) will return
``None`` and are omitted from log output.

Token counts from local tokenizers may differ slightly from API-reported counts
due to special tokens and chat-template overhead, but are a reliable proxy for
comparing how different model families tokenize the same text.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# tiktoken (OpenAI / GPT-4 family)
# ---------------------------------------------------------------------------

try:
    import tiktoken as _tiktoken
    _TIKTOKEN_AVAILABLE = True
except ImportError:  # pragma: no cover
    _tiktoken = None  # type: ignore[assignment]
    _TIKTOKEN_AVAILABLE = False

# Model ID → tiktoken encoding name.
# GPT-4o and GPT-4.1 families share the o200k_base encoding.
# Claude models use a proprietary tokenizer; cl100k_base is the closest public
# approximation (same BPE family, typically within ~5% of the true count).
_TIKTOKEN_ENCODING_MAP: dict[str, str] = {
    # --- OpenAI GPT-4o / GPT-4.1 (exact) ---
    "gpt-4.1":                "o200k_base",
    "gpt-4.1-2025-04-14":    "o200k_base",
    "gpt-4.1-mini":           "o200k_base",
    "gpt-4.1-nano":           "o200k_base",
    "gpt-4o":                 "o200k_base",
    "gpt-4o-2024-08-06":     "o200k_base",
    "gpt-4o-mini":            "o200k_base",
    "gpt-4o-mini-2024-07-18": "o200k_base",
    # --- Anthropic Claude — full Bedrock model IDs (approximate) ---
    "anthropic.claude-3-haiku-20240307-v1:0":    "cl100k_base",
    "anthropic.claude-haiku-3-5-20241022-v1:0":  "cl100k_base",
    "anthropic.claude-haiku-4-5-20250929-v1:0":  "cl100k_base",
    "anthropic.claude-3-sonnet-20240229-v1:0":   "cl100k_base",
    "anthropic.claude-3-5-sonnet-20241022-v2:0": "cl100k_base",
    "anthropic.claude-3-5-sonnet-20240620-v1:0": "cl100k_base",
    "anthropic.claude-sonnet-4-20250514-v1:0":   "cl100k_base",
    "anthropic.claude-sonnet-4-5-20250929-v1:0": "cl100k_base",
    "anthropic.claude-3-opus-20240229-v1:0":     "cl100k_base",
    "anthropic.claude-opus-4-20250514-v1:0":     "cl100k_base",
    # --- Anthropic Claude — short names used by GitHub Copilot (approximate) ---
    "claude-opus-4.5":   "cl100k_base",
    "claude-sonnet-4.5": "cl100k_base",
    "claude-sonnet-4":   "cl100k_base",
    "claude-haiku-4.5":  "cl100k_base",
}

# ---------------------------------------------------------------------------
# transformers AutoTokenizer (HuggingFace models)
# ---------------------------------------------------------------------------

try:
    from transformers import AutoTokenizer as _AutoTokenizer  # type: ignore[import-untyped]
    _TRANSFORMERS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _AutoTokenizer = None  # type: ignore[assignment,misc]
    _TRANSFORMERS_AVAILABLE = False

# In-process tokenizer cache keyed by HuggingFace model ID.
_tokenizer_cache: dict[str, object] = {}

# HuggingFace model IDs that have a publicly downloadable tokenizer.
# Keyed by the pricing_key used in _COMPARISON_MODELS so callers can
# use the same identifier.
_HF_TOKENIZER_IDS: set[str] = {
    "Qwen/Qwen2.5-7B-Instruct",
    "Qwen/Qwen2.5-72B-Instruct",
    "Qwen/Qwen3-235B-A22B",
    "meta-llama/Llama-3.3-70B-Instruct",
    "meta-llama/Llama-3.1-8B-Instruct",
    "mistralai/Mistral-7B-Instruct-v0.3",
    "mistralai/Mixtral-8x7B-Instruct-v0.1",
    "mistralai/Mistral-Small-3.1-24B-Instruct-2503",
}


# Cross-region inference-profile prefixes used by Bedrock (mirrors cost_tracker).
_BEDROCK_PROFILE_PREFIXES: tuple[str, ...] = ("us.", "eu.", "ap.", "au.")


def _normalise_model_id(model_id: str) -> str:
    """Strip a Bedrock cross-region inference-profile prefix if present."""
    for prefix in _BEDROCK_PROFILE_PREFIXES:
        if model_id.startswith(prefix):
            return model_id[len(prefix):]
    return model_id


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def count_tokens(text: str, model_id: str) -> Optional[int]:
    """Return a local token count for *text* using the tokenizer for *model_id*.

    Resolution order:
    1. tiktoken — if *model_id* is a known OpenAI model.
    2. HuggingFace ``AutoTokenizer`` — if *model_id* is a known HF model ID
       and ``transformers`` is installed.

    Returns:
        Token count as ``int``, or ``None`` when no tokenizer is available
        for *model_id* or an error occurs.
    """
    model_id = _normalise_model_id(model_id)

    # --- tiktoken path ---
    if _TIKTOKEN_AVAILABLE and model_id in _TIKTOKEN_ENCODING_MAP:
        enc_name = _TIKTOKEN_ENCODING_MAP[model_id]
        try:
            enc = _tiktoken.get_encoding(enc_name)
            return len(enc.encode(text))
        except Exception as exc:
            logger.debug("tiktoken count failed for %s: %s", model_id, exc)
            return None

    # --- HuggingFace transformers path ---
    if _TRANSFORMERS_AVAILABLE and model_id in _HF_TOKENIZER_IDS:
        try:
            if model_id not in _tokenizer_cache:
                logger.debug("Loading local tokenizer for %s (one-time download)", model_id)
                _tokenizer_cache[model_id] = _AutoTokenizer.from_pretrained(
                    model_id, trust_remote_code=True
                )
            tok = _tokenizer_cache[model_id]
            return len(tok.encode(text))  # type: ignore[union-attr]
        except Exception as exc:
            logger.debug("transformers count failed for %s: %s", model_id, exc)
            return None

    return None


def compare_tokenizers(text: str) -> dict[str, Optional[int]]:
    """Count tokens for *text* across all supported comparison models.

    Returns a dict mapping model_id → token count (or None if unavailable).
    Useful for ad-hoc comparison without going through the cost-tracker.

    Example::

        from core.local_tokenizer import compare_tokenizers
        for model, count in compare_tokenizers("my prompt text").items():
            print(f"{model}: {count}")
    """
    all_ids = list(_TIKTOKEN_ENCODING_MAP.keys()) + list(_HF_TOKENIZER_IDS)
    return {mid: count_tokens(text, mid) for mid in all_ids}
