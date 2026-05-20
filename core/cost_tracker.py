"""
LLM cost tracking: token extraction and cost estimation per call.

No data leaves the process — costs are computed locally from a static
pricing table and emitted as structured log lines at INFO level.

Pricing reference (on-demand, per 1 million tokens, as of 2026-05):
  https://aws.amazon.com/bedrock/pricing/
  https://openai.com/pricing
  https://www.anthropic.com/pricing
  https://huggingface.co/pricing

GitHub Copilot is subscription-based (flat monthly fee) so no per-call charge
applies, but we show the underlying model's list price as a reference so you
can gauge consumption value.  Those entries are labelled ``(list price)`` in
the log output.
"""

from __future__ import annotations

import logging
from typing import Optional

from langchain_core.language_models import BaseChatModel
from core.local_tokenizer import count_tokens as _count_local_tokens

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pricing table
# ---------------------------------------------------------------------------
# Format: { "model-id-or-name": (input_per_1m_usd, output_per_1m_usd) }
# Bedrock model IDs are normalised (cross-region inference-profile prefix
# stripped before lookup).  GitHub Copilot is subscription-based — no
# per-token billing tracked here.

_PRICING: dict[str, tuple[float, float]] = {
    # =========================================================================
    # AWS Bedrock — on-demand pricing
    # =========================================================================

    # ---- Anthropic Claude ---------------------------------------------------
    # Claude 4 family
    "anthropic.claude-opus-4-20250514-v1:0":     (15.00, 75.00),
    "anthropic.claude-sonnet-4-5-20250929-v1:0": ( 3.00, 15.00),
    "anthropic.claude-sonnet-4-20250514-v1:0":   ( 3.00, 15.00),
    "anthropic.claude-haiku-4-5-20250929-v1:0":  ( 0.80,  4.00),
    # Claude 3.x family
    "anthropic.claude-3-5-sonnet-20241022-v2:0": ( 3.00, 15.00),
    "anthropic.claude-3-5-sonnet-20240620-v1:0": ( 3.00, 15.00),
    "anthropic.claude-haiku-3-5-20241022-v1:0":  ( 0.80,  4.00),
    "anthropic.claude-3-opus-20240229-v1:0":     (15.00, 75.00),
    "anthropic.claude-3-sonnet-20240229-v1:0":   ( 3.00, 15.00),
    "anthropic.claude-3-haiku-20240307-v1:0":    ( 0.25,  1.25),

    # ---- Amazon Nova --------------------------------------------------------
    "amazon.nova-pro-v1:0":                      ( 0.80,  3.20),
    "amazon.nova-lite-v1:0":                     ( 0.06,  0.24),
    "amazon.nova-micro-v1:0":                    ( 0.035, 0.14),

    # ---- Meta Llama on Bedrock ----------------------------------------------
    "meta.llama3-3-70b-instruct-v1:0":           ( 2.65,  3.50),
    "meta.llama3-1-70b-instruct-v1:0":           ( 2.65,  3.50),
    "meta.llama3-1-8b-instruct-v1:0":            ( 0.22,  0.22),
    "meta.llama3-70b-instruct-v1:0":             ( 2.65,  3.50),
    "meta.llama3-8b-instruct-v1:0":              ( 0.30,  0.60),
    "meta.llama3-2-3b-instruct-v1:0":            ( 0.15,  0.15),
    "meta.llama3-2-1b-instruct-v1:0":            ( 0.10,  0.10),

    # ---- Mistral on Bedrock -------------------------------------------------
    "mistral.mixtral-8x7b-instruct-v0:1":        ( 0.45,  0.70),
    "mistral.mistral-7b-instruct-v0:2":          ( 0.15,  0.20),
    "mistral.mistral-large-2402-v1:0":           ( 4.00, 12.00),

    # =========================================================================
    # OpenAI — used directly or via HuggingFace router
    # =========================================================================
    "gpt-4.1":                ( 2.00,  8.00),
    "gpt-4.1-2025-04-14":    ( 2.00,  8.00),
    "gpt-4.1-mini":           ( 0.40,  1.60),
    "gpt-4.1-nano":           ( 0.10,  0.40),
    "gpt-4o":                 ( 2.50, 10.00),
    "gpt-4o-2024-08-06":     ( 2.50, 10.00),
    "gpt-4o-mini":            ( 0.15,  0.60),
    "gpt-4o-mini-2024-07-18": ( 0.15,  0.60),

    # =========================================================================
    # GitHub Copilot — subscription plan; entries below are the underlying
    # provider list prices shown as reference only (logged as "list price").
    # Model names are the short IDs used by the Copilot API.
    # Pricing source: https://docs.github.com/en/copilot/reference/copilot-billing/models-and-pricing
    # =========================================================================
    # Anthropic
    "claude-opus-4.5":   (15.00, 75.00),
    "claude-sonnet-4.6": ( 3.00, 15.00),
    "claude-sonnet-4.5": ( 3.00, 15.00),
    "claude-sonnet-4":   ( 3.00, 15.00),
    "claude-haiku-4.5":  ( 1.00,  5.00),
    # OpenAI  (gpt-4.1 / gpt-4o already covered in the OpenAI section above)
    "gpt-5-mini":        ( 0.25,  2.00),
    "raptor-mini":       ( 0.25,  2.00),
    "gpt-5.4-mini":      ( 0.75,  4.50),
    "gpt-5.2":           ( 1.75, 14.00),
    "gpt-5.2-codex":     ( 1.75, 14.00),
    "gpt-5.3-codex":     ( 1.75, 14.00),
    "gpt-5.4":           ( 2.50, 15.00),
    # Google Gemini
    "gemini-3-flash":    ( 0.50,  3.00),
    "gemini-2.5-pro":    ( 1.25, 10.00),
    "gemini-3.1-pro":    ( 2.00, 12.00),

    # =========================================================================
    # HuggingFace Serverless Inference Router
    # Prices are approximate and depend on the backend chosen by the router.
    # =========================================================================
    "Qwen/Qwen2.5-7B-Instruct":              ( 0.07,  0.07),
    "Qwen/Qwen2.5-72B-Instruct":             ( 0.40,  0.40),
    "Qwen/Qwen3-235B-A22B":                  ( 0.50,  0.50),
    "meta-llama/Llama-3.3-70B-Instruct":     ( 0.59,  0.79),
    "meta-llama/Llama-3.1-8B-Instruct":      ( 0.10,  0.10),
    "mistralai/Mistral-7B-Instruct-v0.3":    ( 0.07,  0.07),
    "mistralai/Mixtral-8x7B-Instruct-v0.1":  ( 0.54,  0.54),
    "mistralai/Mistral-Small-3.1-24B-Instruct-2503": (0.10, 0.30),

    # Ollama is local — handled explicitly in estimate_cost(), not here.
}

