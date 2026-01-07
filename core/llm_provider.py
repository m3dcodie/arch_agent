"""
Abstracted LLM provider interface.
Allows switching between different LLM providers (AWS Bedrock, OpenAI, etc.)
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from langchain_core.language_models import BaseChatModel


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    @abstractmethod
    def get_model(self, **kwargs) -> BaseChatModel:
        """
        Get the LLM model instance.
        
        Args:
            **kwargs: Provider-specific configuration options
            
        Returns:
            BaseChatModel: LangChain compatible chat model
        """
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Get the name of the provider"""
        pass
    
    @abstractmethod
    def validate_config(self) -> bool:
        """
        Validate that the provider is properly configured.
        
        Returns:
            bool: True if configuration is valid
            
        Raises:
            ValueError: If configuration is invalid
        """
        pass


class LLMFactory:
    """Factory class to create LLM providers"""
    
    _providers: Dict[str, type] = {}
    
    @classmethod
    def register_provider(cls, name: str, provider_class: type):
        """Register a new LLM provider"""
        cls._providers[name.lower()] = provider_class
    
    @classmethod
    def create_provider(cls, provider_name: str, **config) -> LLMProvider:
        """
        Create an LLM provider instance.
        
        Args:
            provider_name: Name of the provider (e.g., 'bedrock', 'openai')
            **config: Provider-specific configuration
            
        Returns:
            LLMProvider: Instance of the requested provider
            
        Raises:
            ValueError: If provider is not registered
        """
        provider_class = cls._providers.get(provider_name.lower())
        if not provider_class:
            available = ", ".join(cls._providers.keys())
            raise ValueError(
                f"Unknown provider '{provider_name}'. "
                f"Available providers: {available}"
            )
        
        return provider_class(**config)
    
    @classmethod
    def list_providers(cls) -> list[str]:
        """List all registered providers"""
        return list(cls._providers.keys())
