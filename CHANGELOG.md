# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog (https://keepachangelog.com/) and this
project follows Semantic Versioning (https://semver.org/).

## [1.1.0] - 2026-05-05

### Added

- **Prompt Contract compliance** — both `FALLBACK_AUDITOR_PROMPT` and `build_dynamic_prompt()` in `agents/prompts.py` are now structured using the 5-layer [Prompt Contract](https://github.com/m3dcodie/prompt-contract/) architecture in cache-friendly order: `ROLE_IDENTITY` → `ROLE_AUTHORITY` → `LANGUAGE_FORMAT` → `LANGUAGE_TONE` → `SCOPE_CONTEXT` → `SCOPE_CONSTRAINTS` → `SCOPE_KNOWLEDGE` → `REASONING_STEPS` → `REASONING_REVIEW` → `OBJECTIVE_TASK` → `OBJECTIVE_ANTI_GOALS`
- **`REASONING_STEPS` chain-of-thought** — auditor now enumerates resources, classifies by policy applicability, validates each attribute, and compiles violations in explicit ordered steps before output
- **`REASONING_REVIEW` self-audit gate** — auditor verifies each flagged resource before returning, reducing false positives
- **`agents/prompts.py`** extracted as a dedicated module — all LLM prompt text centralised so prompt engineering changes never require touching agent logic
- **`core/hcl_parser.py`** — standalone deterministic HCL parser (regex-based, no LLM dependency) for structured Terraform resource extraction; supports nested blocks, booleans, numbers, quoted strings, and inline comments
- **`core/llm_utils.py`** — shared `invoke_structured()` utility with structured-output path, plain-JSON fallback, and rate-limit retry logic (exponential backoff, up to 3 attempts)
- **Per-agent model selection** — `INTAKE_MODEL` and `AUDITOR_MODEL` env vars allow different model tiers per agent across all providers, aligned to the [LLM Capability Framework (LCF)](https://github.com/m3dcodie/LLM-Capability-Framework-LCF)
- **6 Architecture Decision Records** — `docs/ADR-001` through `ADR-006` covering agent architecture, LangGraph orchestration, MCP interface, RAG policy retrieval, LLM abstraction, and state management
- **Extended test suite** — 56 unit tests covering auditor helpers, HCL parser edge cases, `invoke_structured` fallback/retry paths, per-agent model selection, intake validation (empty input, oversized input), and dynamic resource discovery
- **README inspiration section** — credits [prompt-contract](https://github.com/m3dcodie/prompt-contract/), [rag-pipeline](https://github.com/m3dcodie/rag-pipeline), [LLM-Capability-Framework-LCF](https://github.com/m3dcodie/LLM-Capability-Framework-LCF), and [adag_test](https://github.com/m3dcodie/adag_test)

### Changed

- **`agents/auditor.py`** refactored — prompt building, resource serialisation, and ID assignment moved to dedicated helpers; LLM invocation delegated to `core/llm_utils.invoke_structured`
- **`agents/intake.py`** refactored — parsing delegated to `core/hcl_parser`; added input size guard (2 MB limit) and empty-input rejection before any LLM call
- **`agents/policy_analyst.py`** refactored — RAG fetch extracted to a testable function; offline fallback (disk policy load) triggered automatically when RAG returns empty chunks
- **`policies/naming_conventions.md`** — clarified that naming policy applies only to AWS-facing identifier attributes, not Terraform block labels
- **`adag/mcp_server.py`** — `ingest_document` tool now sends a JSON body instead of a multipart upload to the context augmentation service
- **`scripts/index_policies.py`** — aligned with updated `core/hcl_parser` and `core/policy_loader` interfaces
- **Documentation** (`docs/ARCHITECTURE.md`, `docs/FUNCTIONALITY.md`, `docs/GETTING_STARTED.md`, `docs/RAG_PIPELINE.md`, `docs/CONTRIBUTING.md`, `docs/TECHNICAL_REFERENCE.md`, `llms.txt`) updated to reflect refactored module boundaries and new features

### Removed

- `rag_service_config.py` — configuration now handled inline in `agents/policy_analyst.py`

---

## [1.0.0] - 2026-04-29

### Added

- Initial public release (v1.0.0):
  - Multi-agent LLM-driven Terraform policy scanner (Intake, Policy Analyst, Auditor)
  - Deterministic HCL parsing and 10 built-in compliance policies
  - Per-agent model selection and provider abstraction (Bedrock, Copilot, HF, Ollama)
  - RAG mode (ChromaDB) for scaling policy documents; MCP server for AI assistant integration
  - Output formats: text, JSON, SARIF
  - CI-ready behavior and example GitHub Actions workflow

### Notes

- Repository history has been rewritten into a single commit (v1.0.0) for a clean start.
- When publishing a new release, update `pyproject.toml`, `README.md` (version badge),
  and add a new section to this changelog with date and summary.

For release process guidance see docs/RELEASING.md.
