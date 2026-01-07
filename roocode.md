## Phase 1 Implementation Plan: "Standard Checker" (Weeks 1-2)

### Overview
Phase 1 focuses on building the foundational LangGraph infrastructure with a single, concrete use case: checking if "Delete Protection" is enabled for databases in Terraform files.

---

## 1. Technical Architecture

### Core Stack Selection

| Component | Technology | Justification |
|-----------|-----------|---------------|
| **Orchestration** | LangGraph | Enables stateful workflows with cycles and human-in-the-loop capability |
| **LLM** | Claude 3.5 Sonnet | Superior code understanding and reasoning for infrastructure analysis |
| **State Management** | SqliteSaver (LangGraph) | Provides persistence and checkpoint/resume capability |
| **Validation** | Pydantic v2 | Structured output parsing and type safety |
| **Backend** | Python 3.11+ | Native LangGraph support with modern type hints |
| **Testing** | pytest | Industry standard with excellent fixture support |

### Key Libraries
```
langgraph==0.2.0+
langchain-anthropic==0.1.0+
langchain-core==0.3.0+
pydantic==2.0+
pytest==8.0+
python-dotenv==1.0+
```

---

## 2. Project Structure

```
/adag-system
├── /agents
│   ├── __init__.py
│   ├── intake.py           # Terraform parser agent
│   └── auditor.py          # Delete protection checker
├── /core
│   ├── __init__.py
│   ├── state.py            # LangGraph state schema
│   └── graph.py            # Graph construction logic
├── /models
│   ├── __init__.py
│   └── violations.py       # Pydantic models for violations
├── /tests
│   ├── __init__.py
│   ├── fixtures/
│   │   ├── bad_terraform.tf    # Test case: no delete protection
│   │   └── good_terraform.tf   # Test case: has delete protection
│   ├── test_intake.py
│   └── test_auditor.py
├── /policies
│   └── delete_protection.md    # Human-readable policy document
├── .env.example
├── main.py                 # Entry point
├── requirements.txt
└── README.md
```

---

## 3. State Schema Design

```python
# core/state.py
from typing import Annotated, List, Optional
from typing_extensions import TypedDict
import operator
from pydantic import BaseModel

class Violation(BaseModel):
    """Structured violation output"""
    id: str
    resource_type: str
    resource_name: str
    severity: str  # "HIGH" | "MEDIUM" | "LOW"
    policy_ref: str
    description: str
    line_number: Optional[int] = None

class AgentState(TypedDict):
    """Phase 1 minimal state"""
    # Append-only message history
    messages: Annotated[list, operator.add]
    
    # Input
    iac_code: str              # Raw Terraform content
    file_path: str             # Source file path
    
    # Processing
    parsed_resources: List[dict]  # Extracted resource definitions
    
    # Output
    violations: List[Violation]   # Found issues
    status: str                   # "pending" | "passed" | "failed"
    current_node: str             # For debugging/logging
```

---

## 4. Implementation Phases (Week-by-Week)

### Week 1: Foundation & Skeleton

#### Day 1-2: Project Setup
- Initialize Python project with virtual environment
- Install core dependencies
- Create directory structure
- Set up pytest configuration
- Create `.env` for API keys

#### Day 3-4: State & Mock Nodes
**Goal:** Build the graph structure without LLM calls

```python
# core/graph.py (skeleton)
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

def intake_node(state: AgentState) -> AgentState:
    """Mock: Log input and return dummy parsed resources"""
    print(f"[INTAKE] Processing: {state['file_path']}")
    return {
        "parsed_resources": [{"type": "mock", "name": "test"}],
        "current_node": "intake"
    }

def auditor_node(state: AgentState) -> AgentState:
    """Mock: Log and return dummy violation"""
    print(f"[AUDITOR] Checking {len(state['parsed_resources'])} resources")
    return {
        "violations": [],
        "status": "passed",
        "current_node": "auditor"
    }

def build_graph():
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("intake", intake_node)
    workflow.add_node("auditor", auditor_node)
    
    # Define edges
    workflow.set_entry_point("intake")
    workflow.add_edge("intake", "auditor")
    workflow.add_edge("auditor", END)
    
    # Add persistence
    memory = SqliteSaver.from_conn_string(":memory:")
    return workflow.compile(checkpointer=memory)
```

**Deliverable:** Working graph that logs execution flow

#### Day 5: Test Infrastructure
Create ground truth test cases:

```python
# tests/fixtures/bad_terraform.tf
resource "aws_db_instance" "main" {
  identifier = "mydb"
  engine     = "postgres"
  # VIOLATION: Missing deletion_protection = true
}

# tests/fixtures/good_terraform.tf
resource "aws_db_instance" "main" {
  identifier = "mydb"
  engine     = "postgres"
  deletion_protection = true  # COMPLIANT
}
```

```python
# tests/test_graph.py
def test_graph_executes():
    graph = build_graph()
    result = graph.invoke({
        "iac_code": "...",
        "file_path": "test.tf",
        "messages": []
    })
    assert result["status"] in ["passed", "failed"]
```

---

### Week 2: LLM Integration & Validation

#### Day 6-7: Intake Agent (LLM-Powered Parser)

