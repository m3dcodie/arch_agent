# ADAG Documentation Outline

This file is the master index for all ADAG documentation. Each section links to its dedicated file and notes where additional depth is needed.

---

## Documentation Map

| File                                                  | Audience       | Purpose                                       |
| ----------------------------------------------------- | -------------- | --------------------------------------------- |
| [README.md](../README.md)                             | Everyone       | Entry point — quick-start, badges, links      |
| [VISION.md](../VISION.md)                             | Everyone       | Why it exists, what problem it solves         |
| [docs/ARCHITECTURE.md](ARCHITECTURE.md)               | Engineers      | System design, agent graph, design decisions  |
| [docs/FUNCTIONALITY.md](FUNCTIONALITY.md)             | Users          | What it does, outputs, CI/CD integration      |
| [docs/GETTING_STARTED.md](GETTING_STARTED.md)         | New users      | Install, configure, first scan                |
| [docs/CONFIGURATION.md](CONFIGURATION.md)             | All users      | Every env var and configuration knob          |
| [docs/POLICIES.md](POLICIES.md)                       | Policy authors | Built-in policies, how to write custom ones   |
| [docs/RAG_PIPELINE.md](RAG_PIPELINE.md)               | Engineers      | Advanced RAG mode, microservices architecture |
| [docs/MCP.md](MCP.md)                                 | AI/agent users | MCP server, Claude Desktop, tool reference    |
| [docs/CONTRIBUTING.md](CONTRIBUTING.md)               | Contributors   | Adding agents, providers, policies            |
| [docs/TECHNICAL_REFERENCE.md](TECHNICAL_REFERENCE.md) | Developers     | API, data models, schemas                     |

---

## Section Summaries

### 1. README (Root)

- Project tagline and one-liner value proposition
- Badges (CI, PyPI, license, Python version)
- Quick-start (5-line install + scan)
- Feature highlights
- Links to all docs
- **→ Needs:** demo GIF/screenshot showing real violation output

### 2. VISION.md

- The problem: IaC drift, manual review doesn't scale
- The solution: autonomous AI agent as a virtual principal engineer
- Three operating modes (Local, MCP, Advanced RAG)
- Learning goals: LangGraph, multi-agent, RAG, MCP, provider abstraction
- Non-goals (not a replacement for Checkov/tfsec)
- **→ Needs:** comparison table with existing tools (Checkov, tfsec, Sentinel)

### 3. ARCHITECTURE.md

- High-level diagram — three operating modes
- Multi-agent LangGraph DAG with conditional edges
- Agent responsibilities (Intake, Policy Analyst, Auditor)
- State machine (AgentState TypedDict, AuditStatus flow)
- LLM provider abstraction (Factory + Registry pattern)
- RAG pipeline overview (5 microservices)
- Key design decisions (deterministic parsing, UUID thread IDs, structured output fallback)
- **→ Needs:** sequence diagram of a full scan (file in → violations out)

### 4. FUNCTIONALITY.md

- Inputs: `.tf` file or directory, custom policies dir
- Policy engine: 10 built-in policies (table)
- Output formats: text, JSON, SARIF (with examples)
- Exit codes: 0/1/2 and CI/CD implications
- MCP tool surface
- **→ Needs:** annotated output examples for each format

### 5. GETTING_STARTED.md

- Prerequisites (Python ≥3.10, one LLM provider)
- Installation (pip install vs. editable install)
- LLM provider setup (Bedrock, GitHub Copilot, HuggingFace, Ollama)
- First scan walkthrough
- MCP server setup
- **→ Needs:** troubleshooting section per provider

### 6. CONFIGURATION.md

- Full env var reference table
- Three operating modes with minimal config for each
- `.env` template
- **→ Needs:** per-mode worked example

### 7. POLICIES.md

- Policy Markdown template with annotated fields
- Built-in policies summary (10 policies, table)
- How to write a custom policy
- How to index policies into RAG (Mode 3)
- Severity guidelines
- **→ Needs:** worked example — writing a new policy from scratch (e.g., `vpc_flow_logs_enabled`)

### 8. RAG_PIPELINE.md

- When to use Mode 3 vs. offline disk mode
- 5-microservice architecture diagram
- How to start the RAG stack
- Running `scripts/index_policies.py`
- How semantic retrieval works
- **→ Needs:** adding custom document sources beyond `policies/`

### 9. MCP.md

- What MCP is and why it matters
- The 5 exposed tools with input/output schemas
- Claude Desktop, VS Code Copilot integration
- Offline vs. RAG-enabled behavior per tool
- **→ Needs:** extending the MCP server with a new tool

### 10. CONTRIBUTING.md

- Repo structure tour
- Adding a new LLM provider
- Adding a new agent node
- Adding a new built-in policy
- Running tests
- Code style
- **→ Needs:** integration test setup for RAG

### 11. TECHNICAL_REFERENCE.md

- `ADAGRunner` public API
- `AuditResult` fields and methods
- `Violation`, `Policy`, `AgentState` schemas
- `AuditStatus` enum
- SARIF output structure
- **→ Needs:** JSON schema exports for Violation and Policy models

---

## Priority for Deep-Dive Writing

| Priority | Document           | Reason                                                |
| -------- | ------------------ | ----------------------------------------------------- |
| 1        | ARCHITECTURE.md    | Core learning payload for LangGraph/multi-agent study |
| 2        | GETTING_STARTED.md | #1 friction point for new users                       |
| 3        | POLICIES.md        | Enables extension without touching code               |
| 4        | FUNCTIONALITY.md   | Concrete examples show CI/CD value                    |
| 5        | RAG_PIPELINE.md    | Most complex, least documented currently              |
| 6        | CONTRIBUTING.md    | Required for the public repo goal                     |
