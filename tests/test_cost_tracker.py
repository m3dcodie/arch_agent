"""
Unit tests for core.cost_tracker — pricing table, model/provider introspection,
cost estimation, and structured log output.
"""

import logging
from unittest.mock import MagicMock

import pytest

from core.cost_tracker import (
    _normalise_model_id,
    estimate_cost,
    get_model_name,
    get_provider_name,
    log_cost_comparison,
    log_llm_cost,
)


# ---------------------------------------------------------------------------
# _normalise_model_id
# ---------------------------------------------------------------------------


class TestNormaliseModelId:
    def test_strips_us_prefix(self):
        assert _normalise_model_id("us.anthropic.claude-sonnet-4-5-20250929-v1:0") == (
            "anthropic.claude-sonnet-4-5-20250929-v1:0"
        )

    def test_strips_eu_prefix(self):
        assert _normalise_model_id("eu.amazon.nova-pro-v1:0") == "amazon.nova-pro-v1:0"

    def test_strips_ap_prefix(self):
        assert _normalise_model_id("ap.amazon.nova-lite-v1:0") == "amazon.nova-lite-v1:0"

    def test_strips_au_prefix(self):
        assert _normalise_model_id("au.anthropic.claude-haiku-3-5-20241022-v1:0") == (
            "anthropic.claude-haiku-3-5-20241022-v1:0"
        )

    def test_passthrough_without_prefix(self):
        assert (
            _normalise_model_id("anthropic.claude-sonnet-4-5-20250929-v1:0")
            == "anthropic.claude-sonnet-4-5-20250929-v1:0"
        )


# ---------------------------------------------------------------------------
# get_model_name
# ---------------------------------------------------------------------------


class TestGetModelName:
    def test_bedrock_model_id(self):
        llm = MagicMock(spec=[])
        llm.model_id = "anthropic.claude-sonnet-4-5-20250929-v1:0"
        assert get_model_name(llm) == "anthropic.claude-sonnet-4-5-20250929-v1:0"

    def test_openai_model_name(self):
        llm = MagicMock(spec=[])
        llm.model_name = "gpt-4.1"
        assert get_model_name(llm) == "gpt-4.1"

    def test_ollama_model(self):
        llm = MagicMock(spec=[])
        llm.model = "deepseek-r1:8b"
        assert get_model_name(llm) == "deepseek-r1:8b"

    def test_fallback_unknown(self):
        llm = MagicMock(spec=[])
        assert get_model_name(llm) == "unknown"


# ---------------------------------------------------------------------------
# get_provider_name
# ---------------------------------------------------------------------------


def _mock_llm(class_name: str, base_url: str = "") -> MagicMock:
    llm = MagicMock()
    type(llm).__name__ = class_name
    llm.openai_api_base = base_url
    return llm


class TestGetProviderName:
    def test_bedrock(self):
        assert get_provider_name(_mock_llm("ChatBedrock")) == "bedrock"

    def test_ollama(self):
        assert get_provider_name(_mock_llm("ChatOllama")) == "ollama"

    def test_github_copilot(self):
        assert (
            get_provider_name(_mock_llm("ChatOpenAI", "https://api.githubcopilot.com"))
            == "github-copilot"
        )

    def test_huggingface(self):
        assert (
            get_provider_name(_mock_llm("ChatOpenAI", "https://router.huggingface.co/v1"))
            == "huggingface"
        )

    def test_openai_direct(self):
        assert get_provider_name(_mock_llm("ChatOpenAI", "")) == "openai"

    def test_unknown_class(self):
        assert get_provider_name(_mock_llm("SomeCustomLLM")) == "somecustomllm"


# ---------------------------------------------------------------------------
# estimate_cost
# ---------------------------------------------------------------------------


class TestEstimateCost:
    def test_known_bedrock_model(self):
        cost = estimate_cost(
            "bedrock",
            "anthropic.claude-sonnet-4-5-20250929-v1:0",
            input_tokens=1_000,
            output_tokens=500,
        )
        # (1000/1M * $3.00) + (500/1M * $15.00) = $0.003 + $0.0075 = $0.0105
        assert cost == pytest.approx(0.0105, rel=1e-6)

    def test_bedrock_inference_profile_prefix_stripped(self):
        cost_direct = estimate_cost(
            "bedrock",
            "anthropic.claude-sonnet-4-5-20250929-v1:0",
            1_000,
            500,
        )
        cost_profile = estimate_cost(
            "bedrock",
            "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
            1_000,
            500,
        )
        assert cost_direct == cost_profile

    def test_nova_pro(self):
        cost = estimate_cost("bedrock", "amazon.nova-pro-v1:0", 1_000_000, 1_000_000)
        # $0.80 + $3.20 = $4.00
        assert cost == pytest.approx(4.00, rel=1e-6)

    def test_ollama_always_zero(self):
        assert estimate_cost("ollama", "deepseek-r1:8b", 5_000, 2_000) == 0.0

    def test_github_copilot_known_model_returns_list_price(self):
        cost = estimate_cost("github-copilot", "claude-sonnet-4.5", 1_000, 500)
        # Same list price as Anthropic: (1000/1M * $3.00) + (500/1M * $15.00)
        assert cost == pytest.approx(0.0105, rel=1e-6)

    def test_github_copilot_unknown_model_returns_none(self):
        assert estimate_cost("github-copilot", "some-future-model", 1_000, 500) is None

    def test_unknown_model_returns_none(self):
        assert estimate_cost("bedrock", "amazon.some-future-model-v99:0", 1_000, 500) is None

    def test_unknown_huggingface_model_returns_none(self):
        assert estimate_cost("huggingface", "some-org/some-unknown-model-v9", 1_000, 500) is None

    def test_gpt4o_mini(self):
        cost = estimate_cost("openai", "gpt-4o-mini", 1_000_000, 1_000_000)
        # $0.15 + $0.60 = $0.75
        assert cost == pytest.approx(0.75, rel=1e-6)


