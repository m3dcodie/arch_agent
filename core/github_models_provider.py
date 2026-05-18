"""
GitHub Models LLM provider.

Uses the GitHub Models inference API — the officially supported endpoint for
programmatic AI model access using a standard GitHub Personal Access Token.

Docs: https://docs.github.com/en/github-models/quickstart

Authentication
--------------
A GitHub **fine-grained** Personal Access Token with the ``Models`` (read)
permission is required.

Create one at: https://github.com/settings/personal-access-tokens/new

  1. Under **Account permissions** enable:
     - ``GitHub Copilot`` → Read (gives chat + models API access)
     - ``Models`` → Read (direct Models inference API)
  2. Set an expiry and click **Generate token**.

Token sources (tried in priority order):

1. ``GITHUB_MODELS_TOKEN`` env var (recommended)
2. ``GITHUB_TOKEN`` env var (works in GitHub Actions automatically)

Endpoint and models
-------------------
Base URL : https://models.github.ai/inference
API ver  : 2022-11-28

Model names use the ``vendor/model-id`` format::

    openai/gpt-4.1
    openai/gpt-4o-mini
    anthropic/claude-sonnet-4-5
    meta/llama-3.3-70b-instruct
    deepseek/deepseek-r1

Browse the full catalog: https://github.com/marketplace?type=models

Usage
-----
In ``.env``::

    LLM_PROVIDER=github-models
    GITHUB_MODELS_TOKEN=ghp_your_classic_pat_here
    GITHUB_MODELS_MODEL=openai/gpt-4.1
    INTAKE_MODEL=openai/gpt-4o-mini
    AUDITOR_MODEL=openai/gpt-4.1
"""

from __future__ import annotations

import os
from typing import Optional

import requests
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel

from core.llm_provider import LLMProvider, LLMFactory

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GITHUB_MODELS_BASE_URL = "https://models.github.ai/inference"
GITHUB_MODELS_API_VERSION = "2022-11-28"


# ---------------------------------------------------------------------------
# Helper: resolve the PAT from available sources
# ---------------------------------------------------------------------------


def _resolve_token() -> str:
    """
    Return the GitHub token, trying GITHUB_MODELS_TOKEN then GITHUB_TOKEN.

    Raises:
        ValueError: If no token is found.
    """
    token = os.getenv("GITHUB_MODELS_TOKEN", "").strip()
    if token:
        return token

    # GITHUB_TOKEN is set automatically in GitHub Actions
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        return token

    raise ValueError(
        "No GitHub token found for GitHub Models.\n"
        "Create a fine-grained PAT at:\n"
        "  https://github.com/settings/personal-access-tokens/new\n"
        "Under Account permissions enable:\n"
        "  - GitHub Copilot → Read\n"
        "  - Models → Read\n"
        "Then set: GITHUB_MODELS_TOKEN=github_pat_your_token_here"
    )


# ---------------------------------------------------------------------------
# Helper: validate the token against the GitHub Models API
# ---------------------------------------------------------------------------


def _validate_token(token: str) -> None:
    """
    Confirm the token is accepted by the GitHub API.

    Uses the standard ``/user`` endpoint (works with fine-grained PATs) rather
    than a Models-specific endpoint, since the Models API does not expose a
    public model-listing endpoint for validation.

    Raises:
        ValueError: On auth failure or connectivity error.
    """
    try:
        resp = requests.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": GITHUB_MODELS_API_VERSION,
            },
            timeout=10,
        )
        if resp.status_code == 401:
            raise ValueError(
                "GitHub token is invalid or expired.\n"
                "Regenerate your fine-grained PAT at: https://github.com/settings/personal-access-tokens"
            )
        if resp.status_code == 403:
            raise ValueError(
                "GitHub Models access denied (HTTP 403).\n"
                "Ensure your fine-grained PAT has these Account permissions:\n"
                "  - GitHub Copilot → Read\n"
                "  - Models → Read\n"
                "Create one at: https://github.com/settings/personal-access-tokens/new"
            )
        resp.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise ValueError(f"GitHub API unreachable: {exc}") from exc


# ---------------------------------------------------------------------------
# Provider implementation
# ---------------------------------------------------------------------------


class GitHubModelsProvider(LLMProvider):
    """
    GitHub Models LLM provider.

    Connects to https://models.github.ai/inference using a GitHub PAT with
    the ``models`` scope.  The API is OpenAI-compatible so ChatOpenAI is used
    as the client.
    """

    DEFAULT_MODEL = "openai/gpt-4.1"

    def __init__(
        self,
        model: Optional[str] = None,
        token: Optional[str] = None,
        **kwargs,
    ):
        self.model = model or os.getenv("GITHUB_MODELS_MODEL", self.DEFAULT_MODEL)
        self.temperature = float(os.getenv("GITHUB_MODELS_TEMPERATURE", os.getenv("LLM_TEMPERATURE", "0")))
        self.max_tokens = int(os.getenv("GITHUB_MODELS_MAX_TOKENS", os.getenv("LLM_MAX_TOKENS", "4096")))
        self.extra_kwargs = kwargs

        self._token: str = token or _resolve_token()
        self.validate_config()

    # ------------------------------------------------------------------
    # LLMProvider interface
    # ------------------------------------------------------------------

    def get_model(self, **kwargs) -> BaseChatModel:
        """
        Return a ChatOpenAI instance pointing at the GitHub Models API.

        ``model`` in kwargs (forwarded by graph._get_llm_for_role when
        INTAKE_MODEL / AUDITOR_MODEL env vars are set) overrides the provider
        default, enabling per-agent model selection.
        """
        config = {
            "model": self.model,
            "openai_api_key": self._token,
            "openai_api_base": GITHUB_MODELS_BASE_URL,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "default_headers": {
                "X-GitHub-Api-Version": GITHUB_MODELS_API_VERSION,
            },
            "request_timeout": int(os.getenv("GITHUB_MODELS_TIMEOUT", "120")),
            **self.extra_kwargs,
            **kwargs,  # model=INTAKE_MODEL / AUDITOR_MODEL lands here
        }
        return ChatOpenAI(**config)

    def get_provider_name(self) -> str:
        return "github-models"

    def validate_config(self) -> bool:
        """
        Validate the token against the GitHub Models API.

        Raises:
            ValueError: If the token is missing or rejected.
        """
        _validate_token(self._token)
        return True


# ---------------------------------------------------------------------------
# Auto-register when this module is imported
# ---------------------------------------------------------------------------

LLMFactory.register_provider("github-models", GitHubModelsProvider)
