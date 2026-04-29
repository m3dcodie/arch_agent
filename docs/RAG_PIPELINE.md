# RAG Pipeline (Mode 3)

This document covers the Advanced RAG mode: when to use it, the five-microservice architecture, how to start the stack, and how policy retrieval works at scan time.

---

## Table of Contents

1. [When to Use Mode 3](#1-when-to-use-mode-3)
2. [Architecture Overview](#2-architecture-overview)
3. [Microservice Reference](#3-microservice-reference)
4. [Starting the RAG Stack](#4-starting-the-rag-stack)
5. [Indexing Policies](#5-indexing-policies)
6. [How Semantic Retrieval Works at Scan Time](#6-how-semantic-retrieval-works-at-scan-time)
7. [Adding Custom Document Sources](#7-adding-custom-document-sources)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. When to Use Mode 3

| Scenario                                   | Mode Needed      | Why                                                      |
| ------------------------------------------ | ---------------- | -------------------------------------------------------- |
| CI pipeline, built-in policies             | Mode 1 (offline) | All 10 policies fit in a 200K-token context window       |
| Custom `policies/` folder, up to ~100 docs | Mode 1 (offline) | Still fits in context — RAG adds latency without benefit |
| 500+ enterprise-wide policies              | Mode 3 (RAG)     | Context overflow — need semantic retrieval               |
| Ingest Confluence pages, ADRs, diagrams    | Mode 3 (RAG)     | That IS the ingestion use case                           |
| "Does this match our internal standard?"   | Mode 3 (RAG)     | Internal standard lives in the vector store              |
| Fully offline, air-gapped environment      | Mode 1 (offline) | Microservices require network access                     |

**The core insight:** Terraform files are always read directly from disk — no embedding needed. RAG is only used for _policy retrieval_, and for small-to-medium policy sets the LLM's context window is sufficient.

---

## 2. Architecture Overview

The RAG pipeline is a set of five independent microservices. ADAG calls them via HTTP. The services live in a separate repository (`github.com/your-org/rag`).

```
                    ┌─────────────────────────────────────┐
                    │           Indexing (offline)         │
                    │                                     │
                    │  scripts/index_policies.py          │
                    │         │                           │
                    │         ▼                           │
                    │  POST /ingest/{appid}  (:8001)      │
                    │         │                           │
                    │         ▼                           │
                    │  POST /chunk/{appid}   (:8002)      │
                    │     200 tokens, 50 overlap          │
                    │         │                           │
                    │         ▼                           │
                    │  POST /embed/{appid}   (:8003)      │
                    │     HuggingFace embeddings          │
                    │         │                           │
                    │         ▼                           │
                    │  POST /add_vectors     (:8004)      │
                    │     ChromaDB storage               │
                    └─────────────────────────────────────┘

                    ┌─────────────────────────────────────┐
                    │           Scan Time (runtime)        │
                    │                                     │
                    │  policy_analyst_node                │
                    │         │                           │
                    │         ▼                           │
                    │  POST /context-augment/{appid}      │
                    │             (:8000)                 │
                    │     Orchestration endpoint          │
                    │         │                           │
                    │         ▼                           │
                    │  GET /query/{appid}    (:8004)      │
                    │     ChromaDB retrieval             │
                    │         │                           │
                    │         ▼                           │
                    │  Ranked policy chunks → ADAG        │
                    └─────────────────────────────────────┘
```

---

## 3. Microservice Reference

| Service              | Port | Endpoint                                  | Purpose                                                                                      |
| -------------------- | ---- | ----------------------------------------- | -------------------------------------------------------------------------------------------- |
| Context Augmentation | 8000 | `POST /context-augment/{appid}`           | Orchestration entry point. Accepts a query, calls the vector store, returns ranked chunks.   |
| Ingestion            | 8001 | `POST /ingest/{appid}`                    | Accepts a document (file path, URL, or raw text). Registers it for processing.               |
| Chunking             | 8002 | `POST /chunk/{appid}`                     | Splits documents into chunks using LangChain's text splitter (200 tokens, 50 token overlap). |
| Embedding            | 8003 | `POST /embed/{appid}`                     | Generates vector embeddings using HuggingFace's embedding router.                            |
| Vector Store         | 8004 | `POST /add_vectors`, `GET /query/{appid}` | ChromaDB-backed storage and retrieval.                                                       |

### Request/Response Examples

**Context Augmentation (runtime query):**

```bash
curl -X POST http://localhost:8000/context-augment/archapp \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Policies for aws_db_instance aws_rds_cluster security compliance database"
  }'
```

```json
{
  "relevant_chunks": [
    {
      "chunk_id": "delete_protection_chunk_0",
      "content": "# Deletion Protection Required\n\n## Policy ID `delete_protection`\n...",
      "distance": 0.12,
      "metadata": {
        "policy_id": "delete_protection",
        "severity": "HIGH"
      }
    }
  ]
}
```

**Ingestion (indexing):**

```bash
curl -X POST http://localhost:8001/ingest/archapp \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "local_file",
    "path": "/home/user/arch_agent/policies/delete_protection.md"
  }'
```

---

## 4. Starting the RAG Stack

The RAG microservices are in a separate repository. Clone and start them before running Mode 3 scans.

### Clone the RAG services repo

```bash
git clone https://github.com/your-org/rag.git
cd rag
```

### Install dependencies

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Start all five services

Option A — start each service manually (development):

```bash
# Terminal 1: Vector Store
uvicorn vector_store.main:app --port 8004 --reload

# Terminal 2: Embedding Service
uvicorn embedding.main:app --port 8003 --reload

# Terminal 3: Chunking Service
uvicorn chunking.main:app --port 8002 --reload

# Terminal 4: Ingestion Service
uvicorn ingestion.main:app --port 8001 --reload

# Terminal 5: Context Augmentation (orchestrator)
uvicorn context_augmentation.main:app --port 8000 --reload
```

Option B — start with Docker Compose (recommended):

```bash
docker-compose up
```

### Verify all services are running

```bash
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
curl http://localhost:8004/health
```

Each should return `{"status": "ok"}`.

---

## 5. Indexing Policies

After the services are running, index all policies into ChromaDB.

```bash
cd /path/to/arch_agent

# Enable RAG in env
export USE_RAG=true
export ADAG_APPID=archapp

# Run the indexing script
python scripts/index_policies.py
```

The script prints progress for each policy file:

```
Indexing: policies/delete_protection.md
  → Ingest: 200 OK
  → Chunk: 200 OK (3 chunks)
  → Embed: 200 OK
  → Add vectors: 200 OK
Indexing: policies/encryption_at_rest.md
  → Ingest: 200 OK
  ...
Done. 10 policies indexed.
```

### Re-indexing after policy changes

Run the script again after adding, modifying, or removing policies. Existing chunks are replaced.

---

## 6. How Semantic Retrieval Works at Scan Time

When `USE_RAG=true`, the Policy Analyst agent:

1. **Builds a semantic query** from the resource types found by the Intake agent:

   ```python
   query = f"Policies for {', '.join(resource_types)} resources security compliance requirements database infrastructure policies"
   # e.g.: "Policies for aws_db_instance, aws_rds_cluster resources security compliance..."
   ```

2. **POSTs to the Context Augmentation service** with this query.

3. The service calls the Vector Store to find the most semantically similar policy chunks (by cosine distance in the embedding space).

4. Returns the top-N chunks ranked by distance (lower = more relevant).

5. ADAG converts the chunks back to `Policy` objects and passes them to the Auditor.

### Why semantic retrieval matters

Suppose a policy document says "Database resources must have point-in-time recovery enabled." The query "aws_db_instance backup retention" will find it even though the exact phrase doesn't match — because the embedding model understands the semantic relationship between "backup retention" and "point-in-time recovery."

This becomes critical at scale: when you have 500+ internal policies, you don't want the auditor reading all of them. Semantic retrieval picks the relevant 5-10 for each scan.

---

## 7. Adding Custom Document Sources

You can index any document into the RAG store — not just the built-in policies. This is the key capability for ingesting internal architecture standards.

### Index a single file

```bash
curl -X POST http://localhost:8001/ingest/archapp \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "local_file",
    "path": "/path/to/my-internal-standard.md"
  }'
```

Then chunk, embed, and add:

```bash
# The full pipeline in sequence
curl -X POST http://localhost:8002/chunk/archapp -H "Content-Type: application/json" -d '{"doc_id": "my-internal-standard"}'
curl -X POST http://localhost:8003/embed/archapp  -H "Content-Type: application/json" -d '{"doc_id": "my-internal-standard"}'
curl -X POST http://localhost:8004/add_vectors    -H "Content-Type: application/json" -d '{"doc_id": "my-internal-standard"}'
```

Or use the MCP `ingest_document` tool from Claude Desktop:

```
Please ingest this architecture decision record into ADAG:
/path/to/adr-001-database-standards.md
```

### Supported source types

| Source Type | `source_type` value | Notes                                  |
| ----------- | ------------------- | -------------------------------------- |
| Local file  | `local_file`        | Absolute path to `.md`, `.txt`, `.pdf` |
| Direct text | `direct`            | Pass content inline in `text` field    |
| URL         | `url`               | The service fetches and parses the URL |

### Use a custom `appid` for project-scoping

```bash
# Index a team-specific standard under a different app ID
export ADAG_APPID=my-team-app
python scripts/index_policies.py --policies-dir ./my-team-policies/
```

At scan time, set `ADAG_APPID=my-team-app` so ADAG queries the correct collection.

---

## 8. Troubleshooting

### "Connection refused" on any service port

The service is not running. Check with:

```bash
ps aux | grep uvicorn
# or if using Docker
docker-compose ps
```

### "No relevant chunks returned"

The policies are not indexed. Run `python scripts/index_policies.py` and verify it completes without errors.

### "Embedding service timeout"

The first embedding request can be slow (model loading). Increase timeout or wait for the model to warm up. Subsequent requests are fast.

### "distance > 0.5 for all chunks"

The semantic query does not match the indexed content well. Try:

- Checking that the correct `ADAG_APPID` is set
- Verifying the policies were indexed under the same `appid`
- Simplifying the query to just resource type names

### Chunks return wrong policy

Multiple policies may have similar language. Check which chunks are returned:

```bash
curl -X POST http://localhost:8000/context-augment/archapp \
  -H "Content-Type: application/json" \
  -d '{"query": "aws_db_instance deletion protection"}' \
  | python -m json.tool
```

Review the `distance` values. Anything below 0.3 is a strong match.
