"""
Abstracted database interface for LangGraph checkpointing.
Allows switching between different database backends.
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional
from langgraph.checkpoint.base import BaseCheckpointSaver


class DatabaseProvider(ABC):
    """Abstract base class for database providers"""
    
    @abstractmethod
    def get_checkpointer(self) -> BaseCheckpointSaver:
        """
        Get the checkpoint saver instance.
        
        Returns:
            BaseCheckpointSaver: LangGraph compatible checkpoint saver
        """
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Get the name of the database provider"""
        pass
    
    @abstractmethod
    def validate_config(self) -> bool:
        """
        Validate that the database provider is properly configured.
        
        Returns:
            bool: True if configuration is valid
            
        Raises:
            ValueError: If configuration is invalid
        """
        pass
    
    @abstractmethod
    def initialize(self):
        """Initialize the database (create tables, etc.)"""
        pass


class DatabaseFactory:
    """Factory class to create database providers"""
    
    _providers: Dict[str, type] = {}
    
    @classmethod
    def register_provider(cls, name: str, provider_class: type):
        """Register a new database provider"""
        cls._providers[name.lower()] = provider_class
    
    @classmethod
    def create_provider(cls, provider_name: str, **config) -> DatabaseProvider:
        """
        Create a database provider instance.
        
        Args:
            provider_name: Name of the provider (e.g., 'sqlite', 'postgres')
            **config: Provider-specific configuration
            
        Returns:
            DatabaseProvider: Instance of the requested provider
            
        Raises:
            ValueError: If provider is not registered
        """
        provider_class = cls._providers.get(provider_name.lower())
        if not provider_class:
            available = ", ".join(cls._providers.keys())
            raise ValueError(
                f"Unknown database provider '{provider_name}'. "
                f"Available providers: {available}"
            )
        
        return provider_class(**config)
    
    @classmethod
    def list_providers(cls) -> list[str]:
        """List all registered database providers"""
        return list(cls._providers.keys())
