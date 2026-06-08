# Persistence and Checkpointing in ADAG

Every scan ADAG runs is durably recorded to SQLite at each agent step. This means
any past run can be inspected, resumed after a crash, or replayed from any point
in the pipeline — without re-running the agents that already completed.

This document explains what was built, why each piece exists, and proves it works
with live test output.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Checkpointer — the Storage Backend](#2-checkpointer--the-storage-backend)
3. [thread_id — Identifying a Run](#3-thread_id--identifying-a-run)
4. [State Schema and Reducers](#4-state-schema-and-reducers)
5. [Checkpoints and the Run Timeline](#5-checkpoints-and-the-run-timeline)
6. [Cross-run Memory (Policy Knowledge Base)](#6-cross-run-memory-policy-knowledge-base)
7. [Fault Tolerance](#7-fault-tolerance)
8. [CheckpointManager — Time Travel and Replay](#8-checkpointmanager--time-travel-and-replay)
9. [Visual Debugging with LangSmith Studio](#9-visual-debugging-with-langsmith-studio)
10. [Serialization Warning](#10-serialization-warning)
11. [Live Test Output](#11-live-test-output)
12. [Implementation Map](#12-implementation-map)
13. [Further Reading](#13-further-reading)

---

## 1. Overview

ADAG's graph runs through four agents in sequence:

```
START → intake → policy_analyst → auditor → remediation → END
```

At every step boundary, the complete state of the run is saved to a SQLite
database (`./data/adag.db`). Each run is identified by a UUID called the
`thread_id`. This `thread_id` is returned on every `AuditResult` so the caller
can use it later to inspect, resume, or replay that exact run.

What this enables:

| Capability   | What you can do                                                               |
| ------------ | ----------------------------------------------------------------------------- |
| **Inspect**  | Read the saved state at any step without re-running anything                  |
| **Resume**   | Pick up a crashed run from the last successful node                           |
| **Replay**   | Re-run from a specific step (e.g. re-run the auditor with different policies) |
| **Fork**     | Inject a state patch and replay from there                                    |
| **Timeline** | Print a step-by-step execution log for any past run                           |

---

## 2. Checkpointer — the Storage Backend

ADAG uses a two-layer abstraction so the storage backend can be swapped without
touching the graph code:

```
DatabaseProvider  (abstract interface)   core/database_provider.py
      │
      └── SQLiteProvider               core/sqlite_provider.py
              │
              └── SqliteSaver          langgraph.checkpoint.sqlite
                      │
                      └── ./data/adag.db  (SQLite file on disk)
```

`DatabaseProvider` is an abstract base class registered via `DatabaseFactory`.
Swapping to Postgres or any other backend only requires registering a new provider
and setting the `DB_PROVIDER` environment variable — the graph code does not
change.

`SQLiteProvider` creates a persistent connection and hands it to `SqliteSaver`,
which handles schema creation, serialization, and transactions automatically:

```python
# core/sqlite_provider.py
def get_checkpointer(self) -> BaseCheckpointSaver:
    self._connection = sqlite3.connect(self.db_path, check_same_thread=False)
    self._checkpointer = SqliteSaver(self._connection)
    return self._checkpointer
```

The graph is compiled with the checkpointer once at startup:

```python
# core/graph.py
checkpointer = self.db_provider.get_checkpointer()
return workflow.compile(checkpointer=checkpointer)
```

From this point, every agent step is automatically written to SQLite with no
additional code required.

---

## 3. thread_id — Identifying a Run

Each `.tf` file scan gets a unique UUID that acts as the key to all its saved
checkpoints. The design rule is: **generate the UUID before the `try` block**.

This is the critical decision. If the UUID were generated inside `try`, a crash
would lose it and the operator could never find the partial checkpoints in SQLite.
By generating it first, even a crashed scan returns an `AuditResult` with a
`thread_id` pointing to whatever was saved before the failure.

```python
# adag/runner.py — the scan loop
for tf_file in tf_files:
    run_thread_id = str(uuid.uuid4())   # BEFORE try — survives exceptions
    with AuditSpan("file.scan", file=str(tf_file), thread_id=run_thread_id) as span:
        try:
            raw = graph.invoke(
                iac_code=iac_code,
                file_path=str(tf_file),
                thread_id=run_thread_id,
            )
            result = AuditResult(..., thread_id=run_thread_id)
        except Exception as e:
            result = AuditResult(
                status=AuditStatus.ERROR,
                thread_id=run_thread_id,   # still set after crash
                ...
            )
```

`graph.invoke()` accepts the `thread_id` and staples it onto the result dict so
it travels all the way back to `AuditResult.thread_id`:

```python
# core/graph.py
def invoke(self, iac_code: str, file_path: str, thread_id: Optional[str] = None, **kwargs):
    run_thread_id = thread_id or str(uuid.uuid4())
    kwargs["config"] = {"configurable": {"thread_id": run_thread_id}}
    raw = self.graph.invoke(initial_state, **kwargs)
    raw["_thread_id"] = run_thread_id
    return raw
```

`AuditResult` carries it to the caller and includes it in `to_json()`:

```python
# models/violations.py
class AuditResult(BaseModel):
    thread_id: Optional[str] = Field(
        default=None,
        description="Use with CheckpointManager for replay and resume"
    )
```

---

## 4. State Schema and Reducers

`AgentState` in `core/state.py` defines everything that gets saved at each
checkpoint. Each field is either a **plain channel** (overwrites on each write)
or a **reducer channel** (accumulates):

```python
class AgentState(TypedDict):
    messages: Annotated[list, operator.add]    # accumulates — every agent appends
    iac_code: str                               # overwrites
    file_path: str                              # overwrites
    parsed_resources: List[TerraformResource]   # overwrites
    retrieved_policies: List[Policy]            # overwrites
    resource_types: List[str]                   # overwrites
    violations: List[Violation]                 # overwrites
    status: AuditStatus                         # overwrites
    remediation_patches: List[RemediationPatch] # overwrites
    remediation_status: RemediationStatus       # overwrites
    current_node: str                           # overwrites
    error_message: str                          # overwrites
```

Only `messages` accumulates. The full message log from every agent across the
entire run is preserved in every checkpoint. All other fields hold the latest
value written by the most recent node.

---

## 5. Checkpoints and the Run Timeline

A full scan of a non-compliant Terraform file produces **6 checkpoints**:

```
step -1  empty state           START queued
step  0  after __start__       intake queued         status=pending
step  1  after intake          policy_analyst queued status=in_progress
step  2  after policy_analyst  auditor queued        status=in_progress
step  3  after auditor         remediation queued    status=failed, violations found
step  4  after remediation     next=END              status=failed, patches generated
```

If `intake` encounters an error (empty file, parse failure), the graph exits at
step 1. The per-node conditional routing means the exact checkpoint count varies
by run path (minimum 2, maximum 6).

Each saved checkpoint contains:

```
values        — full AgentState at that point in time
next          — which nodes will execute next (empty = run complete)
checkpoint_id — unique ID for this specific snapshot (used for exact replay)
created_at    — ISO 8601 timestamp
metadata      — step number, source, what the last node wrote
```

`CheckpointManager.print_history()` renders this as a readable timeline directly
in the terminal — the same information LangSmith Studio shows visually.

---

## 6. Cross-run Memory (Policy Knowledge Base)

The checkpointer saves state **within a single run** (one `thread_id`). For
knowledge that needs to be shared **across all runs**, ADAG uses a separate
mechanism: the policy knowledge base.

| Scope                       | Storage                                     | How accessed                             |
| --------------------------- | ------------------------------------------- | ---------------------------------------- |
| Within a run                | SQLite (`./data/adag.db`) via `SqliteSaver` | Automatic via checkpointer               |
| Across all runs (read-only) | Disk (`policies/`) or ChromaDB              | `policy_analyst_node` queries at runtime |

The RAG pipeline queries ChromaDB inside `policy_analyst_node` to retrieve relevant
policies for the resources being audited. This is read-only — policies are a static
corpus, not evolving memory.

**What a cross-run write store would enable** (not yet implemented):

- Tracking which policies produced false positives per team or repository
- Storing operator-approved exceptions to specific violations
- Sharing learned context between scans of related files

---

## 7. Fault Tolerance

If an agent crashes mid-run (LLM rate-limit, network failure, OOM), every
checkpoint written before the crash is already safely in SQLite. The `thread_id`
generated before the `try` block means the caller receives it even in the error
result.

The recovery flow:

```
auditor_node crashes during LLM call
    ↓
Exception propagates to runner.scan() except block
    ↓
AuditResult returned with:
    status    = ERROR
    thread_id = run_thread_id   ← generated before the crash
    ↓
Operator calls runner.resume(result.thread_id)
    ↓
CheckpointManager reads the last saved checkpoint (after policy_analyst, step 2)
    ↓
graph.invoke(None, config)   ← None = "use checkpoint state, don't start fresh"
    ↓
intake and policy_analyst do NOT re-run
auditor re-runs from the saved state
remediation runs if auditor produces violations
```

Passing `None` as the input to `graph.invoke()` is the resume pattern: it signals
that state should be loaded from the checkpointer rather than provided fresh.

---

## 8. CheckpointManager — Time Travel and Replay

All time-travel and replay logic lives in `core/checkpoint_manager.py`. This keeps
it separate from graph construction and gives operators a clean API without needing
to import graph internals.

### Instantiation

```python
from core.graph import create_graph
from core.checkpoint_manager import CheckpointManager

graph = create_graph()
cm    = CheckpointManager(graph)
```

Or use the high-level runner which wraps it:

```python
from adag.runner import ADAGRunner

runner = ADAGRunner(terraform_file="main.tf")
results = runner.scan()
tid = results[0].thread_id
```

### Read-only inspection

```python
# Full checkpoint history, newest first
history = cm.history(tid)
# Each entry: step, next, checkpoint_id, created_at, node_that_ran,
#             status, violations count, resources count

# Pretty-print the timeline to stdout
cm.print_history(tid)

# Read the final (or latest) state without re-running
state = cm.current_state(tid)
```

### Resume a crashed run

```python
# If run already complete: returns saved state instantly (no LLM calls)
# If run incomplete: re-runs remaining nodes from last checkpoint
raw = cm.resume(tid)

# High-level convenience — returns AuditResult directly
result = runner.resume(tid)
```

### Replay from a specific step

```python
# Re-run from step 1 (after intake) onward
# intake does NOT re-run; policy_analyst, auditor, remediation do
raw = cm.replay_from_step(tid, step=1)

# Replay from an exact checkpoint ID (useful when multiple checkpoints share a step)
raw = cm.replay_from_checkpoint(tid, checkpoint_id="1f162c86-602...")
```

### Inject a state patch and replay (fork)

```python
# Edit the state at a past step and re-run from there.
# The original checkpoints are not modified — a new fork is created.
raw = cm.inject_and_replay(
    tid,
    step=2,                                        # after policy_analyst
    state_patch={"retrieved_policies": [...]},     # inject corrected policies
    as_node="policy_analyst",                      # treat patch as policy_analyst output
)
# → auditor runs next with the injected policies
```

The `as_node` parameter controls which node runs after the patch. Setting it to
`"policy_analyst"` means the graph treats the patched state as policy_analyst's
output and routes to `auditor` next.

---

## 9. Visual Debugging with LangSmith Studio

LangSmith Studio is a visual graph debugger comparable to AWS Step Functions:

| AWS Step Functions           | LangSmith Studio                        |
| ---------------------------- | --------------------------------------- |
| Visual state machine diagram | Visual node graph                       |
| Execution timeline per run   | Checkpoint timeline per thread          |
| Click a state → inspect I/O  | Click a node → full `StateSnapshot`     |
| Re-run from a failed state   | Time travel: replay from any checkpoint |
| CloudWatch logs              | LangSmith traces                        |

All the SQLite checkpoints ADAG already writes are what Studio reads. To connect
locally (no cloud account needed):

```bash
pip install langgraph-cli
langgraph dev
```

This starts a local server that Studio connects to. For production, deploy to
LangSmith Cloud where Studio is a hosted IDE with one-click replay, prompt
editing, and dataset evaluation.

---

## 10. Serialization Warning

When reading checkpoints, the following warning appears:

```
Deserializing unregistered type models.violations.Severity from checkpoint.
This will be blocked in a future version. Add to allowed_msgpack_modules to silence.
```

The default serializer does not know about ADAG's custom Pydantic enums
(`Severity`, `AuditStatus`, `RemediationStatus`). It deserializes them correctly
now, but future versions may block unknown types. To silence the warning:

```python
# core/sqlite_provider.py (future improvement)
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

checkpointer = SqliteSaver(
    conn,
    serde=JsonPlusSerializer(
        allowed_msgpack_modules=[
            ("models.violations", "Severity"),
            ("models.violations", "AuditStatus"),
            ("models.remediation", "RemediationStatus"),
        ]
    )
)
```

This is a forward-compatibility fix only — current functionality is unaffected.

---

## 11. Live Test Output

The following is the actual output of `scripts/test_checkpoint_live.py` run against
the `arch_agent_ci-demo` infrastructure using the GitHub Models LLM provider
(`openai/gpt-4.1`). Run it with:

```bash
cd /home/mst/projects/arch_agent
source venv/bin/activate
set -a && source /home/mst/projects/arch_agent_ci-demo/.env && set +a
python scripts/test_checkpoint_live.py 2>/dev/null
```

```
============================================================
  Pre-flight checks
============================================================
  PASS  LLM_PROVIDER = github-models
  PASS  Fixture found: .../infrastructure/staging/database.tf

============================================================
  Test 1 — Normal scan returns thread_id
============================================================
         status     = failed
         violations = 8
         thread_id  = c2ed4a86-339a-451c-90ca-b4cbb710cfe9
  PASS  thread_id is a valid UUID and appears in to_json()

============================================================
  Test 2 — Checkpoint history timeline
============================================================
         Checkpoints saved: 6

============================================================
  Checkpoint history for thread: c2ed4a86-339a-451c-90ca-b4cbb710cfe9
============================================================
  step  -1 │ __start__       │ next=__start__      │ status=—          │ violations=0 │ 2026-06-07T23:42:48 │ ckpt=1f162ca9-71b
  step   0 │ __start__       │ next=intake          │ status=pending    │ violations=0 │ 2026-06-07T23:42:48 │ ckpt=1f162ca9-71b
  step   1 │ intake          │ next=policy_analyst  │ status=in_progress│ violations=0 │ 2026-06-07T23:42:48 │ ckpt=1f162ca9-71b
  step   2 │ policy_analyst  │ next=auditor         │ status=in_progress│ violations=0 │ 2026-06-07T23:42:48 │ ckpt=1f162ca9-71c
  step   3 │ auditor         │ next=remediation     │ status=failed     │ violations=8 │ 2026-06-07T23:42:53 │ ckpt=1f162ca9-a67
  step   4 │ remediation     │ next=END             │ status=failed     │ violations=8 │ 2026-06-07T23:43:05 │ ckpt=1f162caa-145
============================================================

  PASS  History has 6 checkpoints — timeline rendered above

============================================================
  Test 3 — Read final state from SQLite
============================================================
         State keys: ['messages', 'iac_code', 'file_path', 'parsed_resources',
                      'retrieved_policies', 'resource_types', 'violations',
                      'status', 'remediation_patches', 'remediation_status',
                      'current_node', 'error_message']
         file_path  = .../infrastructure/staging/database.tf
         status     = failed
         resources  = 2
         violations = 8
  PASS  Final state loaded from SQLite without re-running the graph

============================================================
  Test 4 — resume() on completed run (no re-run)
============================================================
  (This should return instantly — no LLM calls)
         _thread_id = c2ed4a86-339a-451c-90ca-b4cbb710cfe9
         status     = failed
  PASS  resume() returned saved state — no LLM calls made

============================================================
  Test 5 — replay_from_step() re-runs from step 1
============================================================
         Available steps: [-1, 0, 1, 2, 3, 4]
  Replaying from step 1 (intake checkpoint) — LLM calls will re-run...
         _thread_id = c2ed4a86-339a-451c-90ca-b4cbb710cfe9
         status     = failed
         violations = 8
  PASS  Replay completed — graph re-ran from intake checkpoint

============================================================
  Test 6 — Simulated crash recovery
============================================================
         status    = error
         thread_id = 8177b8f7-e041-4620-828c-c613047a4197
  PASS  thread_id preserved after crash: 8177b8f7-e041-4620-828c-c613047a4197
  PASS  Operator can now call runner.resume(thread_id) to retry the scan

============================================================
  Test 7 — Unknown thread_id handles gracefully
============================================================
  PASS  history() returns [] for unknown thread_id — no exception raised

============================================================
  Summary
============================================================
  PASS  1_scan_thread_id
  PASS  2_print_history
  PASS  3_current_state
  PASS  4_resume_complete
  PASS  5_replay_from_step
  PASS  6_crash_recovery
  PASS  7_unknown_thread

All tests passed.
```

### Reading the timeline

| Step | Node             | What happened                             | Time  |
| ---- | ---------------- | ----------------------------------------- | ----- |
| −1   | `__start__`      | Empty state, input queued                 | t=0   |
| 0    | `__start__`      | Input written, `intake` queued            | t=0   |
| 1    | `intake`         | 2 Terraform resources parsed              | t=0   |
| 2    | `policy_analyst` | Policies loaded from disk                 | t+1s  |
| 3    | `auditor`        | **8 violations found**, status → `failed` | t+5s  |
| 4    | `remediation`    | Patches generated for all 8 violations    | t+17s |

If the process crashed at step 2 (during the auditor LLM call), `resume()` would
load the step-2 checkpoint and re-run only `auditor` and `remediation`. The
`intake` and `policy_analyst` steps — which completed instantly — would not repeat.

---

## 12. Implementation Map

| Capability                       | File                               | Key symbol                                   |
| -------------------------------- | ---------------------------------- | -------------------------------------------- |
| Abstract checkpointer interface  | `core/database_provider.py`        | `DatabaseProvider`, `DatabaseFactory`        |
| SQLite checkpointer              | `core/sqlite_provider.py`          | `SQLiteProvider.get_checkpointer()`          |
| Graph compiled with checkpointer | `core/graph.py`                    | `ADAGGraph._build_graph()`                   |
| State schema (all channels)      | `core/state.py`                    | `AgentState`                                 |
| thread_id generation + wiring    | `adag/runner.py`                   | scan loop                                    |
| thread_id in invoke/stream       | `core/graph.py`                    | `ADAGGraph.invoke()`, `.stream()`            |
| thread_id on result              | `models/violations.py`             | `AuditResult.thread_id`                      |
| Read current state               | `core/checkpoint_manager.py`       | `CheckpointManager.current_state()`          |
| Read full history                | `core/checkpoint_manager.py`       | `CheckpointManager.history()`                |
| Print timeline                   | `core/checkpoint_manager.py`       | `CheckpointManager.print_history()`          |
| Resume crashed run               | `core/checkpoint_manager.py`       | `CheckpointManager.resume()`                 |
| Resume (high-level)              | `adag/runner.py`                   | `ADAGRunner.resume()`                        |
| Replay from step                 | `core/checkpoint_manager.py`       | `CheckpointManager.replay_from_step()`       |
| Replay from checkpoint ID        | `core/checkpoint_manager.py`       | `CheckpointManager.replay_from_checkpoint()` |
| Inject patch + replay            | `core/checkpoint_manager.py`       | `CheckpointManager.inject_and_replay()`      |
| Observability (separate layer)   | `core/audit_logger.py`             | `AuditSpan`, `audit_event`                   |
| Offline unit tests               | `tests/test_checkpoint_manager.py` | 19 tests, no LLM required                    |
| Live integration tests           | `scripts/test_checkpoint_live.py`  | 7 tests, real LLM                            |

---

## 13. Further Reading

- [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) — the upstream documentation this implementation is based on, covering checkpointers, threads, state snapshots, time travel, memory store, and durability modes in detail.
- [LangGraph Time Travel](https://docs.langchain.com/oss/python/langgraph/use-time-travel) — step-by-step guide to replaying and forking graph executions.
- [LangSmith Studio](https://docs.langchain.com/langsmith/studio) — the visual graph debugger referenced in section 9.
