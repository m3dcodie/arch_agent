"""
Hugging Face LLM provider via the HF router (OpenAI-compatible endpoint).
Uses the HF_ROUTER_BASE_URL env var (default: https://router.huggingface.co/v1).
"""

import os
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel

from core.llm_provider import LLMProvider, LLMFactory


class HuggingFaceProvider(LLMProvider):
    """Hugging Face serverless inference provider via the HF router."""

    DEFAULT_MODEL = "Qwen/Qwen2.5-7B-Instruct"

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        **kwargs,
    ):
        self.model = model or os.getenv("HF_MODEL", self.DEFAULT_MODEL)
        self.api_key = api_key or os.getenv("HF_TOKEN", "")
        self.base_url = os.getenv("HF_ROUTER_BASE_URL", "https://router.huggingface.co/v1")
        self.temperature = float(os.getenv("HF_TEMPERATURE", "0.1"))
        self.max_tokens = int(os.getenv("HF_MAX_TOKENS", "2048"))
        self.extra_kwargs = kwargs
        self.validate_config()

    def get_model(self, **kwargs) -> BaseChatModel:
        config = {
            "model": self.model,
            "openai_api_key": self.api_key,
            "openai_api_base": self.base_url,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            **self.extra_kwargs,
            **kwargs,
        }
        return ChatOpenAI(**config)

    def get_provider_name(self) -> str:
        return "huggingface"

    def validate_config(self) -> bool:
        if not self.api_key:
            raise ValueError(
                "HF_TOKEN environment variable is required for the HuggingFace provider."
            )
        if not self.api_key.startswith("hf_"):
            raise ValueError(
                "HF_TOKEN does not look like a valid Hugging Face token (expected 'hf_...')."
            )
        return True


# Auto-register when this module is imported
LLMFactory.register_provider("huggingface", HuggingFaceProvider)
