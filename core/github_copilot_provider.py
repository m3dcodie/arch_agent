"""
GitHub Copilot LLM provider.

Uses the GitHub Copilot API (OpenAI-compatible) so that anyone with an active
GitHub Copilot subscription (Individual, Business, or Enterprise) can drive
ADAG without separate cloud credentials.

Authentication
--------------
The OAuth token from ``gh auth login`` is used directly as the Bearer token
against ``api.githubcopilot.com`` — no internal token exchange is required.

Two token sources are supported, tried in priority order:

1. ``GITHUB_COPILOT_TOKEN`` env var — set this to the output of::

       gh auth status --show-token

2. ``~/.config/gh/hosts.yml`` — written by the ``gh`` CLI automatically.

Endpoint and models
-------------------
Base URL : https://api.githubcopilot.com
Default model : ``claude-sonnet-4.5``

Available model IDs (run ``adag models`` or check the API)::

    gpt-4.1               gpt-4.1-2025-04-14
    gpt-4o-mini           gpt-4o-mini-2024-07-18
    claude-sonnet-4       claude-sonnet-4.5
    claude-haiku-4.5      claude-opus-4.5

Usage
-----
In ``.env``::

    LLM_PROVIDER=github-copilot
    GITHUB_COPILOT_TOKEN=gho_your_token_here
    GITHUB_COPILOT_MODEL=claude-sonnet-4.5
    INTAKE_MODEL=gpt-4.1
    AUDITOR_MODEL=claude-sonnet-4.5
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import requests
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel

from core.llm_provider import LLMProvider, LLMFactory

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COPILOT_BASE_URL = "https://api.githubcopilot.com"

# gh CLI hosts file (written by `gh auth login`)
_GH_HOSTS_FILE = Path.home() / ".config" / "gh" / "hosts.yml"

# Legacy Copilot extension hosts file
_COPILOT_HOSTS_FILE = Path.home() / ".config" / "github-copilot" / "hosts.json"

_REQUIRED_HEADERS = {
    "Editor-Version": "vscode/1.99.0",
    "Editor-Plugin-Version": "copilot-chat/0.26.0",
    "Copilot-Integration-Id": "vscode-chat",
}


# ---------------------------------------------------------------------------
# Helper: resolve the OAuth token from available sources
# ---------------------------------------------------------------------------


def _resolve_oauth_token() -> str:
    """
    Return the GitHub OAuth token, trying env var first, then gh CLI hosts file.

    Raises:
        ValueError: If no token source is found.
    """
    # 1. Explicit env var (highest priority)
    token = os.getenv("GITHUB_COPILOT_TOKEN", "").strip()
    if token:
        return token

    # 2. gh CLI hosts.yml  (written by `gh auth login`)
    if _GH_HOSTS_FILE.exists():
        try:
            import yaml  # optional dep — only needed if env var not set

            data = yaml.safe_load(_GH_HOSTS_FILE.read_text()) or {}
            token = data.get("github.com", {}).get("oauth_token", "")
            if token:
                return token
        except Exception:
            pass

    # 3. Legacy Copilot extension hosts.json
    if _COPILOT_HOSTS_FILE.exists():
        try:
            data = json.loads(_COPILOT_HOSTS_FILE.read_text())
            token = data.get("github.com", {}).get("oauth_token", "")
            if token:
                return token
        except Exception:
            pass

    raise ValueError(
        "No GitHub Copilot token found.\n"
        "Run the following and add the token to your .env:\n"
        "  gh auth login --scopes 'copilot'\n"
        "  gh auth status --show-token\n"
        "Then set: GITHUB_COPILOT_TOKEN=<token>"
    )


# ---------------------------------------------------------------------------
# Helper: validate the token works against the Copilot API
# ---------------------------------------------------------------------------


def _validate_token(token: str) -> None:
    """
    Hit the /models endpoint to confirm the token is accepted.

    Raises:
        ValueError: On auth failure or connectivity error.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        **_REQUIRED_HEADERS,
    }
    try:
        resp = requests.get(f"{COPILOT_BASE_URL}/models", headers=headers, timeout=10)
        if resp.status_code == 401:
            raise ValueError(
                "GitHub Copilot token is invalid or expired.\n"
                "Run: gh auth login --scopes 'copilot' && gh auth status --show-token\n"
                "Then update GITHUB_COPILOT_TOKEN in your .env"
            )
        resp.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise ValueError(f"GitHub Copilot API unreachable: {exc}") from exc


# ---------------------------------------------------------------------------
# Provider implementation
# ---------------------------------------------------------------------------


class GitHubCopilotProvider(LLMProvider):
    """
    GitHub Copilot LLM provider.

    Uses the OAuth token directly as a Bearer token against the Copilot API
    (OpenAI-compatible). No internal token exchange required.
    """

    DEFAULT_MODEL = "claude-sonnet-4.5"

    def __init__(
        self,
        model: Optional[str] = None,
        oauth_token: Optional[str] = None,
        **kwargs,
    ):
        self.model = model or os.getenv("GITHUB_COPILOT_MODEL", self.DEFAULT_MODEL)
        self.temperature = float(os.getenv("GITHUB_COPILOT_TEMPERATURE", "0.1"))
        self.max_tokens = int(os.getenv("GITHUB_COPILOT_MAX_TOKENS", "4096"))
        self.extra_kwargs = kwargs

        # Resolve token eagerly — fail fast on misconfiguration
        self._token: str = oauth_token or _resolve_oauth_token()

        self.validate_config()

    # ------------------------------------------------------------------
    # LLMProvider interface
    # ------------------------------------------------------------------

    def get_model(self, **kwargs) -> BaseChatModel:
        """
        Return a ChatOpenAI instance pointing at the Copilot API.

        ``model`` in kwargs (forwarded by graph._get_llm_for_role when
        INTAKE_MODEL / AUDITOR_MODEL env vars are set) overrides the provider
        default, enabling per-agent model selection.
        """
        # Required Copilot headers — caller headers are merged in but cannot
        # override the required ones.
        caller_headers = kwargs.pop("default_headers", {})
        merged_headers = {**_REQUIRED_HEADERS, **caller_headers}

        config = {
            "model": self.model,  # overridden by model= kwarg below if set
            "openai_api_key": self._token,
            "openai_api_base": COPILOT_BASE_URL,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "default_headers": merged_headers,
            **self.extra_kwargs,
            **kwargs,  # model=INTAKE_MODEL / AUDITOR_MODEL lands here
        }
        return ChatOpenAI(**config)

    def get_provider_name(self) -> str:
        return "github-copilot"

    def validate_config(self) -> bool:
        """
        Validate the token against the Copilot API.

        Raises:
            ValueError: If the token is missing or rejected.
        """
        _validate_token(self._token)
        return True


# ---------------------------------------------------------------------------
# Auto-register when this module is imported
# ---------------------------------------------------------------------------

LLMFactory.register_provider("github-copilot", GitHubCopilotProvider)
