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
        **kwargs
    ):
        """
        Initialize Bedrock provider.
        
        Args:
            model_id: Bedrock model ID (e.g., 'anthropic.claude-sonnet-4-5-20250929-v1:0')
            region: AWS region
            profile_name: AWS profile name
            **kwargs: Additional configuration for ChatBedrock
        """
        self.model_id = model_id or os.getenv(
            "ANTHROPIC_MODEL",
            os.getenv("LLM_MODEL_ID", "au.anthropic.claude-sonnet-4-5-20250929-v1:0")
        )
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        self.profile_name = profile_name or os.getenv("AWS_PROFILE", "default")
        self.extra_config = kwargs
        
        # Validate configuration on initialization
        self.validate_config()
    
    def get_model(self, **kwargs) -> BaseChatModel:
        """
        Get ChatBedrock model instance.
        
        Args:
            **kwargs: Override configuration for this specific model instance
            
        Returns:
            ChatBedrock: Configured Bedrock chat model
        """
        # Create boto3 session with profile
        session = boto3.Session(
            profile_name=self.profile_name,
            region_name=self.region
        )
        
        # Create bedrock client
        client = session.client("bedrock-runtime")
        
        # Merge instance config with call-time overrides
        config = {
            "model_id": self.model_id,
            "region_name": self.region,
            "client": client,
            **self.extra_config,
            **kwargs
        }
        
        # Check if model uses inference profile (starts with region prefix like 'au.', 'us.', 'eu.')
        model_id_parts = self.model_id.split(".")
        is_inference_profile = len(model_id_parts) > 1 and len(model_id_parts[0]) == 2
        
        # Determine provider based on model ID
        if "amazon" in self.model_id or "nova" in self.model_id:
            # Amazon Nova models require the Converse API
            config["beta_use_converse_api"] = True
            print(f"[DEBUG] Using model: {self.model_id} with Converse API")
        elif is_inference_profile:
            # Inference profiles require Converse API
            config["beta_use_converse_api"] = True
            print(f"[DEBUG] Using inference profile: {self.model_id} with Converse API")
        elif "anthropic" in self.model_id or "claude" in self.model_id:
            # Base model IDs need provider specified
            config["provider"] = "anthropic"
            print(f"[DEBUG] Using model: {self.model_id} with provider=anthropic")
        else:
            # For other models, let LangChain auto-detect
            print(f"[DEBUG] Using model: {self.model_id} (provider auto-detected)")
        
        llm = ChatBedrock(**config)
        
        return llm
    
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
