"""
ChromaDB provider implementation for ADAG system.

This module provides a ChromaDB-based implementation of the RAG provider,
using persistent local storage for policy document embeddings.
"""
import os
import logging
from typing import List, Dict, Any, Optional

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

from core.rag_provider import RAGProvider, RAGFactory

logger = logging.getLogger(__name__)


class ChromaProvider(RAGProvider):
    """ChromaDB implementation for vector storage and retrieval."""
    
    def __init__(self, persist_directory: str = "./data/chroma", **kwargs):
        """
        Initialize ChromaDB provider.
        
        Args:
            persist_directory: Directory for persistent storage
            **kwargs: Additional configuration options
        """
        if not CHROMADB_AVAILABLE:
            raise ImportError(
                "ChromaDB is not installed. "
                "Install it with: pip install chromadb"
            )
        
        self.persist_directory = persist_directory
        self.client = None
        self.collection = None
        self.collection_name = None
        
        logger.info(f"ChromaDB provider initialized with directory: {persist_directory}")
    
    def initialize(self, collection_name: str = "policies", **kwargs):
        """
        Initialize ChromaDB with persistent storage.
        
        Args:
            collection_name: Name of the collection to create/use
            **kwargs: Additional configuration options
        """
        # Create directory if it doesn't exist
        os.makedirs(self.persist_directory, exist_ok=True)
        
        # Initialize ChromaDB client with persistent storage
        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Get or create collection
        try:
            self.collection = self.client.get_collection(name=collection_name)
            logger.info(f"Loaded existing collection: {collection_name}")
        except Exception:
            self.collection = self.client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}  # Use cosine similarity
            )
            logger.info(f"Created new collection: {collection_name}")
        
        self.collection_name = collection_name
    
    def index_documents(self, documents: List[Dict[str, Any]]):
        """
        Index policy documents into ChromaDB.
        
        Args:
            documents: List of documents, each containing:
                - id: Unique policy identifier
                - content: Policy text content
                - metadata: Dictionary of metadata (severity, title, etc.)
        """
        if not self.collection:
            raise RuntimeError("Collection not initialized. Call initialize() first.")
        
        if not documents:
            logger.warning("No documents to index")
            return
        
        # Extract components
        ids = [doc["id"] for doc in documents]
        texts = [doc["content"] for doc in documents]
        metadatas = [doc.get("metadata", {}) for doc in documents]
        
        # Add to collection (ChromaDB handles embedding automatically)
        self.collection.add(
            ids=ids,
            documents=texts,
            metadatas=metadatas
        )
        
        logger.info(f"Indexed {len(documents)} documents into collection '{self.collection_name}'")
    
    def retrieve(
        self, 
        query: str, 
        top_k: int = 5, 
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant policies using semantic search.
        
        Args:
            query: Query string for semantic search
            top_k: Number of results to return
            filters: Optional metadata filters (e.g., {"severity": "HIGH"})
            
        Returns:
            List of retrieved documents with metadata and distances
        """
        if not self.collection:
            raise RuntimeError("Collection not initialized. Call initialize() first.")
        
        # Build where clause for filtering
        where_clause = None
        if filters:
            where_clause = filters
        
        # Query the collection
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where_clause
        )
        
        # Format results
        retrieved = []
        if results and results["ids"] and len(results["ids"]) > 0:
            for i in range(len(results["ids"][0])):
                retrieved.append({
                    "id": results["ids"][0][i],
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i] if "distances" in results else None
                })
        
        logger.info(f"Retrieved {len(retrieved)} documents for query: '{query[:50]}...'")
        return retrieved
    
    def delete_collection(self):
        """Delete the collection for re-indexing."""
        if not self.client or not self.collection_name:
            logger.warning("No collection to delete")
            return
        
        try:
            self.client.delete_collection(name=self.collection_name)
            logger.info(f"Deleted collection: {self.collection_name}")
            self.collection = None
        except Exception as e:
            logger.error(f"Error deleting collection: {e}")
            raise
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the collection.
        
        Returns:
            Dictionary with collection statistics
        """
        if not self.collection:
            return {
                "initialized": False,
                "count": 0
            }
        
        try:
            count = self.collection.count()
            return {
                "initialized": True,
                "collection_name": self.collection_name,
                "document_count": count,
                "persist_directory": self.persist_directory
            }
        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            return {
                "initialized": True,
                "error": str(e)
            }
    
    def update_document(self, doc_id: str, content: str, metadata: Dict[str, Any]):
        """
        Update a single document in the collection.
        
        Args:
            doc_id: Document ID to update
            content: New content
            metadata: New metadata
        """
        if not self.collection:
            raise RuntimeError("Collection not initialized. Call initialize() first.")
        
        self.collection.update(
            ids=[doc_id],
            documents=[content],
            metadatas=[metadata]
        )
        
        logger.info(f"Updated document: {doc_id}")
    
    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific document by ID.
        
        Args:
            doc_id: Document ID to retrieve
            
        Returns:
            Document dict or None if not found
        """
        if not self.collection:
            raise RuntimeError("Collection not initialized. Call initialize() first.")
        
        try:
            result = self.collection.get(ids=[doc_id])
            if result and result["ids"]:
                return {
                    "id": result["ids"][0],
                    "content": result["documents"][0],
                    "metadata": result["metadatas"][0]
                }
        except Exception as e:
            logger.error(f"Error getting document {doc_id}: {e}")
        
        return None


# Register ChromaDB provider with the factory
RAGFactory.register_provider("chroma", ChromaProvider)

logger.info("ChromaDB provider registered")
