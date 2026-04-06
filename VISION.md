# ADAG — Product Vision

**AI-Driven Architecture Guardrail**  
A multi-agent system that acts as a Virtual Principal Engineer — intercepting infrastructure-as-code, comparing it against policy standards, and returning intelligent, actionable audit results.

---

## The Three Product Modes

### Mode 1 — Local Python Package

The developer experience: install, point at Terraform, get violations.

```bash
pip install adag
adag scan ./infra/
```

Or programmatically from a test suite or CI pipeline:

```python
from adag import ADAGRunner

runner = ADAGRunner(
    terraform_dir="./infra",
    policies_dir="./policies",   # built-in policies or bring your own
    llm_provider="bedrock",      # or "openai"
)
result = runner.scan()
print(result.violations)
```

**Key properties:**

- Fully offline — no microservices, no ChromaDB needed
- Policies loaded directly from a `policies/` directory (Markdown files)
- All policies fit in the LLM context window — no vector DB required at this scale
- CI-friendly: exits with code `1` on violations
- Output formats: human-readable, JSON, SARIF (for GitHub code scanning)

---

### Mode 2 — MCP Server

Any MCP-aware AI agent (Claude Desktop, Cursor, Continue.dev) can call ADAG as a tool mid-conversation, without the developer leaving their editor.

**Claude Desktop config:**

```json
{
  "mcpServers": {
    "adag": {
      "command": "python",
      "args": ["-m", "adag.mcp_server"]
    }
  }
}
```

**Available tools exposed via MCP:**

| Tool                         | Description                                 |
| ---------------------------- | ------------------------------------------- |
| `check_terraform_file(path)` | Scan a single `.tf` file, return violations |
| `scan_terraform_dir(path)`   | Scan all `.tf` files in a directory         |
| `list_policies()`            | List all active policies and their severity |
| `query_rag(question)`        | Query the RAG store (if enabled)            |
| `ingest_document(path)`      | Add an architecture doc to the RAG store    |

**Key properties:**

- Same engine as Mode 1 — MCP is a thin tool wrapper over the existing LangGraph graph
- Agent can check compliance mid-conversation before suggesting a deployment
- No separate server process for basic use — runs inline via stdio transport

---

### Mode 3 — Advanced RAG (Architecture Ingestion)

The enterprise use case: ingest your own internal standards (Confluence pages, ADRs, draw.io exports, Mermaid diagrams) and audit against them semantically.

```bash
# Index your internal architecture docs
adag ingest ./architecture-docs/
adag ingest confluence://my-space/architecture-standards

# Now audits are enriched with your organisation's specific context
adag scan ./infra/
```

**Key properties:**

- Powered by the existing RAG microservices (`/home/mst/projects/rag`)
- Policy retrieval is semantic — if a policy changes in a doc, the agent knows without a code change
- Supports per-team/per-project `appid` scoping
- Required when: policy count exceeds ~100 docs, or when querying non-policy architecture context

---

## When Do You Need RAG / ChromaDB?

| Scenario                                   | RAG Needed? | Why                                           |
| ------------------------------------------ | ----------- | --------------------------------------------- |
| Scan `.tf` files, built-in policies        | ❌ No       | All policies fit in LLM context (200K tokens) |
| Custom `policies/` folder, up to ~100 docs | ❌ No       | Still fits in context                         |
| 500+ enterprise-wide policies              | ✅ Yes      | Context overflow — need semantic retrieval    |
| Ingest Confluence / ADRs / diagrams        | ✅ Yes      | That IS the ingestion use case                |
| "Does this match our internal standard?"   | ✅ Yes      | Standard lives in vector store                |

**The core insight:** Terraform files are always read directly from disk — no embedding needed. RAG is only used for policy retrieval, and for small-to-medium policy sets the LLM context window is sufficient.

---

## Current State vs. Target State

### What's Built ✅

