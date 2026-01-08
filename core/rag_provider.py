"""
RAG provider abstraction for ADAG system.

This module provides an abstract base class for RAG/Vector DB providers,
enabling easy switching between different vector database implementations.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class RAGProvider(ABC):
    """Abstract base class for RAG/Vector DB providers."""
    
    @abstractmethod
    def initialize(self, collection_name: str, **kwargs):
        """
        Initialize the vector database.
        
        Args:
            collection_name: Name of the collection to create/use
            **kwargs: Additional provider-specific configuration
        """
        pass
    
    @abstractmethod
    def index_documents(self, documents: List[Dict[str, Any]]):
        """
        Index documents into the vector store.
        
        Args:
            documents: List of documents to index, each containing:
                - id: Unique document identifier
                - content: Text content to embed
                - metadata: Dictionary of metadata fields
        """
        pass
    
    @abstractmethod
    def retrieve(
        self, 
        query: str, 
        top_k: int = 5, 
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant documents based on query.
        
        Args:
            query: Query string for semantic search
            top_k: Number of results to return
            filters: Optional metadata filters (e.g., {"severity": "HIGH"})
            
        Returns:
            List of retrieved documents with metadata and scores
        """
        pass
    
    @abstractmethod
    def delete_collection(self):
        """Delete the collection (for re-indexing)."""
        pass
    
    @abstractmethod
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the collection.
        
        Returns:
            Dictionary with collection statistics (count, size, etc.)
        """
        pass


class RAGFactory:
    """Factory for creating RAG provider instances."""
    
    _providers: Dict[str, type] = {}
    
    @classmethod
    def register_provider(cls, name: str, provider_class: type):
        """
        Register a RAG provider.
        
        Args:
            name: Provider name (e.g., 'chroma', 'pinecone')
            provider_class: Provider class implementing RAGProvider
        """
        cls._providers[name] = provider_class
    
    @classmethod
    def create_provider(cls, name: str, **config) -> RAGProvider:
        """
        Create a RAG provider instance.
        
        Args:
            name: Provider name
            **config: Provider-specific configuration
            
        Returns:
            RAGProvider instance
            
        Raises:
            ValueError: If provider name is not registered
        """
        if name not in cls._providers:
            available = ', '.join(cls._providers.keys())
            raise ValueError(
                f"Unknown RAG provider: {name}. "
                f"Available providers: {available}"
            )
        
        return cls._providers[name](**config)
    
    @classmethod
    def list_providers(cls) -> List[str]:
        """
        List all registered providers.
        
        Returns:
            List of provider names
        """
        return list(cls._providers.keys())