# Cross-region inference-profile prefixes used by Bedrock.
_BEDROCK_PROFILE_PREFIXES: tuple[str, ...] = ("us.", "eu.", "ap.", "au.")

# Curated set of representative models emitted in [COST COMPARISON] log lines.
# Each entry: (short_label, provider, pricing_key).  pricing_key must match a
# key in _PRICING exactly — no prefix stripping is applied here.
_COMPARISON_MODELS: list[tuple[str, str, str]] = [
    # (short_label,    provider,       pricing_key)
    ("nova-micro",    "bedrock",     "amazon.nova-micro-v1:0"),
    ("nova-lite",     "bedrock",     "amazon.nova-lite-v1:0"),
    ("haiku-3",       "bedrock",     "anthropic.claude-3-haiku-20240307-v1:0"),
    ("nova-pro",      "bedrock",     "amazon.nova-pro-v1:0"),
    ("haiku-4.5",     "bedrock",     "anthropic.claude-haiku-4-5-20250929-v1:0"),
    ("sonnet-4.5",    "bedrock",     "anthropic.claude-sonnet-4-5-20250929-v1:0"),
    ("opus-4",        "bedrock",     "anthropic.claude-opus-4-20250514-v1:0"),
    ("gpt-4.1-nano",  "openai",      "gpt-4.1-nano"),
    ("gpt-4o-mini",   "openai",      "gpt-4o-mini"),
    ("gpt-4.1-mini",  "openai",      "gpt-4.1-mini"),
    ("gpt-4.1",       "openai",      "gpt-4.1"),
    ("gpt-4o",        "openai",      "gpt-4o"),
    ("Qwen2.5-7B",    "huggingface", "Qwen/Qwen2.5-7B-Instruct"),
    ("Qwen2.5-72B",   "huggingface", "Qwen/Qwen2.5-72B-Instruct"),
    ("ollama",        "ollama",      ""),
]


def _normalise_model_id(model_id: str) -> str:
    """Strip a cross-region inference-profile prefix from a Bedrock model ID."""
    for prefix in _BEDROCK_PROFILE_PREFIXES:
        if model_id.startswith(prefix):
            return model_id[len(prefix):]
    return model_id