| Component                     | Status  | Notes                                                                          |
| ----------------------------- | ------- | ------------------------------------------------------------------------------ |
| `intake` agent                | ✅ Done | LLM parses Terraform, extracts resources                                       |
| `policy_analyst` agent        | ✅ Done | Calls RAG REST API for policy retrieval                                        |
| `auditor` agent               | ✅ Done | Cross-checks resources vs. policies, returns typed violations                  |
| LangGraph workflow            | ✅ Done | Stateful, conditional, provider-agnostic                                       |
| LLM provider abstraction      | ✅ Done | Bedrock default, swappable                                                     |
| Database provider abstraction | ✅ Done | SQLite default, swappable                                                      |
| 10 policy Markdown docs       | ✅ Done | Encryption, tagging, multi-AZ, retention, deletion protection, regions, etc.   |
| RAG microservices             | ✅ Done | Separate repo (`/home/mst/projects/rag`), ingest → chunk → embed → add → query |
| Policy indexing script        | ✅ Done | `scripts/index_policies.py`                                                    |
| `USE_RAG=false` bypass        | ✅ Done | Falls back to hardcoded deletion-protection prompt                             |

### What's Needed for Each Mode

**Mode 1 — Package:**
| Gap | Work |
|---|---|
| No `pyproject.toml` | Add package config and entry points |
| `main.py` is ad-hoc CLI | Refactor into `ADAGRunner` class with clean `scan()` API |
| `USE_RAG=false` falls back to hardcoded single policy | Load all `.md` files from `policies/` dir directly instead |
| No result serialisation | Add `.to_json()`, `.to_sarif()` |
| No CI template | Add example GitHub Actions workflow |

**Mode 2 — MCP:**
| Gap | Work |
|---|---|
| No `mcp_server.py` | ~100 lines wrapping existing graph with `@tool` decorators |
| No MCP dependency | Add `mcp` Python SDK to `requirements.txt` |

**Mode 3 — Advanced RAG:**
| Gap | Work |
|---|---|
| `core/rag_provider.py` is empty | Implement clean `RAGProvider` class wrapping the 5 REST endpoints |
| `core/chroma_provider.py` is empty | Optional local ChromaDB fallback when microservices are offline |
| No ingestion UX | Add `adag ingest ./docs/` CLI command or MCP `ingest_document` tool |
| Single hardcoded `appid="archapp"` | Make configurable per project/team |

---

## Target Project Structure

```
adag/                         ← Python package root
├── __init__.py               ← exports ADAGRunner
├── runner.py                 ← ADAGRunner class (wraps core/graph.py)
├── cli.py                    ← click CLI: adag scan / adag ingest
├── mcp_server.py             ← MCP server with @tool decorators  [NEW]
├── agents/                   ← ✅ done
├── core/
│   ├── graph.py              ← ✅ done
│   ├── rag_provider.py       ← ⚠️  empty — REST client for RAG microservices
│   ├── chroma_provider.py    ← ⚠️  empty — optional local fallback
│   └── ...                   ← ✅ done
├── policies/                 ← ✅ 10 built-in policy docs
└── scripts/
    └── index_policies.py     ← ✅ done
pyproject.toml                ← ❌ missing
```

---

## Priority Order

The engine (LangGraph, agents, models, RAG microservices) is done — the hard part is built. What remains is surface-area work.

1. **`pyproject.toml` + `ADAGRunner`** — makes it a real installable package; unlocks Modes 1 and 2
2. **Direct policy loader** — replace the `USE_RAG=false` empty fallback with a disk-based policy loader so Mode 1 works fully offline
3. **`mcp_server.py`** — ~100 lines; massive UX gain for AI agent workflows
4. **`cli.py`** (`adag scan`, `adag ingest`) — developer experience polish and CI integration
5. **Fill `core/rag_provider.py`** — formalises the raw `requests` calls in `policy_analyst.py`; enables clean `ingest` command for Mode 3
