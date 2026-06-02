# ADR-007 — Remediation Agent Designer

**ADAG · AI-Driven Architecture Guardrail** · June 2026 · Status: **Proposed**

|  |  |
| :---- | :---- |
| **Author** | m3dcodie |
| **Branch** | `feature/v2-remediation` |
| **Repo** | [github.com/m3dcodie/arch\_agent](https://github.com/m3dcodie/arch_agent) |
| **Depends on** | ADR-001 (Multi-Agent), ADR-002 (LangGraph), ADR-006 (State Management) |

---

## Context

The current ADAG pipeline terminates at the **Auditor** node. When violations are found, the `Violation` model surfaces a `remediation_hint` (a single free-text string). This is intentionally shallow — it describes *what* is wrong, not *how to fix it* in machine-applicable form.

The **Remediation Agent Designer** is the next planned node in the ADAG graph (referenced in `spec.md §2` and `ADR-001 §Roadmap`). Its purpose is:

> Given a set of policy violations and the original IaC source, produce **concrete, apply-ready code changes** that bring the infrastructure back into compliance.

This ADR evaluates three architecture options and selects one for implementation.

---

## Current State (Baseline)

```
START → [INTAKE] → [POLICY_ANALYST] → [AUDITOR] → END
                                                    ↳ violations[] + remediation_hint (string)
```

The `remediation_hint` in `Violation` is a free-text LLM suggestion embedded inside the auditor prompt. It is:
- Not structured (no line reference, no code block)
- Not validated (the hint could introduce new violations)
- Not actionable (cannot be applied via `terraform apply` or a PR patch)

---

## Decision Drivers

| Driver | Priority |
| :---- | :---- |
| **Patch correctness** — generated HCL must be syntactically valid | Critical |
| **Security isolation** — remediation agent must not re-read raw policies or live state | Critical |
| **Cost efficiency** — additional LLM calls per scan must be justified | High |
| **Auditability** — every proposed patch must be traceable to a violation ID | High |
| **Human safety gate** — production IaC must not be auto-applied without approval | High |
| **Integration simplicity** — fits the existing `AgentState` TypedDict / LangGraph graph | Medium |

---

## Option A — Sequential Inline Patch Generator

### Architecture

Add a single `remediation` node immediately after `auditor`. The node receives the full `violations[]` list and the original `iac_code` string from `AgentState`. A single structured LLM call returns a `RemediationReport` Pydantic model containing one patch per violation.

```
START → [INTAKE] → [POLICY_ANALYST] → [AUDITOR] → [REMEDIATION] → END
                                                         ↳ RemediationReport{
                                                              patches: [
                                                                { violation_id, resource_name,
                                                                  before_block, after_block,
                                                                  explanation }
                                                              ]
                                                            }
```

**New state fields:**
```python
# AgentState additions
remediation_patches: List[RemediationPatch]   # structured per-violation patches
remediation_status: RemediationStatus          # PROPOSED | SKIPPED | ERROR
```

**New models:**
```python
class RemediationPatch(BaseModel):
    violation_id: str           # links back to Violation.id (e.g. "VA3F2B-001")
    resource_type: str
    resource_name: str
    before_block: str           # original HCL snippet
    after_block: str            # corrected HCL snippet
    explanation: str            # human-readable rationale
    line_number: Optional[int]

class RemediationReport(BaseModel):
    patches: List[RemediationPatch]
```

**Prompt design (Prompt Contract layers):**
- **Role:** Staff Infrastructure Engineer with write authority over HCL
- **Policies:** violations[] injected as structured JSON (not raw policy text)
- **Scope:** original `iac_code` + violations only — no access to retrieved policies or live AWS state
- **Objective:** produce one `after_block` per violation that satisfies the `remediation_hint` from the Auditor

**Graph change (minimal):**
```python
workflow.add_node("remediation", remediation_node)
workflow.add_conditional_edges(
    "auditor",
    _should_remediate,            # only if status == FAILED
    {"remediation": "remediation", "end": END},
)
workflow.add_edge("remediation", END)
```

### Pros

| Strength | Detail |
| :---- | :---- |
| **Lowest integration cost** | One new node, one new model, ~50 lines in `graph.py`. Fits the existing sequential DAG without graph restructuring. |
| **Single LLM call** | All violations remediated in one prompt. Cost overhead: ~1 call per scan, same order as current auditor call. |
| **Consistent state contract** | `AgentState` grows by two fields. No new graph topology concepts for contributors to learn. |
| **Fastest path to value** | Reviewable patches available within the same scan invocation. No external services or HITL infrastructure required. |
| **Traceable by violation ID** | `RemediationPatch.violation_id` creates a 1:1 audit trail to `Violation.id`. |

### Cons

| Weakness | Detail |
| :---- | :---- |
| **No patch validation** | The LLM-generated `after_block` is never re-audited. A malformed patch could introduce a new violation or break HCL syntax. Risk: medium at low violation counts; grows at 10+ violations. |
| **Context window pressure at scale** | A scan with 20+ violations across a 500-line `.tf` file may exceed the model's effective context window. Patch quality degrades in mid-context positions ([Stanford CRFM 2023](https://arxiv.org/abs/2307.03172)). |
| **All-or-nothing output** | If the model fails to generate one patch, the entire `RemediationReport` may be incomplete. No partial success path. |
| **No human review gate** | Patches are proposed and stored but there is no built-in approval workflow before they can be applied. Requires downstream tooling (e.g., PR bot) to enforce the safety gate. |

---

## Option B — Critic-Fixer Loop (Self-Healing Agentic Cycle)

### Architecture

Introduce a **generate → validate → refine** cycle within a LangGraph subgraph. The `remediation` node generates patches. A lightweight `patch_validator` node re-runs the HCL parser (`hcl_parser.py`) and a subset of policy checks against the patched code. If violations remain or HCL is invalid, control returns to `remediation` with a `critique` message appended to state. The loop exits when all patches are clean or a maximum retry count is reached.

```
                         ┌──────────────────────┐
                         ▼                      │  (violations remain or HCL invalid)
[AUDITOR] → [REMEDIATION] → [PATCH_VALIDATOR] ──┘
                                   │
                                   │  (all patches valid OR max_retries exceeded)
                                   ▼
                                  END
```

**New state fields:**
```python
remediation_patches: List[RemediationPatch]
remediation_status: RemediationStatus
patch_critique: Optional[str]        # validator feedback injected into retry prompt
patch_iteration: int                 # guards against infinite cycles (max: 3)
```

**Validation logic (no LLM):**
```
patch_validator_node:
  1. Reconstruct patched .tf by substituting after_blocks into original iac_code
  2. Run hcl_parser.parse() on the result — catches syntax breaks (no LLM)
  3. Re-run auditor_node() in stateless mode against patched resources — catches new violations (1 LLM call)
  4. If clean → END; else → append critique to state → back to remediation
```

**Graph change:**
```python
workflow.add_node("remediation", remediation_node)
workflow.add_node("patch_validator", patch_validator_node)

workflow.add_conditional_edges("auditor",   _should_remediate, {"remediation": "remediation", "end": END})
workflow.add_edge("remediation", "patch_validator")
workflow.add_conditional_edges(
    "patch_validator",
    _should_retry_remediation,          # checks patch_iteration < MAX_RETRIES
    {"remediation": "remediation", "end": END},
)
```

### Pros

| Strength | Detail |
| :---- | :---- |
| **Self-correcting patches** | Validated patches are re-audited before leaving the graph. Significantly reduces the risk of a "fix" introducing new violations or broken HCL. |
| **Deterministic syntax check** | The HCL parser is deterministic (no LLM). Syntax errors are caught without extra model calls. |
| **Structured critique feedback** | The validator writes a `patch_critique` field that the remediation prompt can read on retry — grounding the correction in specific, structured failure reasons rather than generic re-prompting. |
| **Cycle bound** | `patch_iteration` cap (e.g., 3) prevents runaway loops. A hard exit with `RemediationStatus.DEGRADED` surfaces the best available patches even on timeout. |

### Cons

| Weakness | Detail |
| :---- | :---- |
| **Highest LLM cost** | Each retry cycle adds 1–2 LLM calls (remediation re-generation + re-audit). Worst case: 3 retries × 2 calls = 6 additional calls per scan. |
| **Graph complexity spike** | Introduces a cycle into the currently DAG-only graph. New contributors must understand LangGraph conditional back-edges. Risk of mis-configured `_should_retry` logic causing infinite loops in edge cases. |
| **Patch substitution brittleness** | Step 1 of validation (text substitution of `after_block` into original code) is fragile for multi-line blocks, `for_each` constructs, or resources with inline comments. Needs a robust HCL diffing library, not naive string replace. |
| **Increased latency** | Even on first-pass success, the validation node adds one deterministic parse + one stateless auditor call to the critical path. |

---

## Option C — Per-Violation Atomic Patches with Human-in-the-Loop Gate

### Architecture

Treat each violation as an independent remediation unit. A LangGraph map-reduce pattern spawns one structured LLM call per violation, then merges the results. A mandatory **HITL interrupt** (LangGraph `interrupt()`) pauses the graph and exposes the proposed patches to a human reviewer via the MCP server or CLI before allowing the graph to proceed.

```
[AUDITOR]
    │
    ▼
[REMEDIATION_DISPATCHER]   ← fan-out: one sub-call per Violation
    │   │   │
    ▼   ▼   ▼
  [P1] [P2] [P3]  ← per-violation patch generators (parallel LLM calls)
    │   │   │
    └───┴───┘
        │
        ▼
[PATCH_MERGER]             ← collects List[RemediationPatch], deduplicates
        │
        ▼
[HITL_REVIEW] ⏸            ← LangGraph interrupt() — waits for human approval
        │
   approved?
    ├── YES → [PATCH_APPLIER] → END  (writes corrected .tf to disk / PR)
    └── NO  → END  (patches discarded, original file unchanged)
```

**New state fields:**
```python
remediation_patches: List[RemediationPatch]
remediation_status: RemediationStatus
hitl_decision: Optional[Literal["approved", "rejected", "partial"]]
hitl_approved_ids: List[str]        # subset of violation_ids approved by reviewer
```

**HITL surface (MCP extension):**
```
Tool: propose_patches()     → returns RemediationReport to reviewer
Tool: approve_patches(ids)  → resumes graph with approved subset
Tool: reject_patches()      → terminates graph cleanly
```

### Pros

| Strength | Detail |
| :---- | :---- |
| **Production-safe by design** | The graph cannot apply any patch without explicit human approval. Satisfies compliance requirements for regulated environments (SOC 2, FedRAMP). |
| **Fine-grained control** | Reviewer can approve a subset of patches (`hitl_approved_ids`). A HIGH-severity fix can be approved while a LOW-severity cosmetic change is deferred. |
| **Atomic, independently reviewable patches** | Each `RemediationPatch` maps 1:1 to a single `Violation`. The reviewer sees exactly what changes and why, with no cross-contamination between fixes. |
| **Parallelism** | Per-violation LLM calls can run in parallel (LangGraph `Send` API), reducing wall-clock latency despite the higher call count. |
| **Natural PR integration** | The `PATCH_APPLIER` node has a clean, well-scoped job: write diffs, open PR. No ambiguity about what constitutes an "applied" patch. |

### Cons

| Weakness | Detail |
| :---- | :---- |
| **Highest implementation cost** | Requires: HITL interrupt infrastructure, MCP tool extensions (`approve_patches`), a patch applier that writes to disk/GitHub, and map-reduce graph topology. Estimated 3–5× the code of Option A. |
| **Blocks on human response** | The graph pauses indefinitely at the HITL gate. Requires a persistent checkpointer (PostgreSQL, not SQLite) for production durability during the wait. |
| **LLM call count scales with violations** | 10 violations = 10 LLM calls for patch generation. Cost grows linearly with violation count. Partially offset by parallelism. |
| **Merge complexity** | Multiple atomic patches targeting the same resource block can conflict. The `PATCH_MERGER` node must detect and resolve overlapping `after_block` regions — a non-trivial HCL-aware diffing problem. |
| **Overkill for CI/CD pipeline** | The HITL gate breaks the synchronous, automated nature of CI checks. Best suited for pre-production review workflows, not commit-triggered scans. |

---

## Comparison Matrix

| Criterion | Option A — Sequential | Option B — Critic-Fixer | Option C — HITL + Map-Reduce |
| :---- | :----: | :----: | :----: |
| **LLM calls (typical)** | +1 | +2 to +6 | +N (one per violation) |
| **Patch correctness** | Low–Medium | High | Medium (no re-audit) |
| **Human safety gate** | ❌ | ❌ | ✅ |
| **Integration effort** | Low | Medium | High |
| **Graph complexity** | Low | Medium (cycle) | High (map-reduce + HITL) |
| **Context window risk** | Medium | Medium | Low (atomic) |
| **Production durability** | SQLite | SQLite | PostgreSQL required |
| **CI/CD compatible** | ✅ | ✅ | ❌ (blocks) |
| **Regulatory readiness** | ❌ | Partial | ✅ |

---

## Decision

**Phase 1 (this branch): Implement Option A — Sequential Inline Patch Generator.**

**Phase 2 (future ADR): Layer in Option C's HITL gate as an opt-in mode.**

### Rationale

Option A is the right first step because:

1. **The existing baseline is zero.** The `remediation_hint` string is not actionable. Any structured patch — even unvalidated — is a material improvement for the 80% of users running ADAG in CI/CD pipelines where automated patching is already gated by PR review.

2. **Option A is the foundation, not the ceiling.** The `RemediationPatch` model and `remediation_node` introduced here are reused in Options B and C. Building Option A first avoids a big-bang implementation and allows the patch schema to be validated in production before adding validation loops or HITL infrastructure.

3. **Option B's value is conditional.** The self-healing loop only pays off when the LLM frequently produces incorrect patches. Empirical data from Option A runs will determine whether retry rates justify Option B's complexity and cost.

4. **Option C requires infrastructure that does not yet exist.** A PostgreSQL-backed persistent checkpointer and MCP `approve_patches` tool are prerequisite infrastructure items that warrant their own ADR. They should not block remediation shipping.

### Rejection of Option B (now)
The cycle complexity and 2–6× LLM cost are not justified without evidence that Option A patch quality is insufficient. Defer.

### Rejection of Option C (now)
HITL interrupts require a persistent checkpointer and MCP tooling extensions that do not exist yet. The synchronous CI/CD use case (the primary ADAG user) is incompatible with a blocking human gate. Defer to a dedicated "Compliance Review Mode" ADR.

---

## Implementation Plan (Option A)

### 1. New Models (`models/remediation.py`)
```python
class RemediationStatus(str, Enum):
    PROPOSED = "PROPOSED"
    SKIPPED = "SKIPPED"    # no violations — nothing to remediate
    ERROR = "ERROR"

class RemediationPatch(BaseModel):
    violation_id: str
    resource_type: str
    resource_name: str
    before_block: str
    after_block: str
    explanation: str
    line_number: Optional[int] = None

class RemediationReport(BaseModel):
    patches: List[RemediationPatch]
    status: RemediationStatus
```

### 2. New Agent (`agents/remediation.py`)
```python
def remediation_node(state: AgentState, llm: BaseChatModel) -> Dict[str, Any]:
    violations = state.get("violations", [])
    iac_code   = state.get("iac_code", "")
    # Single structured LLM call → RemediationReport
    # Prompt: Role(infra engineer) + violations JSON + original HCL → after_blocks
```

### 3. State Extension (`core/state.py`)
```python
remediation_patches: List[RemediationPatch]
remediation_status: RemediationStatus
```

### 4. Graph Extension (`core/graph.py`)
```python
REMEDIATION_MODEL env var  →  self.remediation_llm
workflow.add_node("remediation", ...)
workflow.add_conditional_edges("auditor", _should_remediate, {...})
workflow.add_edge("remediation", END)
```

### 5. New Prompt (`agents/prompts.py` — `build_remediation_prompt`)
```
Role    → Staff Infrastructure Engineer
Language → Output ONLY valid JSON. One patch object per violation.
Scope   → iac_code + violations[] only. No access to policy docs.
Reasoning → For each violation, identify the minimal change to after_block.
Objective → RemediationReport JSON schema.
```

### 6. CLI / MCP output
The `RemediationReport` is returned alongside `violations[]` in all output surfaces (CLI table, MCP `scan` tool, SQLite audit log).

---

## Security Considerations

| Risk | Mitigation |
| :---- | :---- |
| **Patch injection** — a crafted `.tf` file tricks the remediation LLM into generating malicious HCL | Remediation node operates on `violations[]` (structured, validated by the Auditor Pydantic model), not raw LLM text. The `iac_code` is the original input — already processed by the deterministic HCL parser in intake. |
| **Scope creep** — remediation LLM modifies resources not referenced in `violations[]` | `RemediationPatch.violation_id` is required. Output schema enforced by `invoke_structured`. Any patch without a matching `violation_id` is dropped by the merger. |
| **Auto-apply without review** | Option A produces patches as data in state. No file write occurs. Application requires explicit downstream action (e.g., CI job reading `remediation_patches` from the MCP output). |

---

## Key References

- [LangGraph Human-in-the-Loop](https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/)
- [LangGraph Map-Reduce (Send API)](https://langchain-ai.github.io/langgraph/how-tos/map-reduce/)
- [Stanford CRFM — Lost in the Middle](https://arxiv.org/abs/2307.03172)
- [ADAG spec.md §2 — The Remediation Designer node](../spec.md)
- [ADR-001 — Multi-Agent Architecture](ADR-001-ADAG-Architecture-Decision.md)
- [ADR-006 — State Management](ADR-006-State-Management.md)