# ---------------------------------------------------------------------------
# log_llm_cost
# ---------------------------------------------------------------------------


class TestLogLlmCost:
    def test_bedrock_cost_logged(self, caplog):
        llm = _mock_llm("ChatBedrock")
        llm.model_id = "anthropic.claude-sonnet-4-5-20250929-v1:0"

        with caplog.at_level(logging.INFO, logger="core.cost_tracker"):
            log_llm_cost(
                llm,
                {"input_tokens": 1000, "output_tokens": 500, "total_tokens": 1500},
                agent_role="auditor",
            )

        assert len(caplog.records) == 2  # [COST] + [COST COMPARISON]
        msg = caplog.records[0].message
        assert "[COST]" in msg
        assert "provider=bedrock" in msg
        assert "agent=auditor" in msg
        assert "input_tokens=1000" in msg
        assert "output_tokens=500" in msg
        assert "total_tokens=1500" in msg
        assert "$" in msg

    def test_ollama_cost_is_zero(self, caplog):
        llm = _mock_llm("ChatOllama")
        llm.model = "deepseek-r1:8b"

        with caplog.at_level(logging.INFO, logger="core.cost_tracker"):
            log_llm_cost(llm, {"input_tokens": 200, "output_tokens": 100})

        msg = caplog.records[0].message
        assert "provider=ollama" in msg
        assert "$0.000000" in msg

    def test_github_copilot_subscription_label(self, caplog):
        llm = _mock_llm("ChatOpenAI", "https://api.githubcopilot.com")
        llm.model_name = "claude-sonnet-4.5"

        with caplog.at_level(logging.INFO, logger="core.cost_tracker"):
            log_llm_cost(llm, {"input_tokens": 800, "output_tokens": 300})

        msg = caplog.records[0].message
        assert "provider=github-copilot" in msg
        assert "(list price)" in msg
        assert "$" in msg

    def test_unknown_model_logs_not_in_table(self, caplog):
        llm = _mock_llm("ChatBedrock")
        llm.model_id = "amazon.some-future-model-v99:0"

        with caplog.at_level(logging.INFO, logger="core.cost_tracker"):
            log_llm_cost(llm, {"input_tokens": 500, "output_tokens": 100})

        msg = caplog.records[0].message
        assert "N/A (model not in pricing table)" in msg

    def test_empty_usage_metadata_logs_zeros(self, caplog):
        llm = _mock_llm("ChatBedrock")
        llm.model_id = "amazon.nova-micro-v1:0"

        with caplog.at_level(logging.INFO, logger="core.cost_tracker"):
            log_llm_cost(llm, {})

        msg = caplog.records[0].message
        assert "input_tokens=0" in msg
        assert "output_tokens=0" in msg

    def test_none_usage_metadata_handled(self, caplog):
        llm = _mock_llm("ChatOllama")
        llm.model = "llama3"

        with caplog.at_level(logging.INFO, logger="core.cost_tracker"):
            log_llm_cost(llm, None)  # type: ignore[arg-type]

        assert len(caplog.records) == 2  # [COST] + [COST COMPARISON]


# ---------------------------------------------------------------------------
# log_cost_comparison
# ---------------------------------------------------------------------------


class TestLogCostComparison:
    def test_emits_comparison_line(self, caplog):
        with caplog.at_level(logging.INFO, logger="core.cost_tracker"):
            log_cost_comparison("bedrock", "amazon.nova-micro-v1:0", 1_000, 500, "auditor")

        assert len(caplog.records) == 1
        msg = caplog.records[0].message
        assert "[COST COMPARISON]" in msg
        assert "agent=auditor" in msg
        assert "in=1000" in msg
        assert "out=500" in msg

    def test_current_model_marked_with_arrow(self, caplog):
        with caplog.at_level(logging.INFO, logger="core.cost_tracker"):
            log_cost_comparison("openai", "gpt-4.1", 1_000, 500, "auditor")

        msg = caplog.records[0].message
        assert "gpt-4.1(openai) \u2190" in msg

    def test_bedrock_prefix_stripped_for_current_match(self, caplog):
        with caplog.at_level(logging.INFO, logger="core.cost_tracker"):
            log_cost_comparison(
                "bedrock", "us.amazon.nova-micro-v1:0", 1_000, 500, "auditor"
            )

        msg = caplog.records[0].message
        assert "nova-micro(bedrock) \u2190" in msg

    def test_sorted_cheapest_to_priciest(self, caplog):
        with caplog.at_level(logging.INFO, logger="core.cost_tracker"):
            log_cost_comparison("openai", "gpt-4.1", 1_000, 500, "auditor")

        msg = caplog.records[0].message
        # ollama ($0) should appear before opus-4 (most expensive)
        assert msg.index("ollama") < msg.index("opus-4")
        # nova-micro should appear before gpt-4.1
        assert msg.index("nova-micro") < msg.index("gpt-4.1")

    def test_ollama_is_zero_cost(self, caplog):
        with caplog.at_level(logging.INFO, logger="core.cost_tracker"):
            log_cost_comparison("ollama", "deepseek-r1:8b", 5_000, 2_000, "auditor")

        msg = caplog.records[0].message
        assert "$0.000000 ollama(ollama)" in msg

    def test_unknown_current_model_no_arrow(self, caplog):
        with caplog.at_level(logging.INFO, logger="core.cost_tracker"):
            log_cost_comparison("bedrock", "amazon.some-future-v99:0", 1_000, 500, "auditor")

        msg = caplog.records[0].message
        assert "\u2190" not in msg
