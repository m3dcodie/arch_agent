"""
GitHub Copilot LLM provider.

Uses the GitHub Copilot API (OpenAI-compatible) so that anyone with an active
GitHub Copilot subscription (Individual, Business, or Enterprise) can drive
ADAG without separate cloud credentials.

Authentication
--------------
GitHub Copilot issues short-lived *copilot tokens* (TTL ~30 min) that are
obtained by exchanging a long-lived OAuth token.  Two auth sources are supported,
tried in priority order:

1. ``GITHUB_COPILOT_TOKEN`` env var — a pre-obtained OAuth token (e.g. from
   ``gh auth token`` or a GitHub App).
2. ``~/.config/github-copilot/hosts.json`` — written by the ``gh`` CLI and the
   VS Code / JetBrains Copilot extension.  The file has the shape::

       {"github.com": {"oauth_token": "ghu_..."}}

The OAuth token is exchanged for a copilot token once at startup (and again on
each ``get_model()`` call, since tokens are short-lived).

Endpoint and models
-------------------
Base URL : https://api.githubcopilot.com
Default model : ``gpt-4o`` (available on all Copilot plans)

Other usable model IDs (subject to your plan):
  - ``gpt-4o``
  - ``gpt-4.1``
  - ``o3``
  - ``o4-mini``
  - ``claude-sonnet-4-5``   (Pro+ / Enterprise)
  - ``claude-sonnet-4``     (Pro+ / Enterprise)
  - ``gemini-2.0-flash``    (Pro+ / Enterprise)

Run ``/models`` in OpenCode or call ``list_copilot_models()`` below to get the
live list from the API.

Usage
-----
In ``.env``::

    LLM_PROVIDER=github-copilot
    GITHUB_COPILOT_TOKEN=ghu_your_oauth_token_here
    # Optional overrides:
    GITHUB_COPILOT_MODEL=gpt-4o
    GITHUB_COPILOT_TEMPERATURE=0.1
    GITHUB_COPILOT_MAX_TOKENS=4096
"""

from __future__ import annotations

import json
import os
import time
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
_TOKEN_EXCHANGE_URL = "https://api.github.com/copilot_internal/v2/token"

# Hosts file written by `gh` CLI / Copilot extensions
_HOSTS_FILE = Path.home() / ".config" / "github-copilot" / "hosts.json"

# Copilot tokens have a ~30-minute TTL; refresh with a 5-minute safety margin.
_TOKEN_TTL_SECONDS = 25 * 60


# ---------------------------------------------------------------------------
# Helper: resolve the OAuth token from available sources
# ---------------------------------------------------------------------------


def _resolve_oauth_token() -> str:
    """
    Return the GitHub OAuth token, trying env var first, then hosts.json.

    Raises:
        ValueError: If no token source is found.
    """
    # 1. Explicit env var
    token = os.getenv("GITHUB_COPILOT_TOKEN", "").strip()
    if token:
        return token

    # 2. gh CLI / VS Code extension hosts file
    if _HOSTS_FILE.exists():
        try:
            data = json.loads(_HOSTS_FILE.read_text())
            token = data.get("github.com", {}).get("oauth_token", "") or data.get(
                "github.com", {}
            ).get("user", {}).get("oauth_token", "")
            if token:
                return token
        except (json.JSONDecodeError, AttributeError):
            pass

    raise ValueError(
        "No GitHub Copilot OAuth token found.\n"
        "Supply one via the GITHUB_COPILOT_TOKEN environment variable, "
        "or authenticate with the GitHub CLI:\n"
        "  gh auth login --scopes 'copilot'\n"
        "  export GITHUB_COPILOT_TOKEN=$(gh auth token)"
    )


# ---------------------------------------------------------------------------
# Helper: exchange OAuth token for a short-lived copilot token
# ---------------------------------------------------------------------------


