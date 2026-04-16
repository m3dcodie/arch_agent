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
│   └── ...                   ← ✅ done
├── policies/                 ← ✅ 10 built-in policy docs
└── scripts/
    └── index_policies.py     ← ✅ done
pyproject.toml                ← ❌ missing
```

---

## Priority Order

The engine (LangGraph, agents, models, RAG microservices) is done — the hard part is built. What remains is surface-area work and enterprise-readiness.

1. **`pyproject.toml` + `ADAGRunner`** — ✅ Done; installable package with CLI entry point, unlocks Modes 1 and 2
2. **Direct policy loader** — replace the `USE_RAG=false` empty fallback with a disk-based policy loader so Mode 1 works fully offline
3. **`mcp_server.py`** — ~100 lines; massive UX gain for AI agent workflows
4. **`cli.py`** (`adag scan`, `adag ingest`) — developer experience polish and CI integration
5. **Fill `core/rag_provider.py`** — formalises the raw `requests` calls in `policy_analyst.py`; enables clean `ingest` command for Mode 3
6. **SARIF output** — required for GitHub Advanced Security and Azure DevOps native integration; turns scan results into PR annotations without custom tooling
7. **Audit trail and structured logging** — every scan must be recorded with timestamp, file hash, policy version, and result; required for compliance and operational visibility

---

## Roadmap: Enterprise-Readiness Items

These items are not yet in the build plan but are required before ADAG can be positioned in an enterprise procurement conversation alongside tools like Snyk or Checkov.

### SARIF Output (High Priority)

**Why:** SARIF (Static Analysis Results Interchange Format) is the industry standard consumed by GitHub Advanced Security, Azure DevOps, and most enterprise security dashboards. Without it, ADAG results cannot be surfaced as native PR annotations or fed into a SIEM.

**What to build:**

```python
# Target usage
result = runner.scan()
result.to_sarif("adag-results.sarif")   # GitHub Code Scanning compatible
result.to_json("adag-results.json")     # Machine-readable
result.to_text()                        # Human-readable (existing)
```

**SARIF structure required:**

```json
{
  "version": "2.1.0",
  "runs": [{
    "tool": { "driver": { "name": "adag", "version": "0.1.0", "rules": [] } },
    "results": [{
      "ruleId": "delete_protection",
      "level": "error",
      "message": { "text": "Database instance does not have deletion protection enabled" },
      "locations": [{ "physicalLocation": { "artifactLocation": { "uri": "infra/main.tf" }, "region": { "startLine": 3 } } }]
    }]
  }]
}
```

**GitHub Actions integration (example):**

```yaml
- name: Run ADAG scan
  run: adag scan ./infra/ --format sarif --output adag.sarif

- name: Upload SARIF
  uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: adag.sarif
```

**Gap to close:** Add `SARIFSerializer` class in `models/serializers.py`; wire into `ADAGRunner.scan()` and CLI `--format` flag.

---

### Audit Trail and Structured Logging (High Priority)

**Why:** Enterprise compliance teams (SOC 2, ISO 27001, internal audit) require evidence that governance controls ran. "The tool checked it" is not evidence — a timestamped, immutable record of what was checked, against which policy version, and what the result was, is evidence.

**What to build:**

Every scan should produce a structured audit record, persisted to the existing SQLite database (or swappable backend via the existing `DatabaseProvider` abstraction):

```python
@dataclass
class AuditRecord:
    scan_id: str              # UUID
    timestamp: str            # ISO 8601
    file_path: str            # Scanned file
    file_hash: str            # SHA-256 of the scanned content
    policy_version: str       # Git commit or semver of policies dir
    policies_applied: list    # List of policy IDs retrieved and applied
    violations: list          # Typed violation objects
    status: str               # PASSED | FAILED | ERROR
    llm_provider: str         # bedrock / openai / ollama
    llm_model: str            # model ID used
    duration_ms: int          # Wall-clock time for the scan
    token_cost_estimate: float # Approximate LLM token cost in USD
```

**Structured log output (JSON lines, consumable by Datadog / CloudWatch / ELK):**

```json
{"event": "scan_complete", "scan_id": "abc-123", "file": "infra/main.tf", "status": "FAILED", "violations": 2, "policies_applied": ["delete_protection", "encryption_at_rest"], "duration_ms": 3240, "token_cost_usd": 0.0031, "timestamp": "2026-04-16T10:00:00Z"}
```

**Gap to close:**
- Add `AuditRecord` model to `models/`
- Add `AuditLogger` class to `core/` that writes to the existing `DatabaseProvider`
- Wire into `ADAGRunner.scan()` as a post-scan hook
- Add `adag history` CLI command to query past scan records
- Add `LOG_FORMAT=json` env var to switch between human and structured output

---

## Additional Strategic Use Cases

Beyond the three delivery modes, the following high-value applications are viable without significant re-architecture:

| Use Case | Description | Effort |
|---|---|---|
| **PR Review Bot** | GitHub App that triggers on PR open and posts SARIF violations as inline review comments | Medium — requires SARIF output (above) + GitHub App wrapper |
| **Live Drift Detection** | Scan live AWS resources via Boto3 and compare against the same policy engine | Medium — Boto3 integration; new intake agent variant |
| **Cost Governance Policies** | Policies like "all EC2 must use Graviton" open the FinOps buyer persona | Low — purely policy authoring, engine unchanged |
| **Diagram Auditing** | Ingest Mermaid / draw.io and audit architectural patterns (e.g. "WAF must front all public services") | High — new intake agent variant |
| **ADR Auto-Generation** | After a passing scan, emit a draft Architecture Decision Record: "RDS encryption confirmed compliant as of 2026-04-16" | Low — post-scan LLM call |
| **Remediation Agent** | Phase 3: generate a git patch / Terraform snippet to fix each violation automatically | High — new LangGraph node; highest developer adoption driver |
| **Waiver / Approval Workflow** | Human-in-the-loop node: pause on HIGH violations and require architect sign-off via CLI or Slack | Medium — LangGraph interrupt node; critical for preventing tool bypass |
