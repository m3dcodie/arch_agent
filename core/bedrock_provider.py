"""
AWS Bedrock LLM provider implementation.
"""

import os
from typing import Optional
import boto3
from langchain_aws import ChatBedrock
from langchain_core.language_models import BaseChatModel

from core.llm_provider import LLMProvider, LLMFactory


class BedrockProvider(LLMProvider):
    """AWS Bedrock LLM provider"""

    def __init__(
        self,
        model_id: Optional[str] = None,
        region: Optional[str] = None,
        profile_name: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize Bedrock provider.

        Args:
            model_id: Bedrock model ID (e.g., 'anthropic.claude-sonnet-4-5-20250929-v1:0')
            region: AWS region
            profile_name: AWS profile name
            **kwargs: Additional configuration for ChatBedrock
        """
        # Use standardized BEDROCK_MODEL env var (consistent with HF_MODEL, OLLAMA_MODEL, etc.)
        self.model_id = model_id or os.getenv(
            "BEDROCK_MODEL",
            "anthropic.claude-sonnet-4-5-20250929-v1:0",
        )
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        self.profile_name = profile_name or os.getenv("AWS_PROFILE", "default")
        # Auditor task is deterministic classification — temperature=0 prevents
        # random pass/fail flips and JSON corruption.
        # Override globally via LLM_TEMPERATURE, or per-provider via BEDROCK_TEMPERATURE.
        self.temperature = float(os.getenv("BEDROCK_TEMPERATURE", os.getenv("LLM_TEMPERATURE", "0")))
        # Max output tokens — caps response length and prevents runaway generation.
        # Override globally via LLM_MAX_TOKENS, or per-provider via BEDROCK_MAX_TOKENS.
        self.max_tokens = int(os.getenv("BEDROCK_MAX_TOKENS", os.getenv("LLM_MAX_TOKENS", "4096")))
        # Prompt caching — enabled by default for Anthropic/Claude base model IDs.
        # Adds anthropic_beta header so cache_control blocks in messages are honoured.
        # Set BEDROCK_PROMPT_CACHE=false to disable (e.g. for models that don't support it).
        self.prompt_cache = os.getenv("BEDROCK_PROMPT_CACHE", "true").lower() == "true"
        self.extra_config = kwargs

        # Validate configuration on initialization
        self.validate_config()

    def get_model(self, **kwargs) -> BaseChatModel:
        """
        Get ChatBedrock model instance.

        Args:
            model_id: Override the default model ID for per-agent model selection
            **kwargs: Override configuration for this specific model instance

        Returns:
            ChatBedrock: Configured Bedrock chat model
        """
        # Extract model_id override if provided (for per-agent selection)
        model_id = kwargs.pop("model_id", None) or self.model_id

        # Create boto3 session with profile
        session = boto3.Session(profile_name=self.profile_name, region_name=self.region)

        # Create bedrock client
        client = session.client("bedrock-runtime")

        # Merge instance config with call-time overrides
        config = {
            "model_id": model_id,
            "region_name": self.region,
            "client": client,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            **self.extra_config,
            **kwargs,
        }

        # Check if model uses inference profile (starts with region prefix like 'au.', 'us.', 'eu.')
        model_id_parts = model_id.split(".")
        is_inference_profile = len(model_id_parts) > 1 and len(model_id_parts[0]) == 2

        # Determine provider based on model ID
        if "amazon" in model_id or "nova" in model_id:
            # Amazon Nova models require the Converse API
            config["beta_use_converse_api"] = True
            print(f"[DEBUG] Using model: {model_id} with Converse API")
        elif is_inference_profile:
            # Inference profiles require Converse API
            config["beta_use_converse_api"] = True
            print(f"[DEBUG] Using inference profile: {model_id} with Converse API")
        elif "anthropic" in model_id or "claude" in model_id:
            # Base model IDs need provider specified
            config["provider"] = "anthropic"
            # Enable prompt caching — requires anthropic_beta header on the request.
            # cache_control blocks in SystemMessage content will then be honoured.
            if self.prompt_cache:
                model_kwargs = config.get("model_kwargs", {})
                betas = list(model_kwargs.get("anthropic_beta", []))
                if "prompt-caching-2024-07-31" not in betas:
                    betas.append("prompt-caching-2024-07-31")
                model_kwargs["anthropic_beta"] = betas
                config["model_kwargs"] = model_kwargs
            print(f"[DEBUG] Using model: {model_id} with provider=anthropic")
        else:
            # For other models, let LangChain auto-detect
            print(f"[DEBUG] Using model: {model_id} (provider auto-detected)")

        llm = ChatBedrock(**config)

        return llm

    @property
    def supports_prompt_cache(self) -> bool:
        """True when prompt caching is enabled and the model is a base Anthropic/Claude ID.

        Inference profiles (e.g. ``us.anthropic.claude-*``) use the Converse API
        which has a different caching mechanism and is excluded here.
        """
        mid = self.model_id.lower()
        is_anthropic = "anthropic" in mid or "claude" in mid
        # Inference profiles have a two-character region prefix before the first dot
        is_inference_profile = len(mid.split(".")[0]) == 2
        return self.prompt_cache and is_anthropic and not is_inference_profile

    def get_provider_name(self) -> str:
        """Get the provider name"""
        return "bedrock"

    def validate_config(self) -> bool:
        """
        Validate AWS Bedrock configuration.

        Returns:
            bool: True if valid

        Raises:
            ValueError: If configuration is invalid
        """
        if not self.model_id:
            raise ValueError("model_id is required for Bedrock provider")

        if not self.region:
            raise ValueError("AWS region is required for Bedrock provider")

        # Validate AWS credentials are available
        try:
            session = boto3.Session(profile_name=self.profile_name)
            credentials = session.get_credentials()
            if not credentials:
                raise ValueError(
                    f"No AWS credentials found for profile '{self.profile_name}'. "
                    "Please configure AWS credentials."
                )
        except Exception as e:
            raise ValueError(f"AWS configuration error: {str(e)}")

        return True


# Register the Bedrock provider with the factory
LLMFactory.register_provider("bedrock", BedrockProvider)
