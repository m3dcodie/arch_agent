# Phase 2: RAG-Enabled Knowledge Base Implementation Plan

## 🎯 Executive Summary

Phase 2 transforms ADAG from a single-policy checker into a **dynamic, knowledge-driven system** that can audit against multiple policies stored in a vector database. This eliminates hardcoded rules and enables policy updates without code changes.

**Key Outcome:** The auditor agent will retrieve relevant policies from a RAG system instead of using hardcoded prompts.

---

## 📊 Current State (Phase 1) vs. Target State (Phase 2)

| Aspect | Phase 1 | Phase 2 |
|--------|---------|---------|
| **Policy Storage** | Hardcoded in [`agents/auditor.py`](agents/auditor.py:13) | Vector database (ChromaDB) |
| **Policy Updates** | Requires code changes | Update markdown files, re-index |
| **Policy Count** | 1 (deletion protection) | Multiple (5-10 for MVP) |
| **Retrieval** | N/A | Semantic search via embeddings |
| **Flexibility** | Low | High |

---

## 🏗️ Architecture Design

### RAG Stack Selection for MVP

After evaluating options, here's the recommended stack:

| Component | Technology | Justification |
|-----------|-----------|---------------|
| **Vector Database** | **ChromaDB** | • Embedded (no separate server)<br>• Persistent storage<br>• Easy Python integration<br>• Perfect for MVP scale (< 100 policies) |
| **Embeddings** | **AWS Bedrock Titan Embeddings** | • Already using Bedrock for LLM<br>• No additional auth setup<br>• Cost-effective ($0.0001/1K tokens)<br>• Consistent with existing architecture |
| **Alternative Embeddings** | OpenAI `text-embedding-3-small` | • Fallback option if Bedrock unavailable<br>• Better semantic quality<br>• $0.00002/1K tokens |
| **Document Loader** | LangChain `DirectoryLoader` | • Handles markdown files natively<br>• Metadata extraction<br>• Already in dependency tree |
| **Chunking Strategy** | **Policy-level** (no chunking) | • Each policy is self-contained<br>• Avg size: 500-1000 tokens<br>• No need for semantic splitting |

### Why ChromaDB Over Alternatives?

**Rejected: Pinecone**
- ❌ Requires external service + API keys
- ❌ Overkill for MVP scale
- ✅ Better for production (millions of vectors)

**Rejected: FAISS**
- ❌ No built-in persistence (requires manual save/load)
- ❌ No metadata filtering
- ✅ Faster for large-scale retrieval

**Selected: ChromaDB**
- ✅ Embedded database (single `pip install`)
- ✅ Persistent storage (SQLite backend)
- ✅ Metadata filtering (filter by severity, resource type)
- ✅ Easy migration path to Chroma Cloud later

---

## 🔄 Updated System Architecture

### New Components

```
┌─────────────────────────────────────────────────────────────┐
│                    PHASE 2 ARCHITECTURE                      │
└─────────────────────────────────────────────────────────────┘

┌──────────────┐
│  Policy Docs │  (Markdown files in /policies)
│  *.md files  │
└──────┬───────┘
       │
       │ (One-time indexing)
       ▼
┌──────────────────┐
│  Policy Indexer  │  New utility script
│  - Load .md      │
│  - Extract meta  │
│  - Generate emb. │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│   ChromaDB       │  Vector store (./data/chroma/)
│   Collection:    │
│   "policies"     │
└──────┬───────────┘
       │
       │ (Runtime retrieval)
       ▼
┌──────────────────┐
│  Policy Analyst  │  New LangGraph node
│  Agent           │  (RAG retrieval)
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  Auditor Agent   │  Modified to use retrieved policies
│  (Enhanced)      │
└──────────────────┘
```

### Updated LangGraph Workflow

```
START
  │
  ▼
┌─────────────┐
│   Intake    │  Parse Terraform (unchanged)
│   Agent     │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Policy    │  NEW: Retrieve relevant policies
│   Analyst   │  - Query: resource types from intake
│             │  - Returns: Top 3-5 relevant policies
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Auditor    │  MODIFIED: Use retrieved policies
│   Agent     │  - Dynamic prompt construction
│             │  - Multi-policy checking
└──────┬──────┘
       │
       ▼
     END
```

