# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog (https://keepachangelog.com/) and this
project follows Semantic Versioning (https://semver.org/).

## [1.2.6] - 2026-06-05

### Added

- **Workflow vs. Agent classification documented** — ADAG is formally classified as a **workflow** (not an autonomous agent) per [Anthropic's Building Effective Agents best practices](https://www.anthropic.com/research/building-effective-agents); specifically implements the **Prompt Chaining** pattern with **Routing** gates; rationale and rejected alternatives documented in `docs/ARCHITECTURE.md` (Decision 6) and `docs/ADR-002-LangGraph-Orchestration.md`

### Changed

- **`docs/ARCHITECTURE.md`** — added Decision 6 explaining Anthropic's workflow vs. agent distinction, why ADAG uses a workflow, and why autonomous agent behaviour was rejected for a compliance guardrail tool
- **`docs/ADR-002-LangGraph-Orchestration.md`** — added "Workflow vs. Agent Classification" section with a pattern coverage table (Prompt Chaining ✅, Routing ✅, Parallelization ❌, Orchestrator–subagents ❌, Evaluator–optimizer ❌); added Anthropic reference
- **`docs/ADAG-v2.gif`** — updated demo GIF; `README.md` updated to reference `ADAG-v2.gif`

---

## [1.2.2] - 2026-06-02

### Added

- **Remediation Agent Designer** — a new fourth agent node (`agents/remediation.py`) that fires automatically after the Auditor when violations are found; produces one structured inline patch suggestion per violation, analogous to a GitHub Copilot inline PR suggestion: the user sees a `before` / `after` HCL diff and decides whether to apply it — nothing is written to disk automatically
- **`models/remediation.py`** — three new Pydantic models: `RemediationPatch` (violation-linked before/after code block), `RemediationReport` (structured LLM output), `RemediationStatus` (`proposed` | `skipped` | `error`)
- **`build_remediation_prompt()`** in `agents/prompts.py` — full 5-layer Prompt Contract prompt for the remediation agent; role scoped to Staff Infrastructure Engineer with write authority over HCL only; `before_block` must be verbatim from source, `after_block` is the minimal change to satisfy the violated policy
- **`REMEDIATION_MODEL` env var** — per-agent model override for the remediation role, consistent with `INTAKE_MODEL` and `AUDITOR_MODEL`; allows routing remediation to a cheaper code-gen model (e.g. `openai/gpt-4.1-mini`) while keeping the auditor on a stronger reasoning model
- **Inline diff rendering in CLI** — the `adag scan` text output now renders each patch suggestion directly under its violation as a red `- before` / green `+ after` diff block with a one-sentence explanation
- **`suggestions` field on `AuditResult`** — all output surfaces (CLI `--format json`, MCP `scan` tool, Python API) now include the `suggestions` array alongside `violations`
- **ADR-007** (`docs/ADR-007-Remediation-Agent-Design.md`) — architectural decision record covering three design options (Sequential Inline, Critic-Fixer Loop, HITL Map-Reduce) with pros/cons and rationale for selecting Option A

### Changed

- **Graph topology** (`core/graph.py`): `auditor → END` replaced by `auditor → remediation → END` (on `FAILED`); `PASSED` and `ERROR` still route directly to `END`
- **`AgentState`** (`core/state.py`): two new fields — `remediation_patches: List[RemediationPatch]` and `remediation_status: RemediationStatus`
- **`AuditResult`** (`models/violations.py`): new `suggestions: List[dict]` field; `to_json()` now serialises suggestions alongside violations
- **`ADAGRunner.scan()`** (`adag/runner.py`): passes `remediation_patches` from raw graph state to `AuditResult.suggestions`
- **CLI `_print_text()`** (`adag/cli.py`): violation output expanded with `Suggestions` count header and inline diff block per violation when a patch is available

---

## [1.2.1] - 2026-05-20

### Added

- **`benchmarks/` folder** — model evaluation results for the auditor against the built-in 7-fixture test suite; each run produces a `.json` (machine-readable) and `.md` (human-readable) report tracking Recall, Precision, F1, Accuracy, latency, and estimated cost per model; first entries cover Claude Haiku 4.5 and Gemini 2.5 Pro (both via GitHub Copilot, both scoring 100% on all metrics)
- **Benchmarks section in README** — documents the `benchmarks/` folder structure, explains each metric, and includes a summary table of results to date

### Removed

- **`FALLBACK_AUDITOR_PROMPT`** removed from `agents/prompts.py` — the hardcoded deletion-protection-only prompt was a silent degradation path: when no policies were found, audits appeared to succeed but were checked against a single hardcoded rule instead of the repository's actual policy set

### Changed

- **Auditor now errors on missing policies** (`agents/auditor.py`) — when `retrieved_policies` is empty and resources are present, the auditor returns `AuditStatus.ERROR` with a clear message instead of silently falling back to the removed hardcoded prompt; auditing without explicit policies is no longer permitted
- **Policy analyst now errors on empty disk load** (`agents/policy_analyst.py`) — in both offline mode and the RAG empty-chunks fallback path, if `load_policies_from_dir` returns zero policies the node returns `AuditStatus.ERROR` immediately rather than propagating an empty list downstream; operators get an actionable error at the source instead of a silent no-op audit

---

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

- **Prompt Contract compliance** — `build_dynamic_prompt()` in `agents/prompts.py` is now structured using the 5-layer [Prompt Contract](https://github.com/m3dcodie/prompt-contract/) architecture in cache-friendly order: `ROLE_IDENTITY` → `ROLE_AUTHORITY` → `LANGUAGE_FORMAT` → `LANGUAGE_TONE` → `SCOPE_CONTEXT` → `SCOPE_CONSTRAINTS` → `SCOPE_KNOWLEDGE` → `REASONING_STEPS` → `REASONING_REVIEW` → `OBJECTIVE_TASK` → `OBJECTIVE_ANTI_GOALS`
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
