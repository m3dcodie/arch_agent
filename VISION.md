# ADAG — Vision

**AI-Driven Architecture Guardrail**

A multi-agent system that acts as a Virtual Principal Engineer — intercepting infrastructure-as-code, comparing it against policy standards, and returning intelligent, actionable audit results.

This project serves two purposes simultaneously: it is a **working, production-quality tool** and a **learning vehicle** for modern AI engineering patterns.

---

## The Problem

Organisations write Terraform. Organisations also write architecture policies. These two artefacts drift apart constantly.

- Policies live in Confluence, ADRs, or a principal engineer's head
- Terraform lives in Git, reviewed by developers who may not know the policies
- Manual policy review doesn't scale beyond a small team
- Existing static analysis tools (Checkov, tfsec) check syntax and known CVEs — they cannot reason about *your organisation's specific standards*

**The result:** databases without deletion protection, S3 buckets without encryption, resources deployed to disallowed regions — discovered in a post-incident review, not a PR review.

---

## The Solution

ADAG intercepts Terraform before deployment and checks it against a policy knowledge base using an LLM auditor. The LLM can reason about nuanced, organisation-specific requirements that no static analysis rule can capture.

**The virtual principal engineer:** instead of "I'll ask the principal engineer to review this," you get an automated review with the same depth of reasoning — available in CI, in your editor, or on demand from Claude.

---

## What ADAG Is Not

ADAG is **complementary to** — not a replacement for — tools like Checkov, tfsec, or Terraform Sentinel.

| Tool | What it does | When to use it |
|---|---|---|
| **Checkov / tfsec** | Static rules, CVE databases, known misconfigs | Always — fast, deterministic, no LLM cost |
| **Terraform Sentinel** | Policy-as-code enforcement gates | Enterprise Terraform Cloud/Enterprise |
| **ADAG** | LLM reasoning over organisation-specific policies | When your policies can't be expressed as static rules |

Use ADAG alongside existing tools, not instead of them.

---

## Three Operating Modes

### Mode 1 — Local Package (Offline)

The developer experience: install, point at Terraform, get violations.

```bash
pip install adag
adag scan ./infra/
```

Or programmatically from a test suite or CI pipeline:

```python
from adag import ADAGRunner

runner = ADAGRunner(llm_provider="github-copilot")
result = runner.scan("./infra/main.tf")
print(result.violations)
```

**Properties:**
- Fully offline — no microservices required
- Policies loaded from `policies/` directory (Markdown files)
- All built-in policies fit in the LLM context window — no vector DB needed
- CI-friendly: exit code `1` on violations
- Output: human-readable text, JSON, SARIF

---

### Mode 2 — MCP Server

Any MCP-compatible AI assistant (Claude Desktop, VS Code Copilot, Cursor) can call ADAG as a tool mid-conversation — without the developer leaving their editor.

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

**Properties:**
- Same engine as Mode 1 — MCP is a thin wrapper over the existing LangGraph graph
- AI assistant can check compliance before suggesting a deployment
- No separate server process for basic use (stdio transport)

---

### Mode 3 — Advanced RAG (Architecture Ingestion)

The enterprise use case: ingest your internal standards (Confluence pages, ADRs, Mermaid diagrams) and audit against them semantically.

```bash
# Index your internal architecture docs
python scripts/index_policies.py --policies-dir ./architecture-docs/

# Audits are now enriched with your organisation's specific context
USE_RAG=true adag scan ./infra/
```

**Properties:**
- Powered by a 5-microservice RAG pipeline (ingestion → chunking → embedding → ChromaDB → retrieval)
- Policy retrieval is semantic — if a policy changes in a doc, the agent knows without a code change
- Supports per-team/per-project `appid` scoping
- Required when: policy count exceeds ~100 docs, or when querying non-policy architecture context

---

## When Do You Need RAG?

| Scenario | RAG needed? | Why |
|---|---|---|
| Scan `.tf` files, built-in policies | No | All 10 policies fit in LLM context (200K tokens) |
| Custom `policies/` folder, up to ~100 docs | No | Still fits in context |
| 500+ enterprise-wide policies | Yes | Context overflow — semantic retrieval required |
| Ingest Confluence / ADRs / diagrams | Yes | That IS the ingestion use case |
| "Does this match our internal standard?" | Yes | Standard lives in the vector store |

---

## What This Project Demonstrates

ADAG was built to learn and demonstrate these patterns in a realistic context:

### LangGraph — Stateful Multi-Agent Workflows
How to model a multi-step AI workflow as a directed graph with typed state, conditional routing, and SQLite-backed checkpointing. How to isolate each agent's responsibilities and communicate only through shared state.

### Multi-Agent Systems — Separation of Concerns
Why different agents should have different responsibilities. Intake is deterministic (no LLM). Policy Analyst is retrieval-only (no LLM). Auditor is the only LLM caller. This separation makes the system testable, debuggable, and extensible.

### RAG — Retrieval-Augmented Generation
How to build a full RAG pipeline from document ingestion through chunking, embedding, vector storage, and semantic retrieval. How to choose between context-window loading (Mode 1) and semantic retrieval (Mode 3) based on scale.

### MCP — Model Context Protocol
How to expose an existing tool as an MCP server so any AI assistant can call it as a tool. The difference between "the LLM writes code" and "the LLM calls a real tool that actually runs."

### LLM Provider Abstraction
How to design a provider abstraction that makes the LLM backend a configuration choice, not a code change. Factory + Registry pattern for self-registering providers. Structured output with fallback for providers that don't support function calling.

### Deterministic vs. LLM Parsing
Why the intake agent was moved off LLM-based parsing: LLMs hallucinate attribute values, causing false positives. This is a real engineering lesson — not every step in an AI system should involve an LLM.

---

## Current State

All MVP functionality is complete. The system is production-quality for the scope it covers.

| Component | Status |
|---|---|
| Intake agent (deterministic HCL parser) | Complete |
| Policy Analyst (disk + RAG modes) | Complete |
| Auditor agent (structured output, retry, rate limiting) | Complete |
| LangGraph workflow | Complete |
| LLM provider abstraction (Bedrock, Copilot, HuggingFace, Ollama) | Complete |
| 10 built-in policy documents | Complete |
| `ADAGRunner` public API | Complete |
| CLI (`adag scan`, JSON, SARIF) | Complete |
| MCP server (5 tools) | Complete |
| `pyproject.toml` installable package | Complete |
| Offline disk-based policy loader | Complete |
| RAG microservices integration | Complete (separate repo) |
| Audit trail / structured logging | Future work |
| Additional resource types (Lambda, ECS, etc.) | Future work |

---

## Future Directions

- **Audit trail:** every scan recorded with timestamp, file hash, policy version, result — for compliance and trend analysis
- **Remediation agent:** generate a `terraform fmt`-ready patch for each violation
- **Validator agent:** a second LLM pass to catch false positives before reporting
- **More resource types:** Lambda, ECS, EKS, VPC, IAM roles
- **Pre-commit hook:** block commits that introduce violations
- **VS Code extension:** inline violation highlighting in the editor