---

## 📁 New File Structure

```
/adag-system
├── agents/
│   ├── intake.py           # Unchanged
│   ├── auditor.py          # MODIFIED: Dynamic policy handling
│   └── policy_analyst.py   # NEW: RAG retrieval agent
├── core/
│   ├── llm_provider.py     # Unchanged
│   ├── bedrock_provider.py # MODIFIED: Add embeddings support
│   ├── rag_provider.py     # NEW: Vector DB abstraction
│   ├── chroma_provider.py  # NEW: ChromaDB implementation
│   ├── state.py            # MODIFIED: Add retrieved_policies field
│   └── graph.py            # MODIFIED: Add policy_analyst node
├── models/
│   ├── violations.py       # Unchanged
│   └── policy.py           # NEW: Policy Pydantic models
├── policies/
│   ├── delete_protection.md        # Existing
│   ├── encryption_at_rest.md       # NEW (example)
│   ├── multi_az_requirement.md     # NEW (example)
│   ├── backup_retention.md         # NEW (example)
│   └── public_access_block.md      # NEW (example)
├── scripts/
│   └── index_policies.py   # NEW: Policy indexing utility
├── data/
│   ├── adag.db            # Existing (LangGraph checkpoints)
│   └── chroma/            # NEW: ChromaDB storage
├── tests/
│   ├── test_adag.py       # MODIFIED: Add RAG tests
│   └── test_rag.py        # NEW: RAG-specific tests
└── requirements.txt        # MODIFIED: Add chromadb, sentence-transformers
```

---

## 🔧 Implementation Details

### 1. Enhanced State Schema

**File:** [`core/state.py`](core/state.py:1)

```python
from typing import Annotated, List
from typing_extensions import TypedDict
import operator

from models.violations import Violation, TerraformResource, AuditStatus
from models.policy import Policy  # NEW

class AgentState(TypedDict):
    """Enhanced state with RAG support"""
    
    # Existing fields
    messages: Annotated[list, operator.add]
    iac_code: str
    file_path: str
    parsed_resources: List[TerraformResource]
    violations: List[Violation]
    status: AuditStatus
    current_node: str
    error_message: str
    
    # NEW: Phase 2 fields
    retrieved_policies: List[Policy]  # Policies from RAG
    resource_types: List[str]         # Extracted resource types for query
```

### 2. Policy Model

**File:** `models/policy.py` (NEW)

```python
from pydantic import BaseModel, Field
from typing import List, Optional

class Policy(BaseModel):
    """Represents a single architecture policy"""
    
    id: str = Field(description="Unique policy identifier (e.g., 'delete_protection')")
    title: str = Field(description="Human-readable policy name")
    severity: str = Field(description="HIGH, MEDIUM, or LOW")
    description: str = Field(description="What the policy enforces")
    scope: List[str] = Field(description="Resource types this applies to")
    requirements: str = Field(description="Specific technical requirements")
    examples_compliant: str = Field(description="Example of compliant code")
    examples_non_compliant: str = Field(description="Example of violations")
    remediation: str = Field(description="How to fix violations")
    
    # Metadata for retrieval
    file_path: Optional[str] = None
    chunk_id: Optional[str] = None
```

### 3. RAG Provider Abstraction

**File:** `core/rag_provider.py` (NEW)

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class RAGProvider(ABC):
    """Abstract base class for RAG/Vector DB providers"""
    
    @abstractmethod
    def initialize(self, collection_name: str):
        """Initialize the vector database"""
        pass
    
    @abstractmethod
    def index_documents(self, documents: List[Dict[str, Any]]):
        """Index documents into the vector store"""
        pass
    
    @abstractmethod
    def retrieve(self, query: str, top_k: int = 5, filters: Dict = None) -> List[Dict]:
        """Retrieve relevant documents"""
        pass
    
    @abstractmethod
    def delete_collection(self):
        """Delete the collection (for re-indexing)"""
        pass