# ---------------------------------------------------------------------------
# LLM introspection helpers
# ---------------------------------------------------------------------------

def get_model_name(llm: BaseChatModel) -> str:
    """Return the model name/ID from any supported LangChain chat model.

    Tries the attributes used by each provider in priority order:
    - ``model_id``   — ChatBedrock
    - ``model_name`` — ChatOpenAI
    - ``model``      — ChatOllama
    """
    for attr in ("model_id", "model_name", "model"):
        value = getattr(llm, attr, None)
        if value and isinstance(value, str):
            return value
    return "unknown"


def get_provider_name(llm: BaseChatModel) -> str:
    """Infer the logical provider name from the LangChain model class."""
    class_name = type(llm).__name__

    if class_name == "ChatBedrock":
        return "bedrock"

    if class_name == "ChatOllama":
        return "ollama"

    if class_name == "ChatOpenAI":
        # Both GitHubCopilotProvider and HuggingFaceProvider use ChatOpenAI;
        # distinguish them by the base URL stored on the instance.
        base_url: str = getattr(llm, "openai_api_base", None) or ""
        if "githubcopilot.com" in base_url:
            return "github-copilot"
        if "huggingface.co" in base_url:
            return "huggingface"
        return "openai"

    return class_name.lower()


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------

def estimate_cost(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> Optional[float]:
    """Estimate the USD cost of a single LLM call.

    Args:
        provider:      Logical provider name (``"bedrock"``, ``"ollama"``, …).
        model:         Model name or ID as returned by :func:`get_model_name`.
        input_tokens:  Number of prompt tokens.
        output_tokens: Number of completion tokens.

    Returns:
        Cost in USD rounded to 8 decimal places, ``0.0`` for Ollama (local,
        free), or ``None`` when the model/provider is not in the pricing table
        (e.g. GitHub Copilot subscription or an unknown HuggingFace model).
    """
    if provider == "ollama":
        return 0.0

    # All other providers (including github-copilot) look up the pricing table.
    # For GitHub Copilot the returned value is the underlying model's list price
    # used as a reference — the caller labels it accordingly.
    normalised = _normalise_model_id(model)
    pricing = _PRICING.get(normalised)
    if pricing is None:
        return None

    input_cost = (input_tokens / 1_000_000) * pricing[0]
    output_cost = (output_tokens / 1_000_000) * pricing[1]
    return round(input_cost + output_cost, 8)


def _estimate_cost_breakdown(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> tuple[Optional[float], Optional[float]]:
    """Return ``(input_usd, output_usd)`` separately, or ``(None, None)`` when
    the model is not in the pricing table.  Ollama returns ``(0.0, 0.0)``.

    Input and output tokens are priced at different rates per million —
    output tokens are typically 3–5× more expensive than input tokens.
    This breakdown makes that difference visible in logs and audit events.
    """
    if provider == "ollama":
        return (0.0, 0.0)

    normalised = _normalise_model_id(model)
    pricing = _PRICING.get(normalised)
    if pricing is None:
        return (None, None)

    return (
        round((input_tokens / 1_000_000) * pricing[0], 8),
        round((output_tokens / 1_000_000) * pricing[1], 8),
    )


# ---------------------------------------------------------------------------
# Cost comparison logger
# ---------------------------------------------------------------------------

def log_cost_comparison(
    current_provider: str,
    current_model: str,
    input_tokens: int,
    output_tokens: int,
    agent_role: str = "unknown",
    prompt_text: Optional[str] = None,
) -> None:
    """Emit a ``[COST COMPARISON]`` line showing what the same token counts
    would cost across representative models, sorted cheapest → priciest.

    The currently-used model is marked with ``←`` in the output.
    When *prompt_text* is supplied, each entry also shows the local token
    count produced by that model's own tokenizer (where available).
    """
    normalised_current = _normalise_model_id(current_model)

    entries: list[tuple[float, str, str, bool, Optional[int]]] = []
    for label, provider, pricing_key in _COMPARISON_MODELS:
        if provider == "ollama":
            cost = 0.0
        else:
            pricing = _PRICING.get(pricing_key)
            if pricing is None:
                continue
            cost = round(
                (input_tokens / 1_000_000) * pricing[0]
                + (output_tokens / 1_000_000) * pricing[1],
                8,
            )
        is_current = pricing_key == normalised_current
        local_tok = _count_local_tokens(prompt_text, pricing_key) if prompt_text else None
        entries.append((cost, label, provider, is_current, local_tok))

    entries.sort(key=lambda e: e[0])

    parts = []
    for cost, label, provider, is_current, local_tok in entries:
        marker = " \u2190" if is_current else ""  # ← arrow
        local_str = f" local_prompt_tokens={local_tok}" if local_tok is not None else ""
        parts.append(f"${cost:.6f} {label}({provider}){local_str}{marker}")

    logger.info(
        "[COST COMPARISON] agent=%s in=%d out=%d | %s",
        agent_role,
        input_tokens,
        output_tokens,
        " | ".join(parts),
    )


# ---------------------------------------------------------------------------
# Structured cost logger
# ---------------------------------------------------------------------------

def log_llm_cost(
    llm: BaseChatModel,
    usage_metadata: dict,
    agent_role: str = "unknown",
    prompt_text: Optional[str] = None,
    response_text: Optional[str] = None,
    duration_ms: Optional[float] = None,
) -> None:
    """Extract token counts from *usage_metadata* and emit a ``[COST]`` log.

    *usage_metadata* is LangChain's normalised ``AIMessage.usage_metadata``
    dict (keys: ``input_tokens``, ``output_tokens``, ``total_tokens``).
    An empty or ``None`` dict logs a zero-token record.

    *duration_ms* is the wall-clock time (milliseconds) for the LLM network
    call, measured by the caller.  When supplied it is included in both the
    text log line and the structured ``llm.invoke`` audit event.

    When *prompt_text* or *response_text* are supplied the log line also
    includes ``local_prompt_tokens`` and ``local_response_tokens`` — counts
    produced by the model's own local tokenizer (tiktoken for OpenAI models,
    transformers for HuggingFace models) so you can compare API-reported
    counts against the local estimates.

    Args:
        llm:            The LangChain model that produced the response.
        usage_metadata: Token-count dict from ``AIMessage.usage_metadata``.
        agent_role:     Name of the calling agent node (e.g. ``"auditor"``).
        prompt_text:    Optional rendered prompt string for local prompt-token count.
        response_text:  Optional raw response string for local response-token count.
    """
    meta = usage_metadata or {}
    input_tokens: int = meta.get("input_tokens", 0)
    output_tokens: int = meta.get("output_tokens", 0)
    total_tokens: int = meta.get("total_tokens", input_tokens + output_tokens)

    provider = get_provider_name(llm)
    model = get_model_name(llm)
    cost = estimate_cost(provider, model, input_tokens, output_tokens)
    input_cost, output_cost = _estimate_cost_breakdown(provider, model, input_tokens, output_tokens)

    if cost is None:
        cost_str = "N/A (model not in pricing table)"
        input_cost_str = "N/A"
        output_cost_str = "N/A"
    elif provider == "github-copilot":
        cost_str = f"${cost:.6f} (list price)"
        input_cost_str = f"${input_cost:.6f} (list price)"
        output_cost_str = f"${output_cost:.6f} (list price)"
    else:
        cost_str = f"${cost:.6f}"
        input_cost_str = f"${input_cost:.6f}"
        output_cost_str = f"${output_cost:.6f}"

    local_prompt: Optional[int] = (
        _count_local_tokens(prompt_text, model) if prompt_text else None
    )
    local_response: Optional[int] = (
        _count_local_tokens(response_text, model) if response_text else None
    )
    local_prompt_str = str(local_prompt) if local_prompt is not None else "N/A"
    local_response_str = str(local_response) if local_response is not None else "N/A"

    logger.info(
        "[COST] provider=%s model=%s agent=%s "
        "input_tokens=%d output_tokens=%d total_tokens=%d "
        "input_cost_usd=%s output_cost_usd=%s estimated_cost_usd=%s "
        "local_prompt_tokens=%s local_response_tokens=%s"
        "%s",
        provider,
        model,
        agent_role,
        input_tokens,
        output_tokens,
        total_tokens,
        input_cost_str,
        output_cost_str,
        cost_str,
        local_prompt_str,
        local_response_str,
        f" duration_ms={duration_ms:.1f}" if duration_ms is not None else "",
    )

    # Emit a machine-readable structured event alongside the text log.
    try:
        from core.audit_logger import audit_event as _audit_event

        _audit_event(
            "llm.invoke",
            agent=agent_role,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            input_cost_usd=input_cost,
            output_cost_usd=output_cost,
            cost_usd=cost,
            cost_label=cost_str,
            local_prompt_tokens=local_prompt,
            local_response_tokens=local_response,
            duration_ms=duration_ms,
        )
    except Exception:
        pass  # Never let audit logging break the main path.

    log_cost_comparison(provider, model, input_tokens, output_tokens, agent_role, prompt_text)
