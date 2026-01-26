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

import requests
from rag_service_config import (
    INGESTION_URL, CHUNKING_URL, EMBEDDING_URL, ADD_VECTORS_URL, APPID
)

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
    
    # REST API base URL and appid
    headers = {"Content-Type": "application/json"}
    
    # Reindex if requested (not supported directly, so log only)
    if reindex:
        logger.info("🔄 Reindexing: Please clear vector DB via API or admin if needed.")
    
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
    
    # Parse and index each policy using REST API
    for policy_file in sorted(policy_files):
        logger.info(f"   Processing: {policy_file.name}")
        policy_data = parse_policy_markdown(str(policy_file))
        if not policy_data:
            logger.warning(f"   ⚠️  Skipped: Could not parse {policy_file.name}")
            continue

        # 1. Ingest document
        ingest_payload = {
            "source_type": "local",
            "config": {
                "id": policy_data["id"],
                "title": policy_data["title"],
                "severity": policy_data["severity"],
                "file_path": str(policy_file),
                "scope": policy_data["scope"],
                "content": policy_data["content"]
            }
        }
        try:
            ingest_resp = requests.post(INGESTION_URL.format(appid=APPID), json=ingest_payload, headers=headers)
            ingest_resp.raise_for_status()
            ingest_result = ingest_resp.json()
            logger.info(f"   ✓ Ingested: {policy_data['title']} ({policy_data['severity']})")
        except Exception as e:
            logger.error(f"   Error ingesting {policy_file.name}: {e}")
            continue

        # 2. Chunk document (send full document object)
        chunk_payload = {
            "document": ingest_payload["config"],
            "chunker_type": "langchain",
            "chunker_config": {"chunk_size": 200, "chunk_overlap": 50}
        }
        try:
            chunk_resp = requests.post(CHUNKING_URL.format(appid=APPID), json=chunk_payload, headers=headers)
            chunk_resp.raise_for_status()
            chunks = chunk_resp.json().get("chunks", [])
            logger.info(f"   ✓ Chunked: {len(chunks)} chunks")
        except Exception as e:
            logger.error(f"   Error chunking {policy_file.name}: {e}")
            continue

        if not chunks:
            logger.warning(f"   ⚠️  No chunks produced for {policy_file.name}")
            continue

        # 3. Embed chunks
        texts = [chunk.get("content", chunk.get("document", "")) for chunk in chunks]
        embed_payload = {
            "texts": texts,
            "embedder_type": "default",
            "embedder_config": {}
        }
        try:
            logger.info(f"[EMBED] Request payload: {embed_payload}")
            embed_resp = requests.post(EMBEDDING_URL.format(appid=APPID), json=embed_payload, headers=headers)
            logger.info(f"[EMBED] Status code: {embed_resp.status_code}")
            logger.info(f"[EMBED] Response: {getattr(embed_resp, 'text', embed_resp)}")
            embed_resp.raise_for_status()
            embeddings = embed_resp.json().get("embeddings", [])
            logger.info(f"   ✓ Embedded: {len(embeddings)} vectors")
        except Exception as e:
            logger.error(f"   Error embedding {policy_file.name}: {e}")
            continue

        if not embeddings or len(embeddings) != len(chunks):
            logger.warning(f"   ⚠️  Embedding count mismatch for {policy_file.name}")
            continue

        # 4. Add vectors to vector DB
        # Ensure each metadata is non-empty: include at least 'text' and 'chunk_index'
        metadatas = []
        for i, chunk in enumerate(chunks):
            meta = dict(chunk.get("metadata") or {})
            # Always include 'text' and 'chunk_index'
            meta["text"] = chunk.get("chunk") or chunk.get("content") or ""
            meta["chunk_index"] = chunk.get("index", i)
            # Remove empty keys
            meta = {k: v for k, v in meta.items() if v not in (None, "")}
            metadatas.append(meta)
        add_vectors_payload = {
            "vectors": embeddings,
            "metadatas": metadatas,
            "adapter_config": {}
        }
        try:
            add_vectors_resp = requests.post(ADD_VECTORS_URL.format(appid=APPID), json=add_vectors_payload, headers=headers)
            add_vectors_resp.raise_for_status()
            logger.info(f"   ✓ Added vectors to DB for {policy_data['title']}")
        except Exception as e:
            logger.error(f"   Error adding vectors for {policy_file.name}: {e}")
            continue

    logger.info("\n✅ Policy indexing pipeline completed via REST API!")
    return len(policy_files)


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