class RAGFactory:
    """Factory for creating RAG providers"""
    
    _providers = {}
    
    @classmethod
    def register_provider(cls, name: str, provider_class):
        cls._providers[name] = provider_class
    
    @classmethod
    def create_provider(cls, name: str, **config):
        if name not in cls._providers:
            raise ValueError(f"Unknown RAG provider: {name}")
        return cls._providers[name](**config)
```

### 4. ChromaDB Implementation

**File:** `core/chroma_provider.py` (NEW)

```python
import os
import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any

from core.rag_provider import RAGProvider, RAGFactory

class ChromaProvider(RAGProvider):
    """ChromaDB implementation for vector storage"""
    
    def __init__(self, persist_directory: str = "./data/chroma"):
        self.persist_directory = persist_directory
        self.client = None
        self.collection = None
        
    def initialize(self, collection_name: str = "policies"):
        """Initialize ChromaDB with persistent storage"""
        os.makedirs(self.persist_directory, exist_ok=True)
        
        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}  # Use cosine similarity
        )
        
    def index_documents(self, documents: List[Dict[str, Any]]):
        """Index policy documents"""
        ids = [doc["id"] for doc in documents]
        texts = [doc["content"] for doc in documents]
        metadatas = [doc["metadata"] for doc in documents]
        
        self.collection.add(
            ids=ids,
            documents=texts,
            metadatas=metadatas
        )
        
    def retrieve(self, query: str, top_k: int = 5, filters: Dict = None) -> List[Dict]:
        """Retrieve relevant policies"""
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k,
            where=filters  # e.g., {"severity": "HIGH"}
        )
        
        # Format results
        retrieved = []
        for i in range(len(results["ids"][0])):
            retrieved.append({
                "id": results["ids"][0][i],
                "content": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i] if "distances" in results else None
            })
        
        return retrieved
    
    def delete_collection(self):
        """Delete collection for re-indexing"""
        if self.collection:
            self.client.delete_collection(self.collection.name)

# Register with factory
RAGFactory.register_provider("chroma", ChromaProvider)
```

### 5. Policy Indexing Script

**File:** `scripts/index_policies.py` (NEW)

```python
#!/usr/bin/env python3
"""
Index policy documents into ChromaDB.

Usage:
    python scripts/index_policies.py [--reindex]
"""
import os
import sys
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.rag_provider import RAGFactory

def parse_policy_markdown(file_path: str) -> dict:
    """
    Parse a policy markdown file and extract structured data.
    
    Expected format:
    # Policy Title
    ## Policy ID
    `policy_id`
    ## Severity
    **HIGH**
    ...
    """
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Simple parsing (can be enhanced with proper MD parser)
    lines = content.split('\n')
    
    policy_data = {
        "id": "",
        "title": "",
        "severity": "",
        "content": content,  # Full content for embedding
        "file_path": file_path
    }
    
    # Extract metadata
    for i, line in enumerate(lines):
        if line.startswith('# ') and not policy_data["title"]:
            policy_data["title"] = line[2:].strip()
        elif '`' in line and not policy_data["id"]:
            # Extract policy ID from backticks
            policy_data["id"] = line.split('`')[1]
        elif '**HIGH**' in line or '**MEDIUM**' in line or '**LOW**' in line:
            policy_data["severity"] = line.split('**')[1]
    
    return policy_data

