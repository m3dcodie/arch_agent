# Phase 2 Setup Guide - ChromaDB Development Environment

This guide walks you through setting up the ChromaDB-based RAG system for ADAG Phase 2.

## 📋 Prerequisites

- Python 3.11 or higher
- Virtual environment activated
- Phase 1 working (basic ADAG system)

## 🚀 Quick Start

### 1. Install Phase 2 Dependencies

```bash
# Install new dependencies (ChromaDB and sentence-transformers)
pip install -r requirements.txt
```

This will install:
- `chromadb==0.4.22` - Vector database for policy storage
- `sentence-transformers==2.3.1` - For local embeddings (optional)

### 2. Verify ChromaDB Installation

```bash
# Run the test script to verify everything is working
python scripts/test_chromadb.py
```

Expected output:
```
======================================================================
ADAG ChromaDB Setup Test
======================================================================

======================================================================
Testing ChromaDB Installation
======================================================================
✅ ChromaDB is installed
   Version: 0.4.22

======================================================================
Testing Provider Registration
======================================================================
Registered providers: ['chroma']
✅ ChromaDB provider is registered

======================================================================
Testing Provider Initialization
======================================================================
✅ Provider created successfully
✅ Collection initialized successfully
   Collection: test_collection
   Documents: 0

======================================================================
Testing Indexing and Retrieval
======================================================================

📝 Indexing test documents...
✅ Indexed 3 documents

🔍 Testing retrieval...
   Query: 'database protection'
   Top result: Deletion Protection Policy
   ✅ Correct result retrieved
   ...

======================================================================
✅ All tests passed! ChromaDB is ready for use.
======================================================================
```

### 3. Index Policy Documents

```bash
# Index all policies from the policies/ directory
python scripts/index_policies.py
```

Expected output:
```
======================================================================
ADAG Policy Indexing Script
======================================================================
Initializing ChromaDB provider...
📄 Found 10 policy files in ./policies
   Processing: allowed_regions.md
   ✓ Parsed: Allowed Regions Policy (MEDIUM)
   Processing: automated_backups_enabled.md
   ✓ Parsed: Automated Backups Enabled Policy (MEDIUM)
   ...

💾 Indexing 10 policies into ChromaDB...
✅ Indexing complete!

📊 Collection Statistics:
   Collection: policies
   Documents: 10
   Location: ./data/chroma

🔍 Testing retrieval...
   Query: 'database deletion protection'
   Retrieved 3 policies:
      1. Deletion Protection Policy (distance: 0.2341)
      2. Backup Retention Policy (distance: 0.4523)
      3. Automated Backups Enabled Policy (distance: 0.4891)

======================================================================
✅ Policy indexing completed successfully!
======================================================================
```

### 4. Verify Data Directory Structure

After indexing, you should have:

```
./data/
├── adag.db              # LangGraph checkpoints (Phase 1)
└── chroma/              # ChromaDB vector store (Phase 2)
    ├── chroma.sqlite3   # ChromaDB database
    └── ...              # Other ChromaDB files
```

## 🔧 Configuration

### Environment Variables

Update your `.env` file with Phase 2 settings:

```bash
# Copy example if you haven't already
cp .env.example .env

# Edit .env and ensure these are set:
RAG_PROVIDER=chroma
CHROMA_PERSIST_DIR=./data/chroma
POLICIES_DIR=./policies
USE_RAG=true
```

### Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `RAG_PROVIDER` | `chroma` | RAG provider to use |
| `CHROMA_PERSIST_DIR` | `./data/chroma` | ChromaDB storage directory |
| `POLICIES_DIR` | `./policies` | Policy documents directory |
| `USE_RAG` | `true` | Enable RAG-based policy retrieval |

## 📝 Usage

### Indexing Policies

**Initial indexing:**
```bash
python scripts/index_policies.py
```

**Re-indexing (delete and recreate):**
```bash
python scripts/index_policies.py --reindex
```

**Custom policies directory:**
```bash
python scripts/index_policies.py --policies-dir /path/to/policies
```

**Custom collection name:**
```bash
python scripts/index_policies.py --collection my_policies
```

### Testing Retrieval

You can test retrieval programmatically:

```python
from core.rag_provider import RAGFactory

# Initialize provider
rag = RAGFactory.create_provider("chroma")
rag.initialize(collection_name="policies")

# Retrieve policies
results = rag.retrieve("database encryption", top_k=5)

for result in results:
    print(f"Policy: {result['metadata']['title']}")
    print(f"Severity: {result['metadata']['severity']}")
    print(f"Distance: {result['distance']:.4f}")
    print()
```

