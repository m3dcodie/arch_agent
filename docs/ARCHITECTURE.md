# Architecture

ADAG is a multi-agent AI system built on LangGraph. This document covers the system design, agent graph, data flow, provider abstractions, and the key engineering decisions that shaped the implementation.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Three Operating Modes](#2-three-operating-modes)
3. [Multi-Agent Graph](#3-multi-agent-graph)
4. [Agent Responsibilities](#4-agent-responsibilities)
5. [Shared State Machine](#5-shared-state-machine)
6. [LLM Provider Abstraction](#6-llm-provider-abstraction)
7. [RAG Pipeline Overview](#7-rag-pipeline-overview)
8. [Key Design Decisions](#8-key-design-decisions)
9. [Full Scan Sequence](#9-full-scan-sequence)

---

## 1. System Overview

ADAG wraps a three-agent LangGraph workflow behind three surfaces: a CLI, an MCP server, and a programmatic Python API. All three surfaces share the same engine — `core/graph.py` and the three agents.

```
┌─────────────────────────────────────────────────────┐
│                   Surfaces                          │
│                                                     │
│  adag scan ./infra/    │  MCP Server  │  Python API │
│  (CLI)                 │  (stdio)     │  ADAGRunner  │
└────────────┬───────────┴──────┬───────┴──────┬──────┘
             │                  │              │
             └──────────────────▼──────────────┘
                         ADAGRunner
                         (adag/runner.py)
                              │
                         ADAGGraph
                         (core/graph.py)
                              │
              ┌───────────────▼───────────────┐
              │       LangGraph StateGraph     │
              │                               │
              │  intake → policy_analyst →    │
              │          auditor              │
              └───────────────────────────────┘
```

---

## 2. Three Operating Modes

The same engine supports three distinct configurations with no code changes — only environment variables differ.

### Mode 1 — Local Package (Offline)

```
.tf file
   │
   ▼
ADAGRunner ──► LangGraph Graph
                  │
                  ▼
            policies/ (disk)   ← Markdown files loaded directly
                  │
                  ▼
            LLM Provider (Bedrock / Copilot / HuggingFace / Ollama)
                  │
                  ▼
            AuditResult (text / JSON / SARIF)
```

No external services. All policies loaded from `policies/` Markdown files. Suitable for CI pipelines and local developer use.

### Mode 2 — MCP Server

Same as Mode 1, but the entry point is an MCP stdio server (`adag/mcp_server.py`) rather than a CLI command. Any MCP-compatible AI assistant (Claude Desktop, VS Code Copilot) can call ADAG as a tool mid-conversation.

### Mode 3 — Advanced RAG

```
.tf file
   │
   ▼
ADAGRunner ──► LangGraph Graph
                  │
                  ▼
            Context Augmentation Service (localhost:8000)
                  │
          ┌───────┼───────┐
          ▼       ▼       ▼
       Chunk   Embed   Vector Query
       :8002   :8003      :8004
                  │
                  ▼
            Relevant Policy Chunks
                  │
                  ▼
            LLM Provider
                  │
                  ▼
            AuditResult
```

Policies are stored in ChromaDB (via the RAG microservices). Retrieval is semantic — the system queries for policies relevant to the resource types found in the scan. Required when policy count exceeds ~100 documents or when querying non-policy architecture context.

---

## 3. Multi-Agent Graph

The LangGraph graph is defined in `core/graph.py` using `StateGraph(AgentState)`.

```
START
  │
  ▼
┌──────────────────────────────────────────┐
│               intake                     │
│  Deterministic HCL parser                │
│  Regex-based resource extraction         │
│  LLM is never called here                │
└──────────────┬───────────────────────────┘
               │
               │ _should_continue_after_intake()
               ├── "end"            if ERROR or no resources found
               └── "policy_analyst" otherwise
                              │
                              ▼
              ┌───────────────────────────────┐
              │         policy_analyst        │
              │  Retrieves relevant policies  │
              │  RAG (Mode 3) or disk (Mode 1)│
              │  No LLM calls                 │
              └──────────────┬────────────────┘
                             │
                             │ _should_continue_after_policy_analyst()
                             ├── "end"     if ERROR
                             └── "auditor" always (has fallback)
                                          │
                                          ▼
                         ┌───────────────────────────────┐
                         │           auditor             │
                         │  LLM-driven compliance check  │
                         │  Structured output (Pydantic) │
                         │  Exponential backoff on 429s  │
                         └──────────────┬────────────────┘
                                        │
                                        │ _should_remediate()
                                        ├── "end"         if PASSED or ERROR
                                        └── "remediation" if FAILED
                                                   │
                                                   ▼
                              ┌─────────────────────────────┐
                              │        remediation             │
                              │  LLM-driven patch generation  │
                              │  One before/after per violation│
                              │  Nothing written to disk       │
                              └───────────────┬─────────────┘
                                             │
                                            END
```

### Checkpointing

The graph is compiled with a **SQLite checkpointer** (`langgraph-checkpoint-sqlite`). Every `scan()` call generates a fresh `uuid4()` as the `thread_id`, so runs are always independent — no stale checkpoint resumption between scans.

Checkpoints exist for debugging (you can inspect the SQLite DB to see intermediate state) but are never reused across invocations.

---

## 4. Agent Responsibilities

### Agent 1: Intake (`agents/intake.py`)

**Purpose:** Validate input and parse raw Terraform HCL into structured `TerraformResource` objects.

**Key property:** The LLM is **never called** in this agent. All parsing is delegated to `core/hcl_parser.py` (deterministic regex).

**What it does:**

- Validates input: rejects empty content and enforces a 2 MB size limit
- Extracts `resource "TYPE" "NAME" { ... }` blocks using a brace-counting regex walker
- Extracts `provider "NAME" { ... }` blocks
- Parses `key = value` pairs from attribute blocks (handles strings, booleans, numbers, lists)
- Returns **all** resource types found — no hardcoded filter list; downstream agents decide relevance

**Output into state:** `parsed_resources: List[TerraformResource]`, `resource_types: List[str]` (deduplicated list of all resource types present in the file)

**Why no LLM?** LLMs hallucinate attribute values. If you ask an LLM "does this resource have `deletion_protection = true`?", it will sometimes confidently say yes even when the attribute is absent. Regex extraction is 100% reliable for structured HCL.

---

### Agent 2: Policy Analyst (`agents/policy_analyst.py`)

**Purpose:** Retrieve policies relevant to the resource types found by Intake.

**Key property:** No LLM calls — pure retrieval/IO.

**RAG mode** (`USE_RAG=true`):

- Reads `resource_types` from state (set by Intake)
- Constructs a semantic query from found resource types (e.g., `"Policies for aws_db_instance, aws_rds_cluster resources security compliance requirements"`)
- POSTs to `http://localhost:8000/context-augment/{appid}` — the `appid` is URL-encoded to prevent path traversal
- Uses a 10-second HTTP timeout on all requests
- Parses `relevant_chunks` from the response
- Converts chunks to `Policy` objects

**Offline mode** (`USE_RAG=false`):

- Calls `core/policy_loader.py` to load all `.md` files from the `policies/` directory
- Regex extracts policy ID, title, severity, scope, and full text

**Output into state:** `retrieved_policies: List[Policy]`

---

### Agent 3: Auditor (`agents/auditor.py`)

**Purpose:** Cross-check parsed resources against retrieved policies using an LLM.

**Key property:** This is the only agent that makes LLM calls in the audit pass.

**What it does:**

- Builds a prompt containing all resource attributes and all policy texts — prompt templates live in `agents/prompts.py`
- Uses `with_structured_output(ViolationList)` for OpenAI-compatible providers (`method="function_calling"`)
- Falls back to plain text invoke + regex JSON extraction for Ollama and HuggingFace providers
- Implements exponential backoff retry on HTTP 429 rate-limit errors (waits 15s, 30s, 60s)
- LLM invocation, fallback, and retry logic is centralised in `core/llm_utils.invoke_structured`
- Handles S3 companion resources: does not flag `aws_s3_bucket` for encryption if `aws_s3_bucket_server_side_encryption_configuration` is present

**Output into state:** `violations: List[Violation]`, `status: AuditStatus`

---

### Agent 4: Remediation (`agents/remediation.py`)

**Purpose:** Propose inline `before` / `after` HCL patch suggestions for every violation found by the Auditor.

**Key property:** Fires only when `status == FAILED`. Skipped entirely when there are no violations — zero extra LLM calls on passing scans.

**What it does:**

- Receives `violations[]` and the original `iac_code` from state — no access to policy documents
- Makes a single structured LLM call returning a `RemediationReport` (one `RemediationPatch` per violation)
- Each `RemediationPatch` contains: `violation_id` (links back to `Violation.id`), `resource_name`, `before_block` (verbatim from source), `after_block` (minimal corrected HCL), `explanation` (one sentence)
- Nothing is written to disk — patches are stored in state and surfaced to the user as suggestions
- The model used is controlled by `REMEDIATION_MODEL` env var; falls back to the provider default (same as auditor)

**Why this is safe:** The prompt scope is intentionally narrow — the agent receives only violations (structured, Pydantic-validated) and the original source, not raw policy text or live AWS state. Output is always gated by the `RemediationReport` schema enforced by `invoke_structured`.

**Output into state:** `remediation_patches: List[RemediationPatch]`, `remediation_status: RemediationStatus`

---

## 5. Shared State Machine

All agents communicate exclusively through `AgentState` — a LangGraph `TypedDict` passed through the graph. No direct agent-to-agent calls exist.

```python
class AgentState(TypedDict):
    messages: Annotated[list, operator.add]      # append-only message log
    iac_code: str                                # raw Terraform content
    file_path: str                               # source file path
    parsed_resources: List[TerraformResource]    # set by intake
    retrieved_policies: List[Policy]             # set by policy_analyst
    resource_types: List[str]                    # set by policy_analyst
    violations: List[Violation]                  # set by auditor
    status: AuditStatus                          # PENDING → IN_PROGRESS → PASSED/FAILED/ERROR
    remediation_patches: List[RemediationPatch]  # set by remediation (empty when PASSED)
    remediation_status: RemediationStatus        # proposed | skipped | error
    current_node: str                            # for debugging
    error_message: str                           # if status == ERROR
```

### AuditStatus Flow

```
PENDING
   │
   ▼ (graph starts)
IN_PROGRESS
   │
   ├──► PASSED   (no violations found)
   ├──► FAILED   (one or more violations)
   └──► ERROR    (parse error, provider failure, etc.)
```

---

## 6. LLM Provider Abstraction

All LLM providers implement the `LLMProvider` abstract base class and self-register with `LLMFactory` at import time.

```python
# Abstract interface (core/llm_provider.py)
class LLMProvider(ABC):
    @abstractmethod
    def get_model(self, role: str = "default") -> BaseChatModel: ...

# Self-registration at module bottom (e.g., core/bedrock_provider.py)
LLMFactory.register_provider("bedrock", BedrockProvider)
```

### Supported Providers

| Key              | Class                   | Backend                                   | Default Model                                  |
| ---------------- | ----------------------- | ----------------------------------------- | ---------------------------------------------- |
| `bedrock`        | `BedrockProvider`       | `ChatBedrock` (langchain-aws)             | `au.anthropic.claude-sonnet-4-5-20250929-v1:0` |
| `github-copilot` | `GitHubCopilotProvider` | `ChatOpenAI` → `api.githubcopilot.com`    | `claude-sonnet-4.5`                            |
| `huggingface`    | `HuggingFaceProvider`   | `ChatOpenAI` → `router.huggingface.co/v1` | `Qwen/Qwen2.5-7B-Instruct`                     |
| `ollama`         | `OllamaProvider`        | `ChatOllama` (langchain-ollama)           | `deepseek-r1:8b`                               |

### Per-Agent Model Overrides

`INTAKE_MODEL` and `AUDITOR_MODEL` env vars allow different models per agent role. For example, a fast small model for intake (which does no LLM work anyway) and a large model for the auditor.

**All providers support per-agent overrides:** HuggingFace, Ollama, GitHub Copilot, and Bedrock all accept `INTAKE_MODEL` and `AUDITOR_MODEL` env vars. Bedrock uses `model_id` parameter internally while others use `model`.

### Factory Resolution

```python
# core/graph.py — caller never touches provider internals
provider = LLMFactory.create_provider(llm_provider_name)
llm = provider.get_model(role="auditor")
```

---

## 7. RAG Pipeline Overview

The RAG pipeline (Mode 3) is a separate set of five microservices. ADAG calls them via HTTP.

```
Policy .md files
        │
        ▼
  scripts/index_policies.py
        │
        ├─► POST /ingest/{appid}      :8001  ← Ingestion Service
        │         │
        │         ▼
        ├─► POST /chunk/{appid}       :8002  ← Chunking Service
        │         │ (200 tokens, 50 overlap)
        │         ▼
        ├─► POST /embed/{appid}       :8003  ← Embedding Service
        │         │ (HuggingFace router)
        │         ▼
        └─► POST /add_vectors         :8004  ← Vector Store (ChromaDB)


At scan time:
        │
        ▼
  policy_analyst_node
        │
        └─► POST /context-augment/{appid}  :8000  ← Orchestrator
                  │ (semantic query)
                  ▼
            Ranked policy chunks
```

See [RAG_PIPELINE.md](RAG_PIPELINE.md) for full setup and operational details.

---

## 8. Key Design Decisions

### Decision 1: Deterministic Intake Parsing

**Choice:** Remove the LLM from the intake agent entirely; use regex-based HCL parsing.

**Why:** In early development, the intake agent used an LLM to extract resource attributes. This caused false positives: the LLM would hallucinate `deletion_protection = true` for resources that had no such attribute, causing the auditor to miss real violations. Regex extraction of `key = value` pairs is unambiguous for well-formed HCL.

**Trade-off:** The regex parser does not handle all HCL features (dynamic blocks, for_each expressions, variable references). Resources using these features may have incomplete attribute maps. This is an acceptable limitation for the current policy set.

---

### Decision 2: UUID Thread ID Per Run

**Choice:** Every `scan()` call generates a fresh `uuid4()` as the LangGraph `thread_id`.

**Why:** LangGraph checkpointing is designed for resumable workflows (e.g., human-in-the-loop). For audit scans, resumption is never the right behavior — a partial scan from a previous (possibly failed) run should never contaminate a new result. UUID thread IDs guarantee isolation.

**Benefit:** Checkpoints are still written to SQLite, which is useful for post-hoc debugging. You can inspect the DB to see the exact intermediate state at any node for any historical scan.

---

### Decision 3: Structured Output with Fallback

**Choice:** Try `with_structured_output(ViolationList, method="function_calling")` first; fall back to plain text + regex JSON extraction.

**Why:** Not all LLM providers support OpenAI-style function calling. Ollama models and some HuggingFace models do not. The fallback ensures the system works with any LLM that can generate valid JSON, even if it cannot follow the structured output contract.

**Pattern:**

LLM invocation, structured-output fallback, and rate-limit retry are centralised in `core/llm_utils.invoke_structured`. The auditor calls this helper rather than managing the retry loop itself.

```python
# core/llm_utils.py — shared by all agents that need LLM calls
def invoke_structured(llm, prompt, inputs, schema):
    try:
        chain = prompt | llm.with_structured_output(schema, method="function_calling")
        return chain.invoke(inputs)
    except RateLimitError:
        # exponential backoff: 15s, 30s, 60s
        ...
    except Exception:
        # fallback: plain invoke + regex JSON extraction
        return _plain_invoke(llm, prompt, inputs, schema)
```

---

### Decision 4: S3 Companion Resource Awareness

**Choice:** The auditor prompt explicitly handles S3's split-resource pattern.

**Why:** AWS S3 encryption and public access settings are configured on _companion_ resources (`aws_s3_bucket_server_side_encryption_configuration`, `aws_s3_bucket_public_access_block`) rather than on the parent `aws_s3_bucket`. Without this handling, the auditor would incorrectly flag every `aws_s3_bucket` as missing encryption because the encryption attributes are on a different resource block.

**Implementation:** The intake agent extracts companion resources. The auditor prompt includes an explicit instruction: do not flag the parent `aws_s3_bucket` for encryption or public access if the corresponding companion resource is present in the resource list.

---

### Decision 5: Three Modes, One Engine

**Choice:** CLI, MCP server, and programmatic API all use the same `ADAGRunner` → `ADAGGraph` path.

**Why:** Prevents the common anti-pattern of maintaining separate "CLI logic" and "API logic" that drift apart. Every bug fix and feature improvement applies to all surfaces simultaneously.

---

## 9. Full Scan Sequence

The following is the complete sequence for `adag scan bad_terraform.tf --llm-provider github-copilot`:

```
CLI (adag/cli.py)
  │ reads file, creates ADAGRunner
  ▼
ADAGRunner.scan()
  │ generates uuid4 thread_id
  │ calls ADAGGraph.run(state)
  ▼
LangGraph: START → intake_node
  │ validates input (rejects empty / > 2 MB)
  │ regex parses HCL blocks via core/hcl_parser.py
  │ extracts TerraformResource objects
  │ sets parsed_resources, resource_types in state
  │ no LLM call
  ▼
conditional edge: _should_continue_after_intake()
  │ resources found → continue
  ▼
LangGraph: policy_analyst_node
  │ reads resource_types from state (set by intake)
  │ USE_RAG=false → policy_loader.load_all_policies()
  │ reads all .md files from policies/
  │ sets retrieved_policies in state
  │ no LLM call
  ▼
conditional edge: _should_continue_after_policy_analyst()
  │ policies found → continue
  ▼
LangGraph: auditor_node
  │ builds prompt with resources + policies (templates from agents/prompts.py)
  │ calls GitHubCopilotProvider.get_model("auditor")
  │ calls core/llm_utils.invoke_structured (handles fallback + retry)
  │ LLM returns ViolationList JSON
  │ sets violations, status=FAILED in state
  ▼
LangGraph: END
  ▼
ADAGRunner.scan()
  │ converts state.violations → AuditResult
  │ returns AuditResult
  ▼
CLI
  │ formats as text/json/sarif
  │ prints to stdout
  │ exits with code 1 (violations found)
```

**Total LLM calls per scan: 1** (auditor only). Intake and Policy Analyst make zero LLM calls.
