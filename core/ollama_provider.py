"""
Ollama LLM provider implementation.
Allows using locally-running Ollama models for testing without cloud credentials.
"""
import os
import requests
from typing import Optional
from langchain_ollama import ChatOllama
from langchain_core.language_models import BaseChatModel

from core.llm_provider import LLMProvider, LLMFactory


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider"""

    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize Ollama provider.

        Args:
            model: Ollama model name (e.g., 'deepseek-r1:8b')
            base_url: Ollama server URL (default: http://localhost:11434)
            **kwargs: Additional configuration passed to ChatOllama
        """
        self.model = model or os.getenv("OLLAMA_MODEL", "deepseek-r1:8b")
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

        # -1 = unlimited tokens (correct for local models — no cost concern).
        # reasoning=False disables the internal reasoning chain on qwen3/deepseek-r1
        # thinking models — without this they spend minutes generating <think> blocks
        # before producing any output, which looks like a hang.
        # OLLAMA_TIMEOUT is a safety net in case the model hangs completely.
        defaults = {
            "num_predict": int(os.getenv("OLLAMA_NUM_PREDICT", "-1")),
            "timeout": int(os.getenv("OLLAMA_TIMEOUT", "300")),
            "reasoning": os.getenv("OLLAMA_THINK", "false").lower() == "true",
        }
        # Caller kwargs override defaults
        defaults.update(kwargs)
        self.extra_config = defaults

        self.validate_config()

    def get_model(self, **kwargs) -> BaseChatModel:
        """
        Get ChatOllama model instance.

        Args:
            **kwargs: Override configuration for this specific model instance

        Returns:
            ChatOllama: Configured Ollama chat model
        """
        config = {
            "model": self.model,
            "base_url": self.base_url,
            **self.extra_config,
            **kwargs,
        }
        return ChatOllama(**config)

    def get_provider_name(self) -> str:
        return "ollama"

    def validate_config(self) -> bool:
        """
        Validate Ollama is reachable and the model is available.

        Raises:
            ValueError: If Ollama server is unreachable or model is not found
        """
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
        except requests.exceptions.ConnectionError:
            raise ValueError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Make sure Ollama is running (`ollama serve`)."
            )
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Ollama health check failed: {e}")

        available_models = [m["name"] for m in response.json().get("models", [])]
        # Accept both 'deepseek-r1:8b' and 'deepseek-r1' (untagged) forms
        model_base = self.model.split(":")[0]
        matched = any(
            m == self.model or m.startswith(model_base + ":")
            for m in available_models
        )
        if not matched:
            raise ValueError(
                f"Model '{self.model}' not found in Ollama. "
                f"Available models: {available_models}. "
                f"Pull it with: ollama pull {self.model}"
            )

        return True


# Auto-register when this module is imported
LLMFactory.register_provider("ollama", OllamaProvider)