def _exchange_for_copilot_token(oauth_token: str) -> tuple[str, float]:
    """
    Exchange a GitHub OAuth token for a short-lived Copilot API token.

    Returns:
        (copilot_token, expiry_timestamp)

    Raises:
        ValueError: On HTTP or JSON errors.
    """
    headers = {
        "Authorization": f"token {oauth_token}",
        "Accept": "application/json",
        "Editor-Version": "adag/0.1.0",
        "Copilot-Integration-Id": "vscode-chat",
    }
    try:
        resp = requests.get(_TOKEN_EXCHANGE_URL, headers=headers, timeout=10)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        raise ValueError(
            f"GitHub Copilot token exchange failed ({exc.response.status_code}): "
            f"{exc.response.text}"
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise ValueError(
            f"GitHub Copilot token exchange request failed: {exc}"
        ) from exc

    data = resp.json()
    copilot_token: str = data.get("token", "")
    if not copilot_token:
        raise ValueError(f"Unexpected response from Copilot token endpoint: {data}")

    # The API returns expires_at as a Unix timestamp (int) in some versions
    # and as an ISO-8601 string in others.  Normalise to float epoch seconds.
    expires_raw = data.get("expires_at")
    if isinstance(expires_raw, (int, float)):
        expiry = float(expires_raw)
    else:
        expiry = time.time() + _TOKEN_TTL_SECONDS

    return copilot_token, expiry


# ---------------------------------------------------------------------------
# Provider implementation
# ---------------------------------------------------------------------------


class GitHubCopilotProvider(LLMProvider):
    """
    GitHub Copilot LLM provider.

    Wraps the Copilot API (OpenAI-compatible) so any Copilot subscriber can
    use ADAG without additional cloud credentials or API keys.
    """

    DEFAULT_MODEL = "gpt-4o"

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

        # Resolve OAuth token eagerly so misconfiguration is caught at startup
        self._oauth_token: str = oauth_token or _resolve_oauth_token()

        # Copilot token cache (token, expiry epoch)
        self._copilot_token: str = ""
        self._copilot_token_expiry: float = 0.0

        self.validate_config()

    # ------------------------------------------------------------------
    # Internal: token management
    # ------------------------------------------------------------------

    def _get_copilot_token(self) -> str:
        """Return a valid (non-expired) Copilot token, refreshing if needed."""
        if time.time() >= self._copilot_token_expiry - 60:
            self._copilot_token, self._copilot_token_expiry = (
                _exchange_for_copilot_token(self._oauth_token)
            )
        return self._copilot_token

    # ------------------------------------------------------------------
    # LLMProvider interface
    # ------------------------------------------------------------------

    def get_model(self, **kwargs) -> BaseChatModel:
        """
        Return a ChatOpenAI instance pointing at the Copilot API.

        A fresh copilot token is obtained (or reused if still valid) on every
        call, so long-running processes automatically handle token rotation.

        ``model`` in kwargs (forwarded by graph._get_llm_for_role when
        INTAKE_MODEL / AUDITOR_MODEL env vars are set) overrides the provider
        default, enabling per-agent model selection exactly as with the
        HuggingFace and Ollama providers.
        """
        copilot_token = self._get_copilot_token()

        # Required Copilot headers — merged first so caller-supplied
        # default_headers cannot accidentally drop them.
        required_headers = {
            "Editor-Version": "adag/0.1.0",
            "Copilot-Integration-Id": "vscode-chat",
            "X-GitHub-Api-Version": "2025-04-01",
        }
        caller_headers = kwargs.pop("default_headers", {})
        merged_headers = {**required_headers, **caller_headers}

        config = {
            "model": self.model,  # provider default; overridden below if caller passes model=
            "openai_api_key": copilot_token,
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
        Validate that an OAuth token exists and the Copilot token exchange works.

        Raises:
            ValueError: If the token is missing or the exchange fails.
        """
        # Trigger a token exchange to validate credentials at startup
        self._get_copilot_token()
        return True


# ---------------------------------------------------------------------------
# Auto-register when this module is imported
# ---------------------------------------------------------------------------

LLMFactory.register_provider("github-copilot", GitHubCopilotProvider)
