# ADAG - AI-Driven Architecture Guardrail

**Phase 1: Deletion Protection Checker**

An intelligent, multi-agent system that audits infrastructure-as-code (IaC) files for compliance with architecture standards. Phase 1 focuses on checking AWS database resources for deletion protection.

## 🎯 Overview

ADAG uses LangGraph and AWS Bedrock (Claude Sonnet 4.5) to automatically review Terraform files and identify policy violations. It's designed with abstraction layers to support multiple LLM providers and database backends.

### Key Features

- ✅ **Automated Policy Checking**: Scans Terraform files for deletion protection compliance
- ✅ **Multi-Agent Architecture**: Separate agents for parsing and auditing
- ✅ **Stateful Workflows**: Uses LangGraph for persistent, resumable workflows
- ✅ **Structured Output**: Pydantic models ensure type-safe, validated results
- ✅ **Provider Abstraction**: Easy to swap LLM providers or databases
- ✅ **Detailed Reporting**: Clear violation reports with remediation hints

## 📋 Prerequisites

- Python 3.11 or higher
- AWS Account with Bedrock access
- AWS CLI configured with appropriate credentials
- Access to Claude Sonnet 4.5 model in AWS Bedrock

## 🚀 Installation

### 1. Clone the Repository

```bash
cd /home/stahir/projects/arch_agent/arch_agent_1
```

### 2. Create Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and configure your settings:

```bash
# AWS Configuration
AWS_PROFILE=default
AWS_REGION=us-east-1

# LLM Configuration
LLM_PROVIDER=bedrock
LLM_MODEL_ID=anthropic.claude-sonnet-4-5-20250929-v1:0

# Database Configuration
DB_PROVIDER=sqlite
DB_PATH=./data/adag.db

# Application Settings
LOG_LEVEL=INFO
```

### 5. Verify AWS Configuration

```bash
aws sts get-caller-identity --profile default
```

Ensure you have access to Bedrock:

```bash
aws bedrock list-foundation-models --region us-east-1 --profile default
```

## 📖 Usage

### Basic Usage

Run the audit on a Terraform file:

```bash
python main.py <path-to-terraform-file>
```

### Example: Test with Fixtures

**Test with non-compliant code (should fail):**

```bash
python main.py tests/fixtures/bad_terraform.tf
```

Expected output:
```
======================================================================
  ADAG - AI-Driven Architecture Guardrail
  Phase 1: Deletion Protection Checker
======================================================================

Reading file: tests/fixtures/bad_terraform.tf
Initializing ADAG system...
✓ System initialized

Running audit on tests/fixtures/bad_terraform.tf...
----------------------------------------------------------------------

======================================================================
AUDIT RESULTS
======================================================================

Status: ✗ FAILED
File: tests/fixtures/bad_terraform.tf
Resources Analyzed: 2
Violations Found: 2

----------------------------------------------------------------------
VIOLATIONS
----------------------------------------------------------------------

1. 🔴 [HIGH] main
   Type: aws_db_instance
   Issue: Database instance does not have deletion protection enabled
   Line: 3
   Fix: Add 'deletion_protection = true' to the resource

2. 🔴 [HIGH] aurora
   Type: aws_rds_cluster
   Issue: Database cluster has deletion protection explicitly disabled
   Line: 23
   Fix: Change 'deletion_protection = false' to 'deletion_protection = true'

======================================================================
```

**Test with compliant code (should pass):**

```bash
python main.py tests/fixtures/good_terraform.tf
```

Expected output:
```
======================================================================
AUDIT RESULTS
======================================================================

Status: ✓ PASSED
File: tests/fixtures/good_terraform.tf
Resources Analyzed: 3
Violations Found: 0

======================================================================
```

### Exit Codes

- `0`: Audit passed (no violations)
- `1`: Audit failed (violations found)
- `2`: Error during execution

## 🧪 Running Tests

Run the test suite:

```bash
pytest tests/ -v
```

Run with coverage:

```bash
pytest tests/ --cov=. --cov-report=html
```

Run specific test:

```bash
pytest tests/test_adag.py::TestAuditorAgent::test_auditor_with_violations -v
```

## 🏗️ Architecture

### Project Structure

```
/adag-system
├── agents/
│   ├── __init__.py
│   ├── intake.py           # Terraform parser agent
│   └── auditor.py          # Policy compliance checker
├── core/
│   ├── __init__.py
│   ├── llm_provider.py     # LLM provider abstraction
│   ├── bedrock_provider.py # AWS Bedrock implementation
│   ├── database_provider.py # Database abstraction
│   ├── sqlite_provider.py  # SQLite implementation
│   ├── state.py            # LangGraph state schema
│   └── graph.py            # Workflow construction
├── models/
│   ├── __init__.py
│   └── violations.py       # Pydantic models
├── tests/
│   ├── __init__.py
│   ├── test_adag.py        # Unit tests
│   └── fixtures/
│       ├── bad_terraform.tf
│       └── good_terraform.tf
├── policies/
│   └── delete_protection.md # Policy documentation
├── .env.example
├── .gitignore
├── requirements.txt
├── main.py                 # Entry point
└── README.md
```