def index_policies(policies_dir: str = "./policies", reindex: bool = False):
    """Index all policy files"""
    
    # Initialize RAG provider
    rag = RAGFactory.create_provider("chroma")
    rag.initialize(collection_name="policies")
    
    # Reindex if requested
    if reindex:
        print("🔄 Deleting existing collection...")
        rag.delete_collection()
        rag.initialize(collection_name="policies")
    
    # Find all markdown files
    policy_files = list(Path(policies_dir).glob("*.md"))
    print(f"📄 Found {len(policy_files)} policy files")
    
    # Parse and index
    documents = []
    for policy_file in policy_files:
        print(f"   Processing: {policy_file.name}")
        policy_data = parse_policy_markdown(str(policy_file))
        
        documents.append({
            "id": policy_data["id"],
            "content": policy_data["content"],
            "metadata": {
                "title": policy_data["title"],
                "severity": policy_data["severity"],
                "file_path": str(policy_file)
            }
        })
    
    # Index all documents
    print(f"💾 Indexing {len(documents)} policies...")
    rag.index_documents(documents)
    
    print("✅ Indexing complete!")
    
    # Test retrieval
    print("\n🔍 Testing retrieval...")
    results = rag.retrieve("database deletion protection", top_k=3)
    print(f"   Retrieved {len(results)} policies:")
    for result in results:
        print(f"   - {result['metadata']['title']} (distance: {result.get('distance', 'N/A')})")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Index policy documents")
    parser.add_argument("--reindex", action="store_true", help="Delete and reindex all policies")
    args = parser.parse_args()
    
    index_policies(reindex=args.reindex)
```

### 6. Policy Analyst Agent

**File:** `agents/policy_analyst.py` (NEW)

```python
"""
Policy Analyst agent - Retrieves relevant policies via RAG.
"""
from typing import Dict, Any, List
from core.state import AgentState
from core.rag_provider import RAGFactory
from models.policy import Policy

def policy_analyst_node(state: AgentState) -> Dict[str, Any]:
    """
    Retrieve relevant policies based on parsed resources.
    
    Args:
        state: Current agent state
        
    Returns:
        Dict with retrieved_policies field
    """
    try:
        parsed_resources = state.get("parsed_resources", [])
        
        if not parsed_resources:
            return {
                "retrieved_policies": [],
                "current_node": "policy_analyst",
                "messages": ["[POLICY_ANALYST] No resources to analyze"]
            }
        
        # Extract resource types
        resource_types = list(set([r.resource_type for r in parsed_resources]))
        
        # Build query
        query = f"Policies for {', '.join(resource_types)} resources"
        
        # Initialize RAG
        rag = RAGFactory.create_provider("chroma")
        rag.initialize(collection_name="policies")
        
        # Retrieve policies
        results = rag.retrieve(query, top_k=5)
        
        # Convert to Policy objects
        retrieved_policies = []
        for result in results:
            # Parse the content to extract policy details
            # (Simplified - in production, store structured data)
            policy = Policy(
                id=result["id"],
                title=result["metadata"]["title"],
                severity=result["metadata"]["severity"],
                description=result["content"][:200],  # Truncated
                scope=resource_types,
                requirements=result["content"],  # Full content
                examples_compliant="",
                examples_non_compliant="",
                remediation="",
                file_path=result["metadata"]["file_path"]
            )
            retrieved_policies.append(policy)
        
        return {
            "retrieved_policies": retrieved_policies,
            "resource_types": resource_types,
            "current_node": "policy_analyst",
            "messages": [f"[POLICY_ANALYST] Retrieved {len(retrieved_policies)} relevant policies"]
        }
        
    except Exception as e:
        return {
            "retrieved_policies": [],
            "resource_types": [],
            "current_node": "policy_analyst",
            "error_message": f"Policy analyst failed: {str(e)}",
            "messages": [f"[POLICY_ANALYST] ERROR: {str(e)}"]
        }
```

### 7. Modified Auditor Agent

**File:** [`agents/auditor.py`](agents/auditor.py:1) (MODIFIED)

Key changes:
- Remove hardcoded `AUDITOR_PROMPT`
- Build dynamic prompt from `state["retrieved_policies"]`
- Support multi-policy checking

```python
def auditor_node(state: AgentState, llm: BaseChatModel) -> Dict[str, Any]:
    """
    Audit parsed resources against retrieved policies.
    """
    try:
        parsed_resources = state.get("parsed_resources", [])
        retrieved_policies = state.get("retrieved_policies", [])
        
        if not parsed_resources:
            return {
                "violations": [],
                "status": AuditStatus.PASSED,
                "messages": ["[AUDITOR] No resources to audit"]
            }
        
        if not retrieved_policies:
            return {
                "violations": [],
                "status": AuditStatus.ERROR,
                "error_message": "No policies retrieved",
                "messages": ["[AUDITOR] ERROR: No policies available"]
            }
        
        # Build dynamic prompt from retrieved policies
        prompt = _build_dynamic_prompt(parsed_resources, retrieved_policies)
        
        # Rest of auditing logic...
        # (Use structured output as before)
        
    except Exception as e:
        # Error handling...
        pass

