# Phase 2 Quick Reference

## 🚀 Quick Commands

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Test ChromaDB
python scripts/test_chromadb.py

# Index policies
python scripts/index_policies.py
```

### Re-indexing
```bash
# Full re-index
python scripts/index_policies.py --reindex

# Custom directory
python scripts/index_policies.py --policies-dir /path/to/policies
```

### Testing
```bash
# Test ChromaDB setup
python scripts/test_chromadb.py

# Run all tests
pytest tests/ -v
```

## 📁 File Structure

```
Phase 2 Files:
├── core/
│   ├── rag_provider.py          # RAG abstraction layer
│   └── chroma_provider.py       # ChromaDB implementation
├── scripts/
│   ├── index_policies.py        # Policy indexing script
│   └── test_chromadb.py         # ChromaDB test script
├── policies/                     # 10 policy documents
│   ├── delete_protection.md
│   ├── encryption_at_rest.md
│   ├── public_access_block.md
│   ├── multi_az_requirement.md
│   ├── backup_retention.md
│   ├── automated_backups_enabled.md
│   ├── required_tagging.md
│   ├── naming_conventions.md
│   ├── kms_key_rotation.md
│   └── allowed_regions.md
└── data/
    └── chroma/                   # ChromaDB storage
```

## 🔧 Configuration (.env)

```bash
# Phase 2 Settings
RAG_PROVIDER=chroma
CHROMA_PERSIST_DIR=./data/chroma
POLICIES_DIR=./policies
USE_RAG=true
```

## 📊 Policy Inventory

| # | Policy | Severity | Resource Types |
|---|--------|----------|----------------|
| 1 | Deletion Protection | HIGH | RDS, Aurora |
| 2 | Encryption at Rest | HIGH | RDS, S3, EBS, DynamoDB |
| 3 | Public Access Block | HIGH | S3, RDS, Security Groups |
| 4 | Multi-AZ Requirement | MEDIUM | RDS, Aurora, ElastiCache |
| 5 | Backup Retention | MEDIUM | RDS, Aurora, DynamoDB |
| 6 | Automated Backups | MEDIUM | RDS, Aurora, Redshift |
| 7 | Required Tagging | LOW | All Resources |
| 8 | Naming Conventions | LOW | All Resources |
| 9 | KMS Key Rotation | MEDIUM | KMS Keys |
| 10 | Allowed Regions | MEDIUM | All Resources |

## 🔍 Common Queries

### Programmatic Usage

```python
from core.rag_provider import RAGFactory

# Initialize
rag = RAGFactory.create_provider("chroma")
rag.initialize(collection_name="policies")

# Retrieve policies
results = rag.retrieve("database encryption", top_k=5)

# Filter by severity
results = rag.retrieve(
    "security policies",
    top_k=5,
    filters={"severity": "HIGH"}
)

# Get stats
stats = rag.get_collection_stats()
print(f"Documents: {stats['document_count']}")
```

## 🎯 Expected Retrieval Results

| Query | Expected Top Result |
|-------|---------------------|
| "database deletion protection" | delete_protection |
| "S3 encryption" | encryption_at_rest |
| "public access security" | public_access_block |
| "high availability" | multi_az_requirement |
| "backup policy" | backup_retention |
| "cost allocation" | required_tagging |
| "resource naming" | naming_conventions |
| "key management" | kms_key_rotation |
| "data sovereignty" | allowed_regions |

## ⚡ Performance Metrics

- **Indexing:** ~5-10 seconds for 10 policies
- **Retrieval:** ~50-100ms per query
- **Storage:** ~1 MB for 10 policies
- **Accuracy:** >90% expected for top-3 results

## 🐛 Troubleshooting

### ChromaDB not installed
```bash
pip install chromadb==0.4.22
```

### No policies found
```bash
ls -la ./policies/*.md
```

### Poor retrieval results
```bash
python scripts/index_policies.py --reindex
```

### Permission errors
```bash
mkdir -p ./data/chroma
chmod 755 ./data/chroma
```

## 📚 Documentation

- **Setup Guide:** [`PHASE2_SETUP.md`](PHASE2_SETUP.md)
- **Implementation Plan:** [`PHASE2_PLAN.md`](PHASE2_PLAN.md)
- **Policy Priority:** [`POLICY_PRIORITY.md`](POLICY_PRIORITY.md)
- **Policy Summary:** [`PHASE2_POLICY_SUMMARY.md`](PHASE2_POLICY_SUMMARY.md)

## ✅ Verification

```bash
# 1. Test ChromaDB
python scripts/test_chromadb.py
# Expected: All tests pass

# 2. Index policies
python scripts/index_policies.py
# Expected: 10 policies indexed

# 3. Verify collection
python -c "
from core.rag_provider import RAGFactory
rag = RAGFactory.create_provider('chroma')
rag.initialize('policies')
print(rag.get_collection_stats())
"
# Expected: document_count: 10
```

## 🚀 Next Steps

1. ✅ Setup complete
2. ⏳ Implement policy analyst agent
3. ⏳ Update auditor for dynamic policies
4. ⏳ Integration testing
5. ⏳ Documentation and demo

---

**Quick Start:** `pip install -r requirements.txt && python scripts/test_chromadb.py && python scripts/index_policies.py`
