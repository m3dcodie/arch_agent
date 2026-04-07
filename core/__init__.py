"""
Core module for ADAG system.

This module provides core functionality including LLM providers,
database providers, and RAG providers.
"""

# Import providers to ensure registration
from core.llm_provider import LLMFactory
from core.database_provider import DatabaseFactory

# Import RAG provider (Phase 2)
try:
    from core.rag_provider import RAGFactory
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False

__all__ = [
    'LLMFactory',
    'DatabaseFactory',
    'RAGFactory',
    'RAG_AVAILABLE'
]