def _build_dynamic_prompt(resources, policies):
    """Build audit prompt from retrieved policies"""
    prompt = "You are a security auditor. Check the following resources against these policies:\n\n"
    
    for policy in policies:
        prompt += f"## Policy: {policy.title}\n"
        prompt += f"Severity: {policy.severity}\n"
        prompt += f"Requirements: {policy.requirements}\n\n"
    
    prompt += "\nResources to audit:\n"
    prompt += _format_resources_for_prompt(resources)
    
    return prompt
```

---

## 📦 Updated Dependencies

**File:** [`requirements.txt`](requirements.txt:1)

```txt
# Existing dependencies
langgraph>=0.0.20
langchain>=0.1.0
langchain-aws>=0.1.0
boto3>=1.34.0
pydantic>=2.5.0
python-dotenv>=1.0.0
pytest>=7.4.0
pytest-cov>=4.1.0

# NEW: Phase 2 dependencies
chromadb>=0.4.22          # Vector database
sentence-transformers>=2.3.0  # For local embeddings (optional)
```

---

## 🧪 Testing Strategy

### Unit Tests

**File:** `tests/test_rag.py` (NEW)

```python
import pytest
from core.rag_provider import RAGFactory

def test_chroma_initialization():
    """Test ChromaDB initialization"""
    rag = RAGFactory.create_provider("chroma", persist_directory="./test_data")
    rag.initialize("test_policies")
    assert rag.collection is not None

def test_policy_indexing():
    """Test indexing policy documents"""
    rag = RAGFactory.create_provider("chroma", persist_directory="./test_data")
    rag.initialize("test_policies")
    
    documents = [
        {
            "id": "test_policy_1",
            "content": "All databases must have encryption enabled",
            "metadata": {"severity": "HIGH", "title": "Encryption Policy"}
        }
    ]
    
    rag.index_documents(documents)
    results = rag.retrieve("database encryption", top_k=1)
    
    assert len(results) == 1
    assert results[0]["id"] == "test_policy_1"

def test_policy_retrieval_relevance():
    """Test that retrieval returns relevant policies"""
    # Test semantic search quality
    pass
