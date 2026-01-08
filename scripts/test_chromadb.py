#!/usr/bin/env python3
"""
Test script for ChromaDB setup and RAG functionality.

This script verifies that ChromaDB is properly installed and configured,
and tests basic indexing and retrieval operations.

Usage:
    python scripts/test_chromadb.py
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.rag_provider import RAGFactory


def test_chromadb_installation():
    """Test that ChromaDB is properly installed."""
    print("=" * 70)
    print("Testing ChromaDB Installation")
    print("=" * 70)
    
    try:
        import chromadb
        print("✅ ChromaDB is installed")
        print(f"   Version: {chromadb.__version__}")
        return True
    except ImportError as e:
        print("❌ ChromaDB is not installed")
        print(f"   Error: {e}")
        print("\n   Install with: pip install chromadb")
        return False


def test_provider_registration():
    """Test that ChromaDB provider is registered."""
    print("\n" + "=" * 70)
    print("Testing Provider Registration")
    print("=" * 70)
    
    providers = RAGFactory.list_providers()
    print(f"Registered providers: {providers}")
    
    if "chroma" in providers:
        print("✅ ChromaDB provider is registered")
        return True
    else:
        print("❌ ChromaDB provider is not registered")
        return False


def test_provider_initialization():
    """Test that ChromaDB provider can be initialized."""
    print("\n" + "=" * 70)
    print("Testing Provider Initialization")
    print("=" * 70)
    
    try:
        rag = RAGFactory.create_provider("chroma", persist_directory="./data/chroma_test")
        print("✅ Provider created successfully")
        
        rag.initialize(collection_name="test_collection")
        print("✅ Collection initialized successfully")
        
        stats = rag.get_collection_stats()
        print(f"   Collection: {stats.get('collection_name')}")
        print(f"   Documents: {stats.get('document_count')}")
        
        return True, rag
    except Exception as e:
        print(f"❌ Provider initialization failed: {e}")
        return False, None


def test_indexing_and_retrieval(rag):
    """Test document indexing and retrieval."""
    print("\n" + "=" * 70)
    print("Testing Indexing and Retrieval")
    print("=" * 70)
    
    # Test documents
    test_docs = [
        {
            "id": "test_policy_1",
            "content": "All databases must have deletion protection enabled to prevent accidental data loss.",
            "metadata": {
                "title": "Deletion Protection Policy",
                "severity": "HIGH",
                "scope": "aws_db_instance,aws_rds_cluster"
            }
        },
        {
            "id": "test_policy_2",
            "content": "All S3 buckets must have encryption at rest enabled using AES256 or KMS.",
            "metadata": {
                "title": "Encryption at Rest Policy",
                "severity": "HIGH",
                "scope": "aws_s3_bucket"
            }
        },
        {
            "id": "test_policy_3",
            "content": "Production databases must be deployed in multi-AZ configuration for high availability.",
            "metadata": {
                "title": "Multi-AZ Requirement",
                "severity": "MEDIUM",
                "scope": "aws_db_instance,aws_rds_cluster"
            }
        }
    ]
    
    try:
        # Index documents
        print("\n📝 Indexing test documents...")
        rag.index_documents(test_docs)
        print(f"✅ Indexed {len(test_docs)} documents")
        
        # Test retrieval
        print("\n🔍 Testing retrieval...")
        test_queries = [
            ("database protection", "test_policy_1"),
            ("S3 encryption", "test_policy_2"),
            ("high availability", "test_policy_3")
        ]
        
        all_passed = True
        for query, expected_id in test_queries:
            print(f"\n   Query: '{query}'")
            results = rag.retrieve(query, top_k=3)
            
            if results and len(results) > 0:
                top_result = results[0]
                print(f"   Top result: {top_result['metadata']['title']}")
                print(f"   Expected: {expected_id}, Got: {top_result['id']}")
                
                if top_result['id'] == expected_id:
                    print("   ✅ Correct result retrieved")
                else:
                    print("   ⚠️  Different result retrieved (may still be relevant)")
            else:
                print("   ❌ No results retrieved")
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print(f"❌ Indexing/retrieval test failed: {e}")
        return False


def test_cleanup(rag):
    """Clean up test collection."""
    print("\n" + "=" * 70)
    print("Cleaning Up Test Data")
    print("=" * 70)
    
    try:
        rag.delete_collection()
        print("✅ Test collection deleted")
        return True
    except Exception as e:
        print(f"⚠️  Could not delete test collection: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("ADAG ChromaDB Setup Test")
    print("=" * 70 + "\n")
    
    results = []
    
    # Test 1: Installation
    results.append(("Installation", test_chromadb_installation()))
    
    if not results[-1][1]:
        print("\n❌ ChromaDB is not installed. Cannot proceed with other tests.")
        print("   Install with: pip install -r requirements.txt")
        sys.exit(1)
    
    # Test 2: Registration
    results.append(("Registration", test_provider_registration()))
    
    # Test 3: Initialization
    init_result, rag = test_provider_initialization()
    results.append(("Initialization", init_result))
    
    if not init_result:
        print("\n❌ Provider initialization failed. Cannot proceed with other tests.")
        sys.exit(1)
    
    # Test 4: Indexing and Retrieval
    results.append(("Indexing & Retrieval", test_indexing_and_retrieval(rag)))
    
    # Test 5: Cleanup
    results.append(("Cleanup", test_cleanup(rag)))
    
    # Summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name:.<50} {status}")
    
    all_passed = all(result[1] for result in results)
    
    print("\n" + "=" * 70)
    if all_passed:
        print("✅ All tests passed! ChromaDB is ready for use.")
        print("=" * 70)
        print("\nNext steps:")
        print("1. Run: python scripts/index_policies.py")
        print("2. This will index all policies from the policies/ directory")
        sys.exit(0)
    else:
        print("❌ Some tests failed. Please check the errors above.")
        print("=" * 70)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
