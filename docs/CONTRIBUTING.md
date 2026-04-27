# Contributing

Thank you for contributing to ADAG. This guide covers the repository structure, the main extension points (new LLM providers, new agents, new policies), and the test workflow.

---

## Table of Contents

1. [Repository Structure](#1-repository-structure)
2. [Development Setup](#2-development-setup)
3. [Running Tests](#3-running-tests)
4. [Adding a New LLM Provider](#4-adding-a-new-llm-provider)
5. [Adding a New Agent Node](#5-adding-a-new-agent-node)
6. [Adding a New Built-in Policy](#6-adding-a-new-built-in-policy)
7. [Adding Support for a New Terraform Resource Type](#7-adding-support-for-a-new-terraform-resource-type)
8. [Code Style](#8-code-style)
9. [Integration Tests (Mode 3 RAG)](#9-integration-tests-mode-3-rag)
10. [Submitting a Pull Request](#10-submitting-a-pull-request)

---

## 1. Repository Structure

```
arch_agent/
├── adag/                      ← Python package root
│   ├── __init__.py            ← exports ADAGRunner
│   ├── runner.py              ← ADAGRunner class (public API)
│   ├── cli.py                 ← click CLI (adag scan)
│   └── mcp_server.py          ← FastMCP server (5 tools)
│
├── agents/                    ← LangGraph agent nodes
│   ├── intake.py              ← deterministic HCL parser
│   ├── policy_analyst.py      ← policy retrieval (RAG or disk)
│   └── auditor.py             ← LLM compliance checker
│
├── core/                      ← Infrastructure / framework code
│   ├── graph.py               ← LangGraph StateGraph definition
│   ├── state.py               ← AgentState TypedDict
│   ├── llm_provider.py        ← LLMProvider ABC + LLMFactory
│   ├── bedrock_provider.py    ← AWS Bedrock implementation
│   ├── github_copilot_provider.py
│   ├── huggingface_provider.py
│   ├── ollama_provider.py
│   ├── database_provider.py   ← DatabaseProvider ABC + DatabaseFactory
│   ├── sqlite_provider.py     ← SQLite checkpointer
│   ├── policy_loader.py       ← offline .md policy loader
│   ├── rag_provider.py        ← stub (RAG REST client placeholder)
│   └── chroma_provider.py     ← stub (local ChromaDB placeholder)
│
├── models/                    ← Pydantic data models
│   ├── policy.py              ← Policy model
│   └── violations.py          ← Violation, TerraformResource, AuditResult
│
├── policies/                  ← Built-in policy Markdown files (10 files)
│
├── scripts/
│   └── index_policies.py      ← RAG indexing script
│
├── tests/
│   ├── test_adag.py           ← unit tests (agents, models, providers)
│   ├── test_mcp_server.py     ← MCP tool tests
│   ├── test_rag.py            ← integration tests (requires live services)
│   └── fixtures/
│       ├── bad_terraform.tf   ← non-compliant fixture
│       └── good_terraform.tf  ← compliant fixture
│
├── docs/                      ← All documentation
├── pyproject.toml             ← package config and entry points
├── requirements.txt           ← pinned dependencies
└── pytest.ini                 ← test configuration
```

---

## 2. Development Setup

```bash
# Clone the repo
git clone https://github.com/your-org/arch_agent.git
cd arch_agent

# Create virtualenv
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Copy env template
cp docs/CONFIGURATION.md /dev/null   # template is in CONFIGURATION.md §3
# Or manually create .env — see docs/CONFIGURATION.md
```

---

## 3. Running Tests

```bash
# Run all unit tests
pytest

# Run with coverage report
pytest --cov=adag --cov=agents --cov=core --cov=models --cov-report=term-missing

# Run a specific test file
pytest tests/test_adag.py

# Run a specific test
pytest tests/test_adag.py::TestIntakeAgent::test_parse_resources

# Run MCP server tests only
pytest tests/test_mcp_server.py -v
```

### Test configuration

`pytest.ini` sets:

- `testpaths = tests`
- `asyncio_mode = auto` (for async test support)

### What the tests cover

| Test File            | What it tests                                      | LLM calls?            |
| -------------------- | -------------------------------------------------- | --------------------- |
| `test_adag.py`       | Models, providers, intake agent, auditor agent     | No (mocked)           |
| `test_mcp_server.py` | All 5 MCP tools, error handling                    | No (graph patched)    |
| `test_rag.py`        | Full RAG pipeline (ingest → chunk → embed → query) | No (integration only) |

**All unit tests run without LLM credentials.** LLM calls are mocked using `unittest.mock.patch`. You can run `pytest tests/test_adag.py tests/test_mcp_server.py` with no provider configured.

---

## 4. Adding a New LLM Provider

ADAG uses a Factory + Registry pattern. Adding a provider requires three steps.

### Step 1: Create the provider file

Create `core/my_provider.py`:

```python
from langchain_core.language_models import BaseChatModel
from core.llm_provider import LLMProvider, LLMFactory


class MyProvider(LLMProvider):
    """
    LLM provider for My Service.

    Required env vars:
      MY_SERVICE_API_KEY — API key for My Service
      MY_SERVICE_MODEL   — default model name
    """

    def __init__(self):
        import os
        self.api_key = os.environ.get("MY_SERVICE_API_KEY")
        self.model_name = os.environ.get("MY_SERVICE_MODEL", "default-model-v1")

        if not self.api_key:
            raise ValueError("MY_SERVICE_API_KEY environment variable is required.")

        # Validate connectivity at startup
        self._validate()

    def _validate(self):
        # Optional: ping the service to verify credentials
        pass

    def get_model(self, role: str = "default") -> BaseChatModel:
        from langchain_openai import ChatOpenAI  # or whichever LangChain integration

        model_name = {
            "auditor": os.environ.get("AUDITOR_MODEL", self.model_name),
            "intake": os.environ.get("INTAKE_MODEL", self.model_name),
        }.get(role, self.model_name)

        return ChatOpenAI(
            api_key=self.api_key,
            model=model_name,
            base_url="https://api.myservice.com/v1",
        )


# Self-register at import time
LLMFactory.register_provider("my-service", MyProvider)
```

### Step 2: Register the import in the factory

Open `core/llm_provider.py` and add your provider to the import-time registration block:

```python
def _load_providers():
    """Import all provider modules to trigger self-registration."""
    from core import bedrock_provider          # noqa
    from core import github_copilot_provider   # noqa
    from core import huggingface_provider      # noqa
    from core import ollama_provider           # noqa
    from core import my_provider               # noqa  ← add this line
```

### Step 3: Add to documentation and tests

- Add to the provider table in [docs/CONFIGURATION.md](CONFIGURATION.md)
- Add a test in `tests/test_adag.py` under `TestProviders`
- Add env var documentation

### Step 4: Verify

```bash
LLM_PROVIDER=my-service MY_SERVICE_API_KEY=xxx adag scan tests/fixtures/bad_terraform.tf
```

---

## 5. Adding a New Agent Node

Agents are functions that accept and return `AgentState`. Adding a new agent node requires touching three files.

### Step 1: Create the agent

Create `agents/my_agent.py`:

```python
from langchain_core.language_models import BaseChatModel
from core.state import AgentState


class MyAgent:
    def __init__(self, llm: BaseChatModel):
        self.llm = llm

    def run(self, state: AgentState) -> AgentState:
        """
        Do something with the state and return an updated state.
        """
        # Read from state
        resources = state.get("parsed_resources", [])

        # Do work (LLM call, I/O, computation, etc.)
        result = self._process(resources)

        # Write back to state — only update the keys you own
        return {
            **state,
            "my_agent_output": result,
            "current_node": "my_agent",
        }

    def _process(self, resources):
        # Implementation here
        pass
```

### Step 2: Add the output field to AgentState

Open `core/state.py` and add your field to the `AgentState` TypedDict:

```python
class AgentState(TypedDict):
    # ... existing fields ...
    my_agent_output: List[str]   # ← add your field
```

### Step 3: Wire into the graph

Open `core/graph.py` and add the node and edges:

```python
from agents.my_agent import MyAgent

class ADAGGraph:
    def _build_graph(self):
        my_agent = MyAgent(llm=self.llm)

        graph = StateGraph(AgentState)
        graph.add_node("intake", self.intake_agent.run)
        graph.add_node("policy_analyst", self.policy_analyst_agent.run)
        graph.add_node("my_agent", my_agent.run)         # ← add node
        graph.add_node("auditor", self.auditor_agent.run)

        graph.set_entry_point("intake")
        graph.add_conditional_edges("intake", self._should_continue_after_intake)
        graph.add_edge("policy_analyst", "my_agent")     # ← wire edge
        graph.add_edge("my_agent", "auditor")            # ← wire edge
        graph.add_edge("auditor", END)

        return graph.compile(checkpointer=self.checkpointer)
```

### Write tests

Add tests for your agent in `tests/test_adag.py` following the pattern in `TestIntakeAgent` and `TestAuditorAgent`. Mock LLM calls with `unittest.mock.patch`.

---

## 6. Adding a New Built-in Policy

See [docs/POLICIES.md](POLICIES.md) for the full workflow including the policy template, severity guidelines, and a worked example.

**Quick summary:**

1. Create `policies/my_policy.md` using the policy Markdown template.
2. Test with `adag scan /tmp/test.tf`.
3. If adding a new resource type, also update the intake agent's `AUDITABLE_RESOURCE_TYPES` set.
4. If using Mode 3, re-run `python scripts/index_policies.py`.

---

## 7. Adding Support for a New Terraform Resource Type

The intake agent only extracts resource types listed in `AUDITABLE_RESOURCE_TYPES`. To add a new type:

Open `agents/intake.py` and add to the set:

```python
AUDITABLE_RESOURCE_TYPES = {
    "aws_db_instance",
    "aws_rds_cluster",
    "aws_rds_cluster_instance",
    "aws_kms_key",
    "aws_s3_bucket",
    "aws_s3_bucket_public_access_block",
    "aws_s3_bucket_server_side_encryption_configuration",
    "provider",
    "aws_vpc",          # ← new
    "aws_flow_log",     # ← new
}
```

No other code changes are needed. The regex parser extracts all attributes from any resource block — it just needs to know which types to keep.

**Write a test** that verifies the new type is extracted correctly. Add a small HCL fixture and assert the expected resource appears in `parsed_resources`.

---

## 8. Code Style

- **Python version:** 3.10+ syntax is fine. Use `match` statements, `X | Y` union types where appropriate.
- **Formatting:** `black` with default settings. Run `black .` before committing.
- **Type hints:** Required for all new public functions and class methods. Use `from __future__ import annotations` for forward references.
- **Imports:** Standard library → third-party → local. No circular imports.
- **Error handling:** Use `AuditStatus.ERROR` + `error_message` in state for recoverable errors. Raise exceptions only for programming errors (bad arguments, missing required env vars at startup).
- **No print statements in library code.** Use `logging.getLogger(__name__)` instead. The CLI layer handles user-facing output.
- **No hardcoded credentials or file paths.** All configuration via environment variables.

---

## 9. Integration Tests (Mode 3 RAG)

`tests/test_rag.py` contains integration tests that require all five RAG microservices to be running. These tests are excluded from the default `pytest` run.

### Running RAG integration tests

```bash
# Start the RAG services first (see docs/RAG_PIPELINE.md)

# Then run RAG tests
pytest tests/test_rag.py -v

# Or run all tests including integration
pytest --run-integration
```

### What the RAG tests cover

1. Ingestion service reachability
2. Chunk, embed, add_vectors pipeline
3. Context augmentation query
4. End-to-end: policy document → index → query → retrieve correct policy

---

## 10. Submitting a Pull Request

1. Fork the repository and create a feature branch: `git checkout -b feature/my-feature`
2. Make your changes.
3. Run `pytest` and verify all tests pass.
4. Run `black .` to format code.
5. Update relevant documentation in `docs/`.
6. Submit a pull request with:
   - A clear description of what changed and why
   - Reference to any related issue
   - Evidence of testing (test output, or description of manual test)

### What makes a good PR

- **One logical change per PR.** Split unrelated changes into separate PRs.
- **Tests included.** New functionality without tests will not be merged.
- **Docs updated.** If you add an env var, update `docs/CONFIGURATION.md`. If you add a tool, update `docs/MCP.md`.
- **No breaking changes without discussion.** If your change breaks existing behavior, open an issue first.