### Workflow

```
┌─────────────┐
│   Start     │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Intake    │  Parse Terraform code
│   Agent     │  Extract database resources
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Auditor    │  Check deletion protection
│   Agent     │  Generate violations
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Report    │  Display results
│   Results   │  Exit with status code
└─────────────┘
```

### Key Components

1. **LLM Provider Abstraction** ([`core/llm_provider.py`](core/llm_provider.py:1))
   - Factory pattern for LLM providers
   - Currently supports AWS Bedrock
   - Easy to add OpenAI, Anthropic Direct, etc.

2. **Database Provider Abstraction** ([`core/database_provider.py`](core/database_provider.py:1))
   - Factory pattern for checkpoint storage
   - Currently supports SQLite
   - Easy to add PostgreSQL, Redis, etc.

3. **Intake Agent** ([`agents/intake.py`](agents/intake.py:1))
   - Parses Terraform files
   - Extracts database resources
   - Uses structured output with Pydantic

4. **Auditor Agent** ([`agents/auditor.py`](agents/auditor.py:1))
   - Checks deletion protection policy
   - Generates violation reports
   - Assigns severity levels

5. **LangGraph Workflow** ([`core/graph.py`](core/graph.py:1))
   - Orchestrates agent execution
   - Manages state transitions
   - Provides checkpointing

## 🔧 Configuration

### Switching LLM Providers

To add a new LLM provider:

1. Create a new provider class inheriting from [`LLMProvider`](core/llm_provider.py:10)
2. Implement required methods
3. Register with [`LLMFactory`](core/llm_provider.py:37)

Example:
```python
from core.llm_provider import LLMProvider, LLMFactory

class OpenAIProvider(LLMProvider):
    def get_model(self, **kwargs):
        # Implementation
        pass
    
    # ... other methods

LLMFactory.register_provider("openai", OpenAIProvider)
```

### Switching Database Providers

Similar pattern for database providers - see [`core/database_provider.py`](core/database_provider.py:1)

## 📊 Policy: Deletion Protection

**Severity:** HIGH

**Description:** All production database instances MUST have deletion protection enabled.

**Applies to:**
- `aws_db_instance`
- `aws_rds_cluster`
- `aws_db_cluster_instance`

**Requirement:** `deletion_protection = true`

See [`policies/delete_protection.md`](policies/delete_protection.md:1) for full policy details.

## 🛣️ Roadmap

### Phase 1: Standard Checker ✅ (Current)
- Single policy check (deletion protection)
- Basic LangGraph workflow
- AWS Bedrock integration
- SQLite persistence

### Phase 2: Knowledge Base (Weeks 3-4)
- RAG integration with vector database
- Dynamic policy loading from documents
- Multiple policy checks
- Policy versioning

### Phase 3: Multi-Agent Critique (Weeks 5-6)
- Remediation agent (auto-fix generation)
- Validator agent (false positive detection)
- Human-in-the-loop approval
- Git patch generation

## 🤝 Contributing

This is a leadership demonstration project. For production use:

1. Add comprehensive error handling
2. Implement retry logic with exponential backoff
3. Add logging and observability
4. Create CI/CD pipeline
5. Add integration tests with real AWS Bedrock
6. Implement rate limiting
7. Add cost tracking for LLM calls

## 📝 License

This project is for demonstration and learning purposes.

## 🙋 Support

For issues or questions:
1. Check the policy documentation in [`policies/`](policies/)
2. Review test cases in [`tests/test_adag.py`](tests/test_adag.py:1)
3. Examine fixture examples in [`tests/fixtures/`](tests/fixtures/)

## 🎓 Architecture Decision Records

### ADR-001: AWS Bedrock as Default LLM Provider
**Decision:** Use AWS Bedrock with Claude Sonnet 4.5  
**Rationale:** Enterprise-ready, no data retention, excellent code understanding  
**Trade-off:** Requires AWS setup, but provides better security posture

### ADR-002: Provider Abstraction Pattern
**Decision:** Abstract LLM and database providers using factory pattern  
**Rationale:** Enables easy switching between providers without code changes  
**Trade-off:** Additional complexity, but critical for flexibility

### ADR-003: Structured Output with Pydantic
**Decision:** Force LLM to return Pydantic models  
**Rationale:** Type safety, validation, eliminates parsing errors  
**Trade-off:** Slightly more complex prompts, but much more reliable

### ADR-004: SQLite for Phase 1
**Decision:** Use SQLite for checkpoint storage  
**Rationale:** Simple setup, no external dependencies for MVP  
**Trade-off:** Not suitable for distributed systems, but perfect for Phase 1

---

**Built with:** LangGraph • AWS Bedrock • Claude Sonnet 4.5 • Python 3.11+
