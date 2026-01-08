#!/usr/bin/env python3
"""
Policy Indexing Script for ADAG Phase 2

This script indexes policy documents from the policies/ directory into ChromaDB
for RAG-based retrieval during auditing.

Usage:
    python scripts/index_policies.py [--reindex] [--policies-dir PATH]
"""
import os
import sys
import argparse
import logging
from pathlib import Path
from typing import Dict, List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.rag_provider import RAGFactory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_policy_markdown(file_path: str) -> Dict[str, str]:
    """
    Parse a policy markdown file and extract structured data.
    
    Expected format:
    # Policy Title
    ## Policy ID
    `policy_id`
    ## Severity
    **HIGH**
    ...
    
    Args:
        file_path: Path to the policy markdown file
        
    Returns:
        Dictionary containing policy metadata and content
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return None
    
    lines = content.split('\n')
    
    policy_data = {
        "id": "",
        "title": "",
        "severity": "",
        "content": content,  # Full content for embedding
        "file_path": file_path,
        "scope": []
    }
    
    # Extract metadata using simple parsing
    in_scope_section = False
    
    for i, line in enumerate(lines):
        # Extract title (first H1)
        if line.startswith('# ') and not policy_data["title"]:
            policy_data["title"] = line[2:].strip()
        
        # Extract policy ID (in backticks)
        elif '`' in line and not policy_data["id"]:
            # Extract text between backticks
            parts = line.split('`')
            if len(parts) >= 2:
                potential_id = parts[1].strip()
                # Check if it looks like a policy ID (lowercase with underscores)
                if '_' in potential_id or potential_id.islower():
                    policy_data["id"] = potential_id
        
        # Extract severity
        elif '**HIGH**' in line or '**MEDIUM**' in line or '**LOW**' in line:
            if '**HIGH**' in line:
                policy_data["severity"] = "HIGH"
            elif '**MEDIUM**' in line:
                policy_data["severity"] = "MEDIUM"
            elif '**LOW**' in line:
                policy_data["severity"] = "LOW"
        
        # Extract scope (resource types)
        elif line.startswith('## Scope'):
            in_scope_section = True
        elif in_scope_section:
            if line.startswith('##'):
                in_scope_section = False
            elif line.strip().startswith('- `'):
                # Extract resource type from list item
                resource_type = line.split('`')[1] if '`' in line else None
                if resource_type:
                    policy_data["scope"].append(resource_type)
    
    # Validate required fields
    if not policy_data["id"]:
        logger.warning(f"Could not extract policy ID from {file_path}")
        # Use filename as fallback
        policy_data["id"] = Path(file_path).stem
    
    if not policy_data["title"]:
        policy_data["title"] = policy_data["id"].replace('_', ' ').title()
    
    if not policy_data["severity"]:
        policy_data["severity"] = "MEDIUM"  # Default
    
    return policy_data


def index_policies(
    policies_dir: str = "./policies",
    reindex: bool = False,
    collection_name: str = "policies"
) -> int:
    """
    Index all policy files from the policies directory.
    
    Args:
        policies_dir: Directory containing policy markdown files
        reindex: If True, delete existing collection and reindex
        collection_name: Name of the ChromaDB collection
        
    Returns:
        Number of policies indexed
    """
    logger.info("=" * 70)
    logger.info("ADAG Policy Indexing Script")
    logger.info("=" * 70)
    
    # Initialize RAG provider
    logger.info("Initializing ChromaDB provider...")
    try:
        rag = RAGFactory.create_provider("chroma")
        rag.initialize(collection_name=collection_name)
    except Exception as e:
        logger.error(f"Failed to initialize RAG provider: {e}")
        return 0
    
    # Reindex if requested
    if reindex:
        logger.info("🔄 Reindexing: Deleting existing collection...")
        try:
            rag.delete_collection()
            rag.initialize(collection_name=collection_name)
            logger.info("✓ Collection deleted and recreated")
        except Exception as e:
            logger.warning(f"Could not delete collection (may not exist): {e}")
    
    # Find all markdown files
    policies_path = Path(policies_dir)
    if not policies_path.exists():
        logger.error(f"Policies directory not found: {policies_dir}")
        return 0
    
    policy_files = list(policies_path.glob("*.md"))
    logger.info(f"📄 Found {len(policy_files)} policy files in {policies_dir}")
    
    if not policy_files:
        logger.warning("No policy files found!")
        return 0
    
    # Parse and index each policy
    documents = []
    for policy_file in sorted(policy_files):
        logger.info(f"   Processing: {policy_file.name}")
        
        policy_data = parse_policy_markdown(str(policy_file))
        
        if not policy_data:
            logger.warning(f"   ⚠️  Skipped: Could not parse {policy_file.name}")
            continue
        
        # Create document for indexing
        documents.append({
            "id": policy_data["id"],
            "content": policy_data["content"],
            "metadata": {
                "title": policy_data["title"],
                "severity": policy_data["severity"],
                "file_path": str(policy_file),
                "scope": ",".join(policy_data["scope"]) if policy_data["scope"] else ""
            }
        })
        
        logger.info(f"   ✓ Parsed: {policy_data['title']} ({policy_data['severity']})")
    
    # Index all documents
    if documents:
        logger.info(f"\n💾 Indexing {len(documents)} policies into ChromaDB...")
        try:
            rag.index_documents(documents)
            logger.info("✅ Indexing complete!")
        except Exception as e:
            logger.error(f"Error indexing documents: {e}")
            return 0
    else:
        logger.warning("No documents to index")
        return 0
    
    # Get collection stats
    stats = rag.get_collection_stats()
    logger.info(f"\n📊 Collection Statistics:")
    logger.info(f"   Collection: {stats.get('collection_name', 'N/A')}")
    logger.info(f"   Documents: {stats.get('document_count', 0)}")
    logger.info(f"   Location: {stats.get('persist_directory', 'N/A')}")
    
    # Test retrieval
    logger.info(f"\n🔍 Testing retrieval...")
    test_queries = [
        "database deletion protection",
        "S3 bucket encryption",
        "production availability requirements"
    ]
    
    for query in test_queries:
        try:
            results = rag.retrieve(query, top_k=3)
            logger.info(f"\n   Query: '{query}'")
            logger.info(f"   Retrieved {len(results)} policies:")
            for i, result in enumerate(results, 1):
                title = result['metadata'].get('title', 'Unknown')
                distance = result.get('distance', 'N/A')
                logger.info(f"      {i}. {title} (distance: {distance:.4f})" if isinstance(distance, float) else f"      {i}. {title}")
        except Exception as e:
            logger.error(f"   Error testing query '{query}': {e}")
    
    logger.info("\n" + "=" * 70)
    logger.info("✅ Policy indexing completed successfully!")
    logger.info("=" * 70)
    
    return len(documents)


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Index ADAG policy documents into ChromaDB"
    )
    parser.add_argument(
        "--reindex",
        action="store_true",
        help="Delete existing collection and reindex all policies"
    )
    parser.add_argument(
        "--policies-dir",
        type=str,
        default="./policies",
        help="Directory containing policy markdown files (default: ./policies)"
    )
    parser.add_argument(
        "--collection",
        type=str,
        default="policies",
        help="ChromaDB collection name (default: policies)"
    )
    
    args = parser.parse_args()
    
    try:
        count = index_policies(
            policies_dir=args.policies_dir,
            reindex=args.reindex,
            collection_name=args.collection
        )
        
        if count > 0:
            sys.exit(0)
        else:
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("\n\nIndexing interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n\nFatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
