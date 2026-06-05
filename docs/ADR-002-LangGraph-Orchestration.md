# ADR-002 — LangGraph as Orchestration Framework

**ADAG · AI-Driven Architecture Guardrail** · April 2026 · Status: **Accepted**

|                |                                                                          |
| :------------- | :----------------------------------------------------------------------- |
| **Author**     | m3dcodie                                                                 |
| **Repo**       | [github.com/m3dcodie/arch_agent](https://github.com/m3dcodie/arch_agent) |
| **Depends on** | ADR-001 (Multi-Agent Architecture Selection)                             |

---

## Decision

**Use LangGraph 0.2 as the orchestration framework for the ADAG multi-agent pipeline.**

---

## Why LangGraph — Framework Comparison

Three frameworks were evaluated: LangGraph, CrewAI, and AutoGen. The comparison is grounded in the [DataCamp framework analysis (2025)](https://www.datacamp.com/tutorial/crewai-vs-langgraph-vs-autogen), [Lushbinary production benchmarks (2026)](https://lushbinary.com/blog/langgraph-vs-crewai-vs-autogen-ai-agent-framework-comparison/), and [OpenAgents framework comparison (2026)](https://openagents.org/blog/posts/2026-02-23-open-source-ai-agent-frameworks-compared).

| Criterion                | LangGraph ✅                                                                 | CrewAI                                       | AutoGen                                                |
| :----------------------- | :--------------------------------------------------------------------------- | :------------------------------------------- | :----------------------------------------------------- |
| **Orchestration model**  | Directed graph with typed state and conditional edges                        | Role-based crew with sequential task passing | Conversational GroupChat — LLM-driven turn order       |
| **State management**     | Typed `TypedDict` schema, persistent across every node transition            | Task outputs passed sequentially, ephemeral  | Conversation history in-memory, pruned at token limits |
| **Checkpointing**        | Built-in SQLite/Postgres — survives failures, supports time-travel debugging | None built-in                                | None built-in                                          |
| **Conditional routing**  | First-class — `_should_continue` edge functions, deterministic               | Not natively supported                       | LLM decides next turn — non-deterministic              |
| **Failure isolation**    | Error edges in graph — branch to recovery without full restart               | Task-level retry only                        | Conversational retry — can spiral                      |
| **Model agnostic**       | Yes — any LangChain-compatible provider                                      | Yes                                          | Yes                                                    |
| **Production downloads** | 34.5M/month (leading in category, 2026\)                                     | High but lower                               | Lower                                                  |
| **v1.0 GA**              | October 2025                                                                 | —                                            | —                                                      |

**Key insight from Lushbinary (2026):** _"LangGraph gives you the most control and the best production characteristics — checkpointing, streaming, deterministic execution. CrewAI gives you the fastest path to a working prototype. A widely documented pattern: teams start on CrewAI for speed, then migrate state-sensitive workflows to LangGraph when reliability requirements increase."_

ADAG is a compliance tool, not a prototype. Reliability requirements were high from day one.

---

## Why LangGraph Specifically Fits ADAG

| ADAG Requirement                                                                                       | LangGraph capability                                                                                                                                                                                                     |
| :----------------------------------------------------------------------------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Deterministic sequential pipeline** — Intake → Policy Analyst → Auditor must always execute in order | Directed acyclic graph with explicit edges. Execution order is defined in code, not by an LLM.                                                                                                                           |
| **Conditional early exit** — a failed parse or empty policy set must halt cleanly                      | `_should_continue_after_intake()` and `_should_continue_after_policy_analyst()` are native conditional edges — not workarounds.                                                                                          |
| **Per-run state isolation** — each scan must be independent; no state bleed between runs               | UUID `thread_id` per `scan()` call. Checkpointer writes to SQLite but never resumes across invocations.                                                                                                                  |
| **Typed interface contracts** — each agent must only consume what it is allowed to see                 | `AgentState` TypedDict is the schema. Fields are explicit and immutable between nodes unless a node writes them. This is structural, not enforced by prompt.                                                             |
| **Post-hoc auditability** — compliance tool must be able to explain every scan decision                | SQLite checkpoint stores full intermediate state per run. Every node transition is inspectable after the fact. Supports Gartner's per-agent observability prerequisite ([ADR-001 §6](http://./ADR-001-ADAG-Concise.md)). |
| **MCP server \+ CLI \+ Python API surface**                                                            | LangGraph `StateGraph` is transport-agnostic — the same compiled graph runs identically regardless of how it is invoked.                                                                                                 |

---

## Workflow vs. Agent Classification (Anthropic Best Practices)

Per [Anthropic's Building Effective Agents guidance](https://www.anthropic.com/research/building-effective-agents):

> **Workflows** are systems where LLMs and tools are orchestrated through predefined code paths.  
> **Agents** are systems where LLMs dynamically direct their own processes and tool usage.

**ADAG is a Workflow** — specifically a combination of Anthropic's **Prompt Chaining** and **Routing** patterns.

| Anthropic Pattern          | Present in ADAG  | Evidence                                                                                               |
| :------------------------- | :--------------- | :----------------------------------------------------------------------------------------------------- |
| **Prompt Chaining**        | ✅ Yes (primary) | Intake output feeds policy_analyst, which feeds auditor — structured state passing between fixed steps |
| **Routing**                | ✅ Yes           | `_should_continue_after_intake()`, `_should_remediate()` — Python conditional edges, not LLM decisions |
| **Parallelization**        | ❌ No            | Nodes execute sequentially; no fan-out                                                                 |
| **Orchestrator–subagents** | ❌ No            | No LLM dispatches other LLMs                                                                           |
| **Evaluator–optimizer**    | ❌ No            | No feedback loop between auditor and remediation                                                       |

Anthropics's guidance: _"Workflows offer predictability and consistency for well-defined tasks."_ Auditing IaC against a fixed policy set is a well-defined task — the steps, order, and success criteria are known upfront. Autonomous agent behaviour (LLM-directed tool selection, dynamic step ordering) would introduce non-determinism into a compliance tool where every scan result must be reproducible and auditable. See [ARCHITECTURE.md §8 Decision 6](ARCHITECTURE.md) for the full rationale.

---

## Why Not CrewAI or AutoGen

**CrewAI** — no built-in checkpointing, no deterministic conditional routing, and state is ephemeral between tasks. For a compliance audit tool where every scan decision must be traceable and reproducible, this is a structural gap, not a configuration choice.

**AutoGen** — GroupChat uses an LLM to decide which agent speaks next. This introduces non-determinism at the orchestration level: the wrong agent could activate in a failure scenario. For ADAG's sequential, strictly-ordered pipeline this is the wrong abstraction entirely.

---

## Trade-offs Accepted

- **Higher boilerplate than CrewAI** — defining `AgentState`, graph nodes, edges, and conditional functions requires more upfront code. Justified by the production reliability and debuggability it provides.
- **LangChain ecosystem dependency** — LangGraph is part of the LangChain ecosystem. Vendor dependency is real but mitigated: the `LLMFactory` abstraction in ADAG keeps LLM providers swappable.

---

## References

[LangGraph official docs](https://langchain-ai.github.io/langgraph/) · [DataCamp: CrewAI vs LangGraph vs AutoGen (2025)](https://www.datacamp.com/tutorial/crewai-vs-langgraph-vs-autogen) · [Lushbinary: Framework comparison (2026)](https://lushbinary.com/blog/langgraph-vs-crewai-vs-autogen-ai-agent-framework-comparison/) · [OpenAgents: Framework comparison (2026)](https://openagents.org/blog/posts/2026-02-23-open-source-ai-agent-frameworks-compared) · [AWS: Build multi-agent systems with LangGraph and Bedrock](https://aws.amazon.com/blogs/machine-learning/build-multi-agent-systems-with-langgraph-and-amazon-bedrock/) · [Anthropic: Building Effective Agents (2024)](https://www.anthropic.com/research/building-effective-agents)