```

### Integration Tests

**File:** [`tests/test_adag.py`](tests/test_adag.py:1) (MODIFIED)

Add tests for:
- Policy analyst node execution
- Multi-policy auditing
- RAG retrieval accuracy

---

## 📈 Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Policy Retrieval Accuracy** | > 90% | Manual review of top-3 results |
| **Retrieval Latency** | < 100ms | Time to retrieve 5 policies |
| **False Positive Rate** | < 10% | Violations that aren't real issues |
| **Policy Coverage** | 5-10 policies | Number of indexed policies |

---

## 🚀 Implementation Roadmap

### Week 1: Foundation
- [ ] Day 1-2: Implement RAG provider abstraction
- [ ] Day 3-4: Implement ChromaDB provider
- [ ] Day 5: Create policy indexing script

### Week 2: Integration
- [ ] Day 1-2: Add policy analyst agent
- [ ] Day 3-4: Modify auditor for dynamic policies
- [ ] Day 5: Update LangGraph workflow

### Week 3: Testing & Polish
- [ ] Day 1-2: Write comprehensive tests
- [ ] Day 3: Create 5+ additional policy documents
- [ ] Day 4: Performance optimization
- [ ] Day 5: Documentation and demo

---

## 🎓 Architecture Decision Records

### ADR-005: ChromaDB for MVP Vector Storage
**Decision:** Use ChromaDB as the vector database  
**Rationale:**  
- Embedded solution (no separate server)
- Persistent storage out of the box
- Perfect for MVP scale (< 100 policies)
- Easy migration to Chroma Cloud for production

**Trade-offs:**  
- Not suitable for distributed systems (yet)
- Limited to ~1M vectors (sufficient for our use case)

**Alternatives Considered:**
- Pinecone: Requires external service, overkill for MVP
- FAISS: No persistence, no metadata filtering
- Weaviate: Too complex for MVP

### ADR-006: Policy-Level Chunking Strategy
**Decision:** Index entire policy documents without chunking  
**Rationale:**  
- Each policy is self-contained (500-1000 tokens)
- Policies have clear boundaries (one per file)
- Chunking would break semantic coherence

**Trade-offs:**  
- May need chunking if policies grow > 2000 tokens
- Less granular retrieval (but acceptable for MVP)

### ADR-007: AWS Bedrock Titan Embeddings
**Decision:** Use Bedrock Titan Embeddings for vector generation  
**Rationale:**  
- Already using Bedrock for LLM
- No additional authentication setup
- Consistent with existing architecture
- Cost-effective ($0.0001/1K tokens)

**Trade-offs:**  
- Tied to AWS ecosystem
- Slightly lower quality than OpenAI embeddings
- Fallback to OpenAI available if needed

---

## 💰 Cost Analysis

### Embedding Costs (AWS Bedrock Titan)
- **Policy Indexing:** 10 policies × 800 tokens = 8,000 tokens
- **Cost:** $0.0001 × 8 = **$0.0008** (one-time)

### Retrieval Costs
- **Per Audit:** 1 query × 50 tokens = 50 tokens
- **Cost:** $0.0001 × 0.05 = **$0.000005** per audit
- **Monthly (1000 audits):** **$0.005**

### LLM Costs (Unchanged)
- Claude Sonnet 4.5: ~$0.003 per audit
- **Monthly (1000 audits):** **$3.00**

**Total Phase 2 Cost:** ~$3.01/month for 1000 audits (negligible increase)

---

## 🔐 Security Considerations

1. **Data Privacy:** Policies stored locally in ChromaDB (no external service)
2. **Access Control:** File system permissions on `./data/chroma/`
3. **Embedding Privacy:** Bedrock has zero-retention policy
4. **Audit Trail:** Log all policy retrievals for compliance

---

## 📚 Documentation Updates Needed

1. Update [`README.md`](README.md:1) with Phase 2 features
2. Create `docs/RAG_ARCHITECTURE.md` with detailed design
3. Add policy authoring guide: `docs/POLICY_AUTHORING.md`
4. Update installation instructions for ChromaDB

---

## 🎯 MVP Scope (Phase 2)

### In Scope
✅ ChromaDB integration  
✅ Policy indexing script  
✅ Policy analyst agent  
✅ Dynamic auditor prompts  
✅ 5-10 policy documents  
✅ Basic retrieval testing  

### Out of Scope (Future Phases)
❌ Policy versioning  
❌ Multi-language support  
❌ Advanced chunking strategies  
❌ Hybrid search (keyword + semantic)  
❌ Policy conflict resolution  
❌ A/B testing of embeddings  

---

## 🤝 Migration Path from Phase 1

### Backward Compatibility
- Phase 1 code continues to work
- RAG is opt-in via environment variable: `USE_RAG=true`
- Fallback to hardcoded prompt if RAG unavailable

### Migration Steps
1. Install new dependencies: `pip install -r requirements.txt`
2. Index policies: `python scripts/index_policies.py`
3. Enable RAG: Set `USE_RAG=true` in `.env`
4. Test: `python main.py tests/fixtures/bad_terraform.tf`

---

## 📞 Next Steps

1. **Review this plan** with stakeholders
2. **Prioritize policies** to create (beyond deletion protection)
3. **Set up development environment** with ChromaDB
4. **Begin Week 1 implementation** (RAG provider abstraction)

---

**Questions for Discussion:**
1. Should we support hybrid search (keyword + semantic)?
2. Do we need policy versioning in Phase 2 or defer to Phase 3?
3. Should we create a web UI for policy management?
4. What's the priority order for new policies?

---

**Built with:** ChromaDB • AWS Bedrock Titan • LangChain • Python 3.11+
