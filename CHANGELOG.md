# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog (https://keepachangelog.com/) and this
project follows Semantic Versioning (https://semver.org/).

## [1.2.0] - 2026-05-19

### Added

- **Unified sampling parameters** — `LLM_TEMPERATURE` and `LLM_MAX_TOKENS` now apply across all providers (Bedrock, GitHub Copilot, GitHub Models, HuggingFace, Ollama) from a single env var; provider-specific vars (`BEDROCK_TEMPERATURE`, `HF_MAX_TOKENS`, etc.) remain supported as per-provider overrides with the same fallback chain
- **Grammar-constrained JSON decoding for Ollama** — `format="json"` added to `OllamaProvider`, enabling GBNF grammar enforcement at the model kernel level; prevents invalid JSON on the plain-invoke fallback path where local models do not support function calling
- **Input/output cost breakdown in logs** — `[COST]` log lines and `llm.invoke` audit events now emit `input_cost_usd` and `output_cost_usd` separately in addition to `estimated_cost_usd`; makes the 3–5× price difference between input and output tokens visible per call
- **`_estimate_cost_breakdown()` helper** in `core/cost_tracker.py` — returns `(input_usd, output_usd)` tuple using the correct per-million rate for each token direction
- **`local_response_tokens` fix** — when `with_structured_output` (function calling) succeeds, `raw_msg.content` is `""` (response payload is in `tool_calls`); the local tokenizer now falls back to the serialised Pydantic result JSON so `local_response_tokens` is populated instead of logging `N/A`
- **Sampling parameters section in README** — documents `LLM_TEMPERATURE` and `LLM_MAX_TOKENS`, explains why `temperature=0` is mandatory for deterministic compliance checking, and explicitly states that `top_k` and `top_p` are irrelevant at temperature 0

### Changed

- **`temperature` default set to `0` on all providers** — Bedrock and Ollama previously used framework defaults (~1.0 and 0.8 respectively), causing non-deterministic audit results; GitHub Copilot and HuggingFace defaults lowered from `0.1` to `0`
- **`max_tokens` default unified to `4096`** — HuggingFace default raised from `2048`; Bedrock now sets `max_tokens` explicitly (was unset); all providers fall back to `LLM_MAX_TOKENS`
- **`BEDROCK_TEMPERATURE` and `BEDROCK_MAX_TOKENS`** added to `BedrockProvider` — Bedrock previously had no temperature or max_tokens control at all
- **`OLLAMA_TEMPERATURE`** added to `OllamaProvider` with fallback to `LLM_TEMPERATURE`
- **`.env.example`** — replaced provider-specific temperature/max_tokens vars with `LLM_TEMPERATURE=0` and `LLM_MAX_TOKENS=4096` as the single source of truth; provider-specific overrides documented as comments
- **`docs/CONFIGURATION.md`** — Core table updated with `LLM_TEMPERATURE` and `LLM_MAX_TOKENS`; all provider tables updated with temperature and max_tokens columns and "Keep at 0" guidance
- **`github_models_provider.py`** temperature default corrected from `0.1` to `0` (consistent with other providers)

---

## [1.1.1] - 2026-05-05

### Changed

- **`llms.txt`** aligned with the actual codebase — corrected per-agent model overrides (`INTAKE_MODEL`/`AUDITOR_MODEL`) to document that they apply across **all providers** (Bedrock, GitHub Copilot, HuggingFace, Ollama), not HuggingFace only; added missing env vars (`BEDROCK_MODEL`, `HF_TEMPERATURE`, `HF_MAX_TOKENS`, `HF_ROUTER_BASE_URL`, `OLLAMA_TIMEOUT`, `OLLAMA_THINK`); added correct GitHub Copilot default model (`claude-sonnet-4.5`) and available model list; noted `ANTHROPIC_MODEL` as a deprecated alias for `BEDROCK_MODEL`

---

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
