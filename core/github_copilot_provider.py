"""
GitHub Copilot LLM provider.

Uses the GitHub Copilot API (OpenAI-compatible) so that anyone with an active
GitHub Copilot subscription (Individual, Business, or Enterprise) can drive
ADAG without separate cloud credentials.

Authentication
--------------
The GitHub OAuth token (``gho_…``) is used directly as the Bearer token
against ``api.githubcopilot.com``.  The token **must** have the ``copilot``
OAuth scope — grant it with::

    gh auth login --scopes 'copilot'

Token sources (tried in priority order):

1. ``GITHUB_COPILOT_TOKEN`` env var — set to the output of::

       gh auth status --show-token

2. ``~/.config/gh/hosts.yml`` — written by ``gh auth login`` automatically.

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
# Helper: validate the token scope and Copilot API access
# ---------------------------------------------------------------------------


def _validate_token(token: str) -> None:
    """
    Check the token has the ``copilot`` scope and that the Copilot API accepts it.

    Uses the GitHub meta API to inspect scopes (avoids consuming quota) then
    confirms the Copilot /models endpoint is reachable.

    Raises:
        ValueError: On missing scope, auth failure, or connectivity error.
    """
    # Step 1: check scopes via GitHub API (cheap — no LLM quota used).
    try:
        scope_resp = requests.get(
            "https://api.github.com/",
            headers={"Authorization": f"token {token}", "Accept": "application/json"},
            timeout=10,
        )
        granted_scopes = [
            s.strip()
            for s in scope_resp.headers.get("X-OAuth-Scopes", "").split(",")
            if s.strip()
        ]
        if scope_resp.ok and granted_scopes and "copilot" not in granted_scopes:
            raise ValueError(
                "GitHub token is missing the 'copilot' OAuth scope.\n"
                "Re-authenticate with the required scope:\n"
                "  gh auth login --scopes 'copilot'\n"
                "  gh auth status --show-token\n"
                "Then update GITHUB_COPILOT_TOKEN in your .env"
            )
    except requests.exceptions.RequestException:
        pass  # offline / firewall — skip scope check, let /models validate

    # Step 2: confirm the Copilot chat API accepts the token.
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
        if resp.status_code == 403:
            raise ValueError(
                "GitHub Copilot API access denied (HTTP 403).\n"
                "Ensure:\n"
                "  1. Your token has the 'copilot' scope:  gh auth login --scopes 'copilot'\n"
                "  2. Your account has an active Copilot Individual/Business/Enterprise plan.\n"
                "  3. Your organisation policy allows API access."
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
    (OpenAI-compatible).  The token must have the ``copilot`` OAuth scope.
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

        # Resolve token eagerly — fail fast on misconfiguration.
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
        caller_headers = kwargs.pop("default_headers", {})
        merged_headers = {**_REQUIRED_HEADERS, **caller_headers}

        config = {
            "model": self.model,
            "openai_api_key": self._token,
            "openai_api_base": COPILOT_BASE_URL,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "default_headers": merged_headers,
            "request_timeout": int(os.getenv("GITHUB_COPILOT_TIMEOUT", "120")),
            **self.extra_kwargs,
            **kwargs,  # model=INTAKE_MODEL / AUDITOR_MODEL lands here
        }
        return ChatOpenAI(**config)

    def get_provider_name(self) -> str:
        return "github-copilot"

    def validate_config(self) -> bool:
        """
        Validate that the token has the required scope and the API is reachable.

        Raises:
            ValueError: If the token is missing, lacks the copilot scope, or
                        the API rejects it.
        """
        _validate_token(self._token)
        return True


# ---------------------------------------------------------------------------
# Auto-register when this module is imported
# ---------------------------------------------------------------------------

LLMFactory.register_provider("github-copilot", GitHubCopilotProvider)