```python
# agents/intake.py
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate

INTAKE_PROMPT = """You are a Terraform parser. Extract all database resources from this code.

Terraform Code:
{iac_code}

Return a JSON array of resources with: type, name, attributes.
Focus on: aws_db_instance, aws_rds_cluster"""

def intake_node(state: AgentState) -> AgentState:
    llm = ChatAnthropic(model="claude-3-5-sonnet-20241022")
    prompt = ChatPromptTemplate.from_template(INTAKE_PROMPT)
    
    chain = prompt | llm
    response = chain.invoke({"iac_code": state["iac_code"]})
    
    # Parse LLM response into structured format
    parsed = parse_llm_json(response.content)
    
    return {
        "parsed_resources": parsed,
        "current_node": "intake",
        "messages": [f"Parsed {len(parsed)} resources"]
    }
```

#### Day 8-9: Auditor Agent (Policy Checker)

```python
# agents/auditor.py
AUDITOR_PROMPT = """You are a security auditor. Check if these database resources have deletion protection enabled.

Resources:
{resources}

Policy: All production databases MUST have deletion_protection = true

Return violations as JSON array with: resource_name, severity, description"""

def auditor_node(state: AgentState) -> AgentState:
    llm = ChatAnthropic(model="claude-3-5-sonnet-20241022")
    
    # Use Pydantic for structured output
    structured_llm = llm.with_structured_output(ViolationList)
    
    violations = structured_llm.invoke({
        "resources": state["parsed_resources"]
    })
    
    status = "failed" if violations else "passed"
    
    return {
        "violations": violations,
        "status": status,
        "current_node": "auditor"
    }
```

#### Day 10: Integration & Testing

**Test Suite:**
```python
def test_detects_missing_deletion_protection():
    """Should flag databases without deletion_protection"""
    graph = build_graph()
    result = graph.invoke({
        "iac_code": load_fixture("bad_terraform.tf"),
        "file_path": "bad.tf",
        "messages": []
    })
    
    assert result["status"] == "failed"
    assert len(result["violations"]) > 0
    assert "deletion_protection" in result["violations"][0].description

def test_passes_compliant_code():
    """Should pass databases with deletion_protection"""
    graph = build_graph()
    result = graph.invoke({
        "iac_code": load_fixture("good_terraform.tf"),
        "file_path": "good.tf",
        "messages": []
    })
    
    assert result["status"] == "passed"
    assert len(result["violations"]) == 0
```

---

## 5. Entry Point & CLI

```python
# main.py
import sys
from core.graph import build_graph

def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <terraform_file>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    with open(file_path) as f:
        iac_code = f.read()
    
    graph = build_graph()
    result = graph.invoke({
        "iac_code": iac_code,
        "file_path": file_path,
        "messages": []
    })
    
    print(f"\n{'='*50}")
    print(f"Status: {result['status'].upper()}")
    print(f"Violations: {len(result['violations'])}")
    
    for v in result['violations']:
        print(f"\n[{v.severity}] {v.resource_name}")
        print(f"  {v.description}")
    
    sys.exit(0 if result['status'] == 'passed' else 1)

if __name__ == "__main__":
    main()
```

---

## 6. Success Criteria for Phase 1

### Functional Requirements
- ✅ Parse Terraform files and extract database resources
- ✅ Check for `deletion_protection` attribute
- ✅ Return structured violations with severity
- ✅ Persist state using SqliteSaver
- ✅ Pass all test cases (good/bad Terraform)

### Non-Functional Requirements
- ✅ Execution time < 10 seconds per file
- ✅ Token usage < 5,000 tokens per check
- ✅ 100% test coverage on core logic
- ✅ Clear logging for debugging

---

## 7. Architecture Decision Records (ADRs)

### ADR-001: Single Policy Focus for MVP
**Decision:** Phase 1 checks only deletion protection, not all policies  
**Rationale:** Validates the graph architecture without RAG complexity  
**Trade-off:** Limited scope, but faster iteration

### ADR-002: In-Memory Checkpointing
**Decision:** Use SQLite in-memory for Phase 1  
**Rationale:** Simplifies setup; persistent DB added in Phase 2  
**Trade-off:** State lost on restart (acceptable for MVP)

### ADR-003: Pydantic for Structured Output
**Decision:** Force LLM to return Pydantic models  
**Rationale:** Eliminates parsing errors and ensures type safety  
**Trade-off:** Slightly more complex prompts

---

## 8. Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| LLM hallucination on parsing | Use structured output + validation layer |
| Token cost overruns | Cache parsed results; limit input size to 2000 lines |
| Terraform syntax variations | Start with AWS RDS only; expand in Phase 2 |
| API rate limits | Implement exponential backoff with tenacity library |

---

## 9. Transition to Phase 2

Phase 1 deliverables enable Phase 2 (RAG integration):
- **State schema** is extensible for policy retrieval
- **Auditor node** can be modified to query vector DB
- **Test infrastructure** supports adding new policy checks
- **Graph structure** allows inserting "Policy Analyst" node before Auditor

---

## 10. Developer Handoff Checklist

Before starting implementation:
- [ ] Claude API key configured in `.env`
- [ ] Python 3.11+ installed
- [ ] Git repository initialized
- [ ] README.md with setup instructions
- [ ] Test fixtures created (good/bad Terraform)
- [ ] CI/CD pipeline configured (optional for Phase 1)

**Estimated Effort:** 40-60 hours (1-2 weeks for senior engineer)