### Filtering by Metadata

```python
# Retrieve only HIGH severity policies
results = rag.retrieve(
    "database security",
    top_k=5,
    filters={"severity": "HIGH"}
)
```

## 🧪 Testing

### Run ChromaDB Tests

```bash
# Test ChromaDB setup
python scripts/test_chromadb.py
```

### Run Full Test Suite (Phase 1 + Phase 2)

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

## 🔍 Troubleshooting

### Issue: ChromaDB Import Error

**Error:**
```
ImportError: No module named 'chromadb'
```

**Solution:**
```bash
pip install chromadb==0.4.22
```

### Issue: Permission Denied on ./data/chroma

**Error:**
```
PermissionError: [Errno 13] Permission denied: './data/chroma'
```

**Solution:**
```bash
# Create directory with proper permissions
mkdir -p ./data/chroma
chmod 755 ./data/chroma
```

### Issue: SQLite Version Too Old

**Error:**
```
sqlite3.OperationalError: near "RETURNING": syntax error
```

**Solution:**
ChromaDB requires SQLite 3.35+. Update Python or use a newer environment.

```bash
# Check SQLite version
python -c "import sqlite3; print(sqlite3.sqlite_version)"

# Should be 3.35.0 or higher
```

### Issue: No Policies Found

**Error:**
```
📄 Found 0 policy files in ./policies
```

**Solution:**
```bash
# Verify policies directory exists and contains .md files
ls -la ./policies/*.md

# If missing, check you're in the correct directory
pwd
```

### Issue: Poor Retrieval Results

**Symptom:** Queries return irrelevant policies

**Solutions:**
1. **Re-index policies:**
   ```bash
   python scripts/index_policies.py --reindex
   ```

2. **Check policy content:** Ensure policies have rich, descriptive content

3. **Adjust top_k:** Retrieve more results
   ```python
   results = rag.retrieve(query, top_k=10)
   ```

## 📊 Performance Considerations

### Indexing Performance

- **10 policies:** ~5-10 seconds
- **50 policies:** ~20-30 seconds
- **100 policies:** ~40-60 seconds

### Retrieval Performance

- **Single query:** ~50-100ms
- **Batch queries (10):** ~200-500ms

### Storage Requirements

- **Per policy:** ~50-100 KB (including embeddings)
- **10 policies:** ~1 MB
- **100 policies:** ~10 MB

## 🔄 Updating Policies

### Add New Policy

1. Create new markdown file in `./policies/`
2. Follow the policy template structure
3. Re-index:
   ```bash
   python scripts/index_policies.py --reindex
   ```

### Update Existing Policy

1. Edit the policy markdown file
2. Re-index:
   ```bash
   python scripts/index_policies.py --reindex
   ```

### Delete Policy

1. Remove the markdown file
2. Re-index:
   ```bash
   python scripts/index_policies.py --reindex
   ```

## 📚 Next Steps

After setting up ChromaDB:

1. **Week 2:** Implement policy analyst agent
   - Create `agents/policy_analyst.py`
   - Integrate with LangGraph workflow

2. **Week 3:** Update auditor agent
   - Modify to use retrieved policies
   - Test multi-policy auditing

3. **Week 4:** Testing and documentation
   - Write comprehensive tests
   - Update README with Phase 2 features

## 🆘 Getting Help

### Check Logs

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
python scripts/index_policies.py
```

### Inspect ChromaDB

```python
from core.rag_provider import RAGFactory

rag = RAGFactory.create_provider("chroma")
rag.initialize(collection_name="policies")

# Get collection statistics
stats = rag.get_collection_stats()
print(stats)

# Get specific document
doc = rag.get_document("delete_protection")
print(doc)
```

### Reset Everything

```bash
# Delete ChromaDB data
rm -rf ./data/chroma

# Re-index from scratch
python scripts/index_policies.py
```

## ✅ Verification Checklist

Before proceeding to Week 2 implementation:

- [x] ChromaDB installed and working
- [x] Test script passes all tests
- [x] All 10 policies indexed successfully
- [x] Retrieval returns relevant results
- [x] Collection statistics show 10 documents
- [x] Data directory structure is correct
- [x] Environment variables configured

**Status:** ✅ All verification steps completed successfully!

## 📖 Additional Resources

- [ChromaDB Documentation](https://docs.trychroma.com/)
- [Phase 2 Plan](PHASE2_PLAN.md)
- [Policy Priority Guide](POLICY_PRIORITY.md)
- [Main README](README.md)

---

**Status:** Phase 2 Development Environment Setup Complete ✅  
**Next:** Begin Week 2 - Policy Analyst Agent Implementation
