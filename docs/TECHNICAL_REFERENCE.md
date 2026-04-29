# Technical Reference

Complete API and data model reference for ADAG. This is the authoritative reference for programmatic use, tool integration, and extending the system.

---

## Table of Contents

1. [ADAGRunner — Public API](#1-adagrunner--public-api)
2. [AuditResult](#2-auditresult)
3. [Violation](#3-violation)
4. [TerraformResource](#4-terraformresource)
5. [Policy](#5-policy)
6. [AgentState](#6-agentstate)
7. [AuditStatus](#7-auditstatus)
8. [ViolationList](#8-violationlist)
9. [LLMFactory](#9-llmfactory)
10. [DatabaseFactory](#10-databasefactory)
11. [SARIF Output Schema](#11-sarif-output-schema)

---

## 1. ADAGRunner — Public API

`ADAGRunner` is the single entry point for programmatic use. Import it from the top-level package.

```python
from adag import ADAGRunner
```

### Constructor

```python
ADAGRunner(
    llm_provider: str = None,       # Provider key: "bedrock" | "github-copilot" | "huggingface" | "ollama"
                                    # Falls back to LLM_PROVIDER env var, then "bedrock"
    policies_dir: str = None,       # Path to policies directory. Falls back to built-in policies/
)
```

The graph is **not initialized at construction time**. Provider validation (credential checks, connectivity) happens on the first call to `scan()`.

### `scan()`

```python
def scan(file_path: str) -> AuditResult
```

Run a compliance scan on a single Terraform file.

**Parameters:**

- `file_path` — Absolute or relative path to a `.tf` file.

**Returns:** `AuditResult`

**Raises:** Does not raise. On error, returns an `AuditResult` with `status=AuditStatus.ERROR` and `violations=[]`.

**Example:**

```python
from adag import ADAGRunner

runner = ADAGRunner(llm_provider="github-copilot")
result = runner.scan("./infra/database.tf")

if result.has_violations:
    for v in result.violations:
        print(f"[{v.severity}] {v.resource_name}: {v.description}")
    exit(1)
```

### Thread Safety

`ADAGRunner` is **not thread-safe**. Each thread or process should instantiate its own `ADAGRunner`. The underlying LangGraph graph is stateful and shares the SQLite checkpointer.

---

## 2. AuditResult

Returned by `ADAGRunner.scan()`. Contains the complete result of a single file scan.

```python
class AuditResult:
    status: AuditStatus
    file_path: str
    total_resources: int
    violations: List[Violation]
    summary: str
```

### Properties

```python
@property
def has_violations(self) -> bool:
    """True if any violations were found (status == FAILED)."""

@property
def high_severity_count(self) -> int:
    """Number of HIGH severity violations."""

@property
def medium_severity_count(self) -> int:
    """Number of MEDIUM severity violations."""

@property
def low_severity_count(self) -> int:
    """Number of LOW severity violations."""
```

### Methods

```python
def to_json(self) -> dict:
    """
    Return a JSON-serializable dict representation.
    Suitable for json.dumps() or API responses.
    """

def to_sarif(self) -> dict:
    """
    Return a SARIF 2.1.0 compliant dict for this file's results.
    Use _merge_sarif() in cli.py to merge multiple files into one SARIF document.
    """
```

### `to_json()` shape

```json
{
  "status": "FAILED",
  "file_path": "infra/main.tf",
  "total_resources": 3,
  "violations": [...],
  "summary": "2 violations found: 1 HIGH, 1 MEDIUM, 0 LOW"
}
```

---

## 3. Violation

A single policy violation found by the auditor.

```python
class Violation(BaseModel):
    id: str                          # e.g. "V-001" — unique within a scan result
    resource_type: str               # e.g. "aws_db_instance"
    resource_name: str               # e.g. "main" (the Terraform resource label)
    severity: Severity               # HIGH | MEDIUM | LOW | INFO
    policy_ref: str                  # Policy ID that was violated, e.g. "delete_protection"
    description: str                 # Human-readable explanation of the violation
    line_number: Optional[int]       # Line number in source .tf file (if available)
    remediation_hint: Optional[str]  # Specific fix instruction
```

### `Severity` enum

```python
class Severity(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"
```

### JSON representation

```json
{
  "id": "V-001",
  "resource_type": "aws_db_instance",
  "resource_name": "main",
  "severity": "HIGH",
  "policy_ref": "delete_protection",
  "description": "Database instance 'main' does not have deletion protection enabled.",
  "line_number": 3,
  "remediation_hint": "Add 'deletion_protection = true' to the aws_db_instance resource block."
}
```

---

## 4. TerraformResource

Represents a parsed Terraform resource block. Produced by the Intake agent.

```python
class TerraformResource(BaseModel):
    resource_type: str       # e.g. "aws_db_instance"
    resource_name: str       # e.g. "main" (the label in the HCL block)
    attributes: dict         # flat key-value pairs extracted from the HCL block
    line_number: Optional[int]  # line number of the resource { declaration
```

### `attributes` structure

The `attributes` dict contains all parsed `key = value` pairs from the HCL block as Python primitives:

```python
{
    "identifier": "prod-rds-main",
    "instance_class": "db.t3.medium",
    "deletion_protection": False,   # boolean
    "backup_retention_period": 7,   # integer
    "storage_encrypted": True,
    "tags": {}                      # nested blocks are partially supported
}
```

**Important limitations:**

- Terraform variable references (`var.name`) are preserved as strings — they are not resolved.
- `for_each` and `count` meta-arguments produce a single resource entry per block; dynamic expansion is not supported.
- Nested blocks (e.g., `lifecycle {}`) are extracted as empty dicts — their contents are not recursively parsed.

---

## 5. Policy

Represents a single compliance policy, either loaded from disk or retrieved from the RAG pipeline.

```python
class Policy(BaseModel):
    id: str                        # e.g. "delete_protection"
    title: str                     # e.g. "Deletion Protection Required"
    severity: str                  # "HIGH" | "MEDIUM" | "LOW"
    description: str               # Brief description
    scope: List[str]               # Applicable resource types
    requirements: str              # Full policy text (verbatim from Markdown)
    examples_compliant: str        # Compliant HCL examples
    examples_non_compliant: str    # Non-compliant HCL examples
    remediation: str               # Fix instructions
    file_path: Optional[str]       # Source .md file path (offline mode)
    chunk_id: Optional[str]        # ChromaDB chunk ID (RAG mode)
    distance: Optional[float]      # Semantic distance from query (RAG mode; lower = more relevant)
```

### Disk-loaded vs RAG-loaded policies

| Field          | Disk mode                  | RAG mode                  |
| -------------- | -------------------------- | ------------------------- |
| `id`           | Parsed from `## Policy ID` | From chunk metadata       |
| `title`        | Parsed from `# Title`      | From chunk metadata       |
| `severity`     | Parsed from `## Severity`  | From chunk metadata       |
| `requirements` | Full `.md` file content    | Chunk content             |
| `chunk_id`     | None                       | ChromaDB chunk ID         |
| `distance`     | None                       | Cosine distance (0.0–1.0) |

---

## 6. AgentState

The shared state TypedDict passed through all LangGraph nodes. Every agent reads from and writes to this object.

```python
from typing import Annotated, List
import operator

class AgentState(TypedDict):
    # Immutable inputs (set by caller, never modified by agents)
    iac_code: str                              # Raw Terraform file content
    file_path: str                             # Source file path

    # Append-only log (use Annotated[list, operator.add] for LangGraph fan-out safety)
    messages: Annotated[list, operator.add]

    # Set by intake node
    parsed_resources: List[TerraformResource]

    # Set by policy_analyst node
    retrieved_policies: List[Policy]
    resource_types: List[str]

    # Set by auditor node
    violations: List[Violation]
    status: AuditStatus

    # Debugging
    current_node: str
    error_message: str                         # Populated only when status == ERROR
```

### Initializing state

`ADAGRunner.scan()` creates the initial state:

```python
initial_state = AgentState(
    messages=[],
    iac_code=file_content,
    file_path=file_path,
    parsed_resources=[],
    retrieved_policies=[],
    resource_types=[],
    violations=[],
    status=AuditStatus.PENDING,
    current_node="",
    error_message="",
)
```

---

## 7. AuditStatus

```python
class AuditStatus(str, Enum):
    PENDING = "PENDING"           # Initial state — scan not yet started
    IN_PROGRESS = "IN_PROGRESS"   # Scan running
    PASSED = "PASSED"             # Scan complete — no violations found
    FAILED = "FAILED"             # Scan complete — violations found
    ERROR = "ERROR"               # Scan failed — see error_message in state
```

### Status → Exit Code Mapping

| Status   | CLI exit code |
| -------- | ------------- |
| `PASSED` | `0`           |
| `FAILED` | `1`           |
| `ERROR`  | `2`           |

---

## 8. ViolationList

The Pydantic model used as the structured output schema for the auditor LLM call. This is an internal model — callers receive `List[Violation]` via `AuditResult.violations`.

```python
class ViolationList(BaseModel):
    violations: List[Violation]
```

The auditor calls `llm.with_structured_output(ViolationList, method="function_calling")` for OpenAI-compatible providers, which instructs the LLM to return JSON conforming to the `ViolationList` schema.

---

## 9. LLMFactory

The factory and registry for LLM providers.

```python
from core.llm_provider import LLMFactory

# Create a provider instance by key
provider = LLMFactory.create_provider("github-copilot")

# Get a model for a specific agent role
llm = provider.get_model(role="auditor")

# List all registered providers
keys = LLMFactory.list_providers()  # ["bedrock", "github-copilot", "huggingface", "ollama"]
```

### `LLMProvider` ABC

```python
class LLMProvider(ABC):
    @abstractmethod
    def get_model(self, role: str = "default") -> BaseChatModel:
        """
        Return a configured LangChain chat model for the given agent role.

        Args:
            role: Agent role hint ("auditor", "intake", "default").
                  Implementations may use this to select different model sizes.
        """
```

### Self-registration pattern

```python
# At the bottom of each provider module:
LLMFactory.register_provider("my-provider", MyProvider)
```

Providers are registered at import time. `LLMFactory.create_provider()` triggers the import of all provider modules via `_load_providers()`.

---

## 10. DatabaseFactory

The factory and registry for database (checkpointer) providers.

```python
from core.database_provider import DatabaseFactory

provider = DatabaseFactory.create_provider("sqlite")
checkpointer = provider.get_checkpointer()  # returns a LangGraph-compatible checkpointer
```

### `DatabaseProvider` ABC

```python
class DatabaseProvider(ABC):
    @abstractmethod
    def get_checkpointer(self):
        """Return a LangGraph-compatible checkpointer instance."""
```

Currently only `sqlite` is implemented (`core/sqlite_provider.py`). The checkpointer uses the `DB_PATH` env var for the SQLite file location.

---

## 11. SARIF Output Schema

`AuditResult.to_sarif()` returns a SARIF 2.1.0 document. This is the format consumed by GitHub Advanced Security, Azure DevOps, and most enterprise SIEM/SAST integrations.

### SARIF structure produced by ADAG

```json
{
  "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
  "version": "2.1.0",
  "runs": [
    {
      "tool": {
            "driver": {
            "name": "ADAG",
            "version": "1.0.0",
          "informationUri": "https://github.com/your-org/arch_agent",
          "rules": [
            {
              "id": "<policy_ref>",
              "name": "<PascalCase policy name>",
              "shortDescription": {
                "text": "<policy title>"
              },
              "defaultConfiguration": {
                "level": "error"    // HIGH → error; MEDIUM → warning; LOW → note
              }
            }
          ]
        }
      },
      "results": [
        {
          "ruleId": "<policy_ref>",
          "level": "error",          // "error" | "warning" | "note"
          "message": {
            "text": "<violation description>"
          },
          "locations": [
            {
              "physicalLocation": {
                "artifactLocation": {
                  "uri": "<file_path>",
                  "uriBaseId": "%SRCROOT%"
                },
                "region": {
                  "startLine": <line_number>   // omitted if line_number is null
                }
              }
            }
          ],
          "fixes": [
            {
              "description": {
                "text": "<remediation_hint>"   // omitted if remediation_hint is null
              }
            }
          ]
        }
      ]
    }
  ]
}
```

### Severity → SARIF level mapping

| Violation Severity | SARIF level |
| ------------------ | ----------- |
| `HIGH`             | `error`     |
| `MEDIUM`           | `warning`   |
| `LOW`              | `note`      |
| `INFO`             | `note`      |

### Uploading to GitHub

```bash
adag scan ./infra/ --format sarif > results.sarif

# Upload using GitHub CLI
gh code-scanning upload --sarif results.sarif

# Or via the GitHub Actions upload action
# See docs/FUNCTIONALITY.md §5 for the full workflow YAML
```

### Merging SARIF from multiple files

When scanning a directory, the CLI merges all per-file SARIF runs into a single SARIF document:

```python
# adag/cli.py
def _merge_sarif(sarif_results: List[dict]) -> dict:
    """Merge multiple single-run SARIF dicts into one multi-run document."""
```

The merged document has one `run` entry per scanned file in the `runs` array.
