"""
Unit tests for the ADAG system.
"""

import pytest
from pathlib import Path

# Mock LLM for testing without AWS credentials
from unittest.mock import Mock, MagicMock, patch
from langchain_core.messages import AIMessage

from models.violations import (
    Violation,
    Severity,
    AuditStatus,
    TerraformResource,
    ResourceList,
    ViolationList,
)


@pytest.fixture
def mock_llm():
    """Create a mock LLM for testing"""
    llm = MagicMock()
    return llm


@pytest.fixture
def bad_terraform_code():
    """Load bad terraform fixture"""
    fixture_path = Path(__file__).parent / "fixtures" / "bad_terraform.tf"
    return fixture_path.read_text()


@pytest.fixture
def good_terraform_code():
    """Load good terraform fixture"""
    fixture_path = Path(__file__).parent / "fixtures" / "good_terraform.tf"
    return fixture_path.read_text()


class TestModels:
    """Test Pydantic models"""

    def test_violation_model(self):
        """Test Violation model creation"""
        violation = Violation(
            id="V001",
            resource_type="aws_db_instance",
            resource_name="main",
            severity=Severity.HIGH,
            policy_ref="delete_protection",
            description="Missing deletion protection",
        )

        assert violation.id == "V001"
        assert violation.severity == Severity.HIGH
        assert violation.resource_type == "aws_db_instance"

    def test_terraform_resource_model(self):
        """Test TerraformResource model creation"""
        resource = TerraformResource(
            resource_type="aws_db_instance",
            resource_name="main",
            attributes={"engine": "postgres", "deletion_protection": True},
            line_number=10,
        )

        assert resource.resource_type == "aws_db_instance"
        assert resource.attributes["deletion_protection"] is True

    def test_violation_list_model(self):
        """Test ViolationList model"""
        violations = ViolationList(violations=[])
        assert len(violations.violations) == 0

        violations.violations.append(
            Violation(
                id="V001",
                resource_type="aws_db_instance",
                resource_name="test",
                severity=Severity.HIGH,
                policy_ref="test",
                description="test",
            )
        )
        assert len(violations.violations) == 1


class TestProviders:
    """Test provider abstractions"""

    def test_llm_factory_registration(self):
        """Test LLM factory registration"""
        from core.llm_provider import LLMFactory
        import core.bedrock_provider  # This registers the provider

        providers = LLMFactory.list_providers()
        assert "bedrock" in providers

    def test_database_factory_registration(self):
        """Test database factory registration"""
        from core.database_provider import DatabaseFactory
        import core.sqlite_provider  # This registers the provider

        providers = DatabaseFactory.list_providers()
        assert "sqlite" in providers

    def test_sqlite_provider_memory(self):
        """Test SQLite provider with in-memory database"""
        from core.sqlite_provider import SQLiteProvider

        provider = SQLiteProvider(db_path=":memory:")
        assert provider.get_provider_name() == "sqlite"

        checkpointer = provider.get_checkpointer()
        assert checkpointer is not None


class TestIntakeAgent:
    """Test intake agent functionality"""

    def test_intake_rejects_empty_code(self, mock_llm):
        """Intake must return ERROR for empty or whitespace-only iac_code."""
        from agents.intake import intake_node

        state = {
            "iac_code": "   ",
            "file_path": "test.tf",
            "messages": [],
            "parsed_resources": [],
            "retrieved_policies": [],
            "resource_types": [],
            "violations": [],
            "status": AuditStatus.PENDING,
            "current_node": "",
            "error_message": "",
        }
        result = intake_node(state, mock_llm)
        assert result["status"] == AuditStatus.ERROR
        assert result["parsed_resources"] == []

    def test_intake_rejects_oversized_input(self, mock_llm):
        """Intake must return ERROR when iac_code exceeds 2 MB."""
        from agents.intake import intake_node, MAX_IAC_BYTES

        # Construct a payload that is exactly 1 byte over the limit
        oversized = "x" * (MAX_IAC_BYTES + 1)
        state = {
            "iac_code": oversized,
            "file_path": "test.tf",
            "messages": [],
            "parsed_resources": [],
            "retrieved_policies": [],
            "resource_types": [],
            "violations": [],
            "status": AuditStatus.PENDING,
            "current_node": "",
            "error_message": "",
        }
        result = intake_node(state, mock_llm)
        assert result["status"] == AuditStatus.ERROR
        assert "2 MB" in result["error_message"]
        assert result["parsed_resources"] == []

    def test_intake_deterministic_parser(self, mock_llm):
        """Test intake agent uses deterministic parser (no LLM required)"""
        from agents.intake import intake_node
        from core.state import AgentState

        tf_code = """
resource "aws_db_instance" "main" {
  engine            = "postgres"
  storage_encrypted = true
  deletion_protection = true
  backup_retention_period = 7
  multi_az = true
  publicly_accessible = false
}
"""
        state = {
            "iac_code": tf_code,
            "file_path": "test.tf",
            "messages": [],
            "parsed_resources": [],
            "retrieved_policies": [],
            "resource_types": [],
            "violations": [],
            "status": AuditStatus.PENDING,
            "current_node": "",
            "error_message": "",
        }

        # LLM should NOT be called — parser is deterministic
        result = intake_node(state, mock_llm)
        mock_llm.invoke.assert_not_called()

        assert result["current_node"] == "intake"
        assert result["status"] == AuditStatus.IN_PROGRESS
        assert len(result["parsed_resources"]) == 1
        r = result["parsed_resources"][0]
        assert r["resource_type"] == "aws_db_instance"
        assert r["resource_name"] == "main"
        assert r["attributes"]["storage_encrypted"] is True
        assert r["attributes"]["deletion_protection"] is True
        assert r["attributes"]["backup_retention_period"] == 7

        # resource_types must be populated for Phase 2 RAG
        assert "resource_types" in result
        assert "aws_db_instance" in result["resource_types"]


class TestHclParser:
    """Unit tests for the standalone HCL parser module."""

    def test_parse_hcl_value_booleans(self):
        from core.hcl_parser import parse_hcl_value

        assert parse_hcl_value("true") is True
        assert parse_hcl_value("True") is True
        assert parse_hcl_value("false") is False
        assert parse_hcl_value("FALSE") is False

    def test_parse_hcl_value_numbers(self):
        from core.hcl_parser import parse_hcl_value

        assert parse_hcl_value("7") == 7
        assert isinstance(parse_hcl_value("7"), int)
        assert parse_hcl_value("3.14") == 3.14
        assert isinstance(parse_hcl_value("3.14"), float)

    def test_parse_hcl_value_strings(self):
        from core.hcl_parser import parse_hcl_value

        assert parse_hcl_value('"postgres"') == "postgres"
        assert parse_hcl_value("'postgres'") == "postgres"

    def test_extract_flat_attrs_strips_comments(self):
        from core.hcl_parser import extract_flat_attrs

        body = '  engine = "mysql"  # primary engine\n  port = 3306\n'
        attrs = extract_flat_attrs(body)
        assert attrs["engine"] == "mysql"
        assert attrs["port"] == 3306

    def test_extract_resource_blocks_all_types(self):
        """Parser returns ALL resource types, not just policy-covered ones."""
        from core.hcl_parser import extract_resource_blocks

        code = """
resource "aws_db_instance" "db" {
  engine = "postgres"
}
resource "aws_custom_widget" "w" {
  size = 5
}
"""
        blocks = extract_resource_blocks(code)
        types = {b["resource_type"] for b in blocks}
        assert "aws_db_instance" in types
        assert "aws_custom_widget" in types

    def test_extract_provider_blocks(self):
        from core.hcl_parser import extract_provider_blocks

        code = 'provider "aws" {\n  region = "us-east-1"\n}\n'
        blocks = extract_provider_blocks(code)
        assert len(blocks) == 1
        assert blocks[0]["resource_type"] == "provider"
        assert blocks[0]["resource_name"] == "aws"
        assert blocks[0]["attributes"]["region"] == "us-east-1"

    def test_extract_block_body_nested_braces(self):
        from core.hcl_parser import extract_block_body

        text = "{ outer { inner = 1 } end = 2 }"
        body, end = extract_block_body(text, 0)
        assert "end = 2" in body
        assert end == len(text)


class TestAuditorAgent:
    """Test auditor agent functionality"""

    def test_auditor_with_violations(self, mock_llm):
        """Test auditor detects violations"""
        from agents.auditor import auditor_node

        mock_result = ViolationList(
            violations=[
                Violation(
                    id="V001",
                    resource_type="aws_db_instance",
                    resource_name="main",
                    severity=Severity.HIGH,
                    policy_ref="delete_protection",
                    description="Missing deletion protection",
                    remediation_hint="Add deletion_protection = true",
                )
            ]
        )

        state = {
            "iac_code": "",
            "file_path": "test.tf",
            "messages": [],
            "parsed_resources": [
                TerraformResource(
                    resource_type="aws_db_instance",
                    resource_name="main",
                    attributes={"engine": "postgres"},
                    line_number=1,
                )
            ],
            "retrieved_policies": [],
            "resource_types": [],
            "violations": [],
            "status": AuditStatus.IN_PROGRESS,
            "current_node": "intake",
            "error_message": "",
        }

        with patch("agents.auditor.invoke_structured", return_value=mock_result):
            result = auditor_node(state, mock_llm)

        assert result["current_node"] == "auditor"
        assert result["status"] == AuditStatus.FAILED
        assert len(result["violations"]) == 1
        assert result["violations"][0]["severity"] == Severity.HIGH

    def test_auditor_no_violations(self, mock_llm):
        """Test auditor passes compliant resources"""
        from agents.auditor import auditor_node

        mock_result = ViolationList(violations=[])

        state = {
            "iac_code": "",
            "file_path": "test.tf",
            "messages": [],
            "parsed_resources": [
                TerraformResource(
                    resource_type="aws_db_instance",
                    resource_name="main",
                    attributes={"engine": "postgres", "deletion_protection": True},
                    line_number=1,
                )
            ],
            "retrieved_policies": [],
            "resource_types": [],
            "violations": [],
            "status": AuditStatus.IN_PROGRESS,
            "current_node": "intake",
            "error_message": "",
        }

        with patch("agents.auditor.invoke_structured", return_value=mock_result):
            result = auditor_node(state, mock_llm)

        assert result["current_node"] == "auditor"
        assert result["status"] == AuditStatus.PASSED
        assert len(result["violations"]) == 0

    def test_auditor_no_resources(self, mock_llm):
        """Test auditor with no resources"""
        from agents.auditor import auditor_node

        # Create state with no resources
        state = {
            "iac_code": "",
            "file_path": "test.tf",
            "messages": [],
            "parsed_resources": [],
            "retrieved_policies": [],
            "resource_types": [],
            "violations": [],
            "status": AuditStatus.IN_PROGRESS,
            "current_node": "intake",
            "error_message": "",
        }

        # Run auditor
        result = auditor_node(state, mock_llm)

        assert result["status"] == AuditStatus.PASSED
        assert len(result["violations"]) == 0


class TestAuditorHelpers:
    """Unit tests for auditor helper functions."""

    def test_format_resources_handles_dicts_and_objects(self):
        """_format_resources_for_prompt accepts both dicts and TerraformResource objects."""
        from agents.auditor import _format_resources_for_prompt
        import json

        resource_obj = TerraformResource(
            resource_type="aws_db_instance",
            resource_name="db",
            attributes={"engine": "postgres"},
            line_number=1,
        )
        resource_dict = {
            "resource_type": "aws_s3_bucket",
            "resource_name": "bucket",
            "attributes": {},
            "line_number": 5,
        }
        output = json.loads(_format_resources_for_prompt([resource_obj, resource_dict]))
        types = {r["resource_type"] for r in output}
        assert "aws_db_instance" in types
        assert "aws_s3_bucket" in types

    def test_assign_violation_ids_fills_placeholders(self):
        """_assign_violation_ids must replace placeholder IDs."""
        from agents.auditor import _assign_violation_ids

        v1 = Violation(
            id="unique-id",
            resource_type="aws_db_instance",
            resource_name="db",
            severity=Severity.HIGH,
            policy_ref="p1",
            description="test",
        )
        v2 = Violation(
            id="",
            resource_type="aws_db_instance",
            resource_name="db2",
            severity=Severity.HIGH,
            policy_ref="p1",
            description="test",
        )
        _assign_violation_ids([v1, v2])
        assert v1.id not in ("unique-id", "")
        assert v2.id not in ("unique-id", "")
        # IDs must be distinct
        assert v1.id != v2.id

    def test_build_dynamic_prompt_escapes_braces(self):
        """build_dynamic_prompt must escape {{ }} in policy content."""
        from agents.prompts import build_dynamic_prompt
        from langchain_core.prompts import ChatPromptTemplate

        policy_with_braces = {
            "id": "p1",
            "title": "Test",
            "severity": "HIGH",
            "description": "Use {var} here",
            "requirements": "require {something}",
            "remediation": "",
        }
        prompt_text = build_dynamic_prompt([policy_with_braces])
        # Must not raise TemplateError — braces in policy content are escaped
        template = ChatPromptTemplate.from_template(prompt_text)
        rendered = template.format(resources_json="[]")
        # Original literal brace content must still appear after rendering
        assert "{var}" in rendered
        assert "{something}" in rendered

    def test_auditor_error_message_is_generic(self, mock_llm):
        """Exception handler must not expose str(e) in returned state."""
        from agents.auditor import auditor_node

        state = {
            "iac_code": "",
            "file_path": "test.tf",
            "messages": [],
            "parsed_resources": [TerraformResource(
                resource_type="aws_db_instance",
                resource_name="db",
                attributes={},
                line_number=1,
            )],
            "retrieved_policies": [],
            "resource_types": [],
            "violations": [],
            "status": AuditStatus.IN_PROGRESS,
            "current_node": "intake",
            "error_message": "",
        }

        secret = "s3://internal-bucket/credentials"
        with patch("agents.auditor.invoke_structured", side_effect=RuntimeError(secret)):
            result = auditor_node(state, mock_llm)

        assert result["status"] == AuditStatus.ERROR
        assert secret not in result["error_message"]
        assert secret not in " ".join(result["messages"])


class TestLLMUtils:
    """Unit tests for core/llm_utils.py."""

    def test_invoke_structured_uses_structured_output(self):
        """invoke_structured calls with_structured_output on the LLM."""
        from core.llm_utils import invoke_structured
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.runnables import RunnableLambda

        mock_llm = MagicMock()
        expected = ViolationList(violations=[])
        # with_structured_output must return a Runnable so `prompt | chain` works
        mock_llm.with_structured_output.return_value = RunnableLambda(lambda _: expected)

        prompt = ChatPromptTemplate.from_template("{resources_json}")
        result = invoke_structured(mock_llm, prompt, {"resources_json": "[]"}, ViolationList)

        assert result is expected
        mock_llm.with_structured_output.assert_called_once()

    def test_invoke_structured_falls_back_to_plain_json(self):
        """On a non-rate-limit structured-output error, plain JSON fallback is used."""
        from core.llm_utils import invoke_structured
        from langchain_core.prompts import ChatPromptTemplate

        mock_llm = MagicMock()
        mock_llm.with_structured_output.side_effect = NotImplementedError("unsupported")
        expected = ViolationList(violations=[])

        prompt = ChatPromptTemplate.from_template("{resources_json}")
        # Patch _plain_invoke directly — the plain invocation path is tested separately;
        # here we only verify that a non-rate-limit structured-output failure causes
        # the caller to receive the result from _plain_invoke.
        with patch("core.llm_utils._plain_invoke", return_value=expected) as mock_plain:
            result = invoke_structured(mock_llm, prompt, {"resources_json": "[]"}, ViolationList)

        assert result is expected
        mock_plain.assert_called_once()

    def test_invoke_structured_raises_after_retries_exhausted(self):
        """invoke_structured raises after all retries on rate-limit errors."""
        from core.llm_utils import invoke_structured, _MAX_RETRIES
        from langchain_core.prompts import ChatPromptTemplate

        mock_llm = MagicMock()
        # Simulate rate-limit on structured_output; plain invoke also rate-limits
        mock_llm.with_structured_output.side_effect = RuntimeError("429 Too Many Requests")
        mock_llm.invoke.side_effect = RuntimeError("429 Too Many Requests")

        prompt = ChatPromptTemplate.from_template("{resources_json}")
        with patch("core.llm_utils.time.sleep"):  # don't actually wait
            with pytest.raises(RuntimeError, match="429"):
                invoke_structured(mock_llm, prompt, {"resources_json": "[]"}, ViolationList)


class TestFixtures:
    """Test that fixtures are valid"""

    def test_bad_terraform_exists(self, bad_terraform_code):
        """Test bad terraform fixture exists and has content"""
        assert bad_terraform_code
        assert "aws_db_instance" in bad_terraform_code
        assert (
            "deletion_protection" not in bad_terraform_code
            or "deletion_protection = false" in bad_terraform_code
        )

    def test_good_terraform_exists(self, good_terraform_code):
        """Test good terraform fixture exists and has content"""
        assert good_terraform_code
        assert "aws_db_instance" in good_terraform_code
        assert "deletion_protection = true" in good_terraform_code


class TestPerAgentModelSelection:
    """Test per-agent model selection for all providers"""

    def test_bedrock_provider_accepts_model_id_kwarg(self):
        """Test Bedrock provider's get_model() method accepts model_id parameter"""
        from core.bedrock_provider import BedrockProvider

        # Verify the method signature includes support for model_id kwarg
        # by checking that get_model can be called with model_id parameter
        import inspect

        sig = inspect.signature(BedrockProvider.get_model)
        # Should accept **kwargs to allow model_id parameter
        assert "kwargs" in str(sig)

    def test_github_copilot_provider_accepts_model_kwarg(self):
        """Test GitHub Copilot provider's get_model() method accepts model parameter"""
        from core.github_copilot_provider import GitHubCopilotProvider

        # Verify the method signature includes support for model kwarg
        import inspect

        sig = inspect.signature(GitHubCopilotProvider.get_model)
        # Should accept **kwargs to allow model parameter
        assert "kwargs" in str(sig)

    def test_graph_get_llm_for_role_uses_env_vars(self):
        """Test _get_llm_for_role reads INTAKE_MODEL and AUDITOR_MODEL from env"""
        from core.graph import ADAGGraph
        import os

        # Verify the method looks for role-based env vars
        import inspect

        source = inspect.getsource(ADAGGraph._get_llm_for_role)
        # Should read environment variables with role prefix
        assert 'f"{role}_MODEL"' in source or "{role}_MODEL" in source


class TestDynamicResourceDiscovery:
    """Test intake agent resource extraction and hcl_parser independence from policies."""

    def test_hcl_parser_has_no_policy_dependency(self):
        """hcl_parser must not import from core.policy_loader or agents modules."""
        import importlib
        import sys

        # Force a fresh import inspection
        mod = importlib.import_module("core.hcl_parser")
        source_file = mod.__file__

        with open(source_file) as f:
            source = f.read()

        assert "policy_loader" not in source, "hcl_parser must not depend on policy_loader"
        assert "load_policies" not in source, "hcl_parser must not depend on load_policies"

    def test_intake_extracts_all_resource_types(self):
        """Parser returns ALL resource types; policy filtering is downstream."""
        from agents.intake import intake_node
        from models.violations import AuditStatus
        from unittest.mock import MagicMock

        tf_code = """
resource "aws_db_instance" "main" {
  engine            = "postgres"
  deletion_protection = true
}

resource "aws_s3_bucket" "logs" {
  bucket = "my-logs"
}

resource "aws_unsupported_resource" "test" {
  name = "not-filtered-at-parse-time"
}
"""
        state = {
            "iac_code": tf_code,
            "file_path": "test.tf",
            "messages": [],
            "parsed_resources": [],
            "retrieved_policies": [],
            "resource_types": [],
            "violations": [],
            "status": AuditStatus.PENDING,
            "current_node": "",
            "error_message": "",
        }

        result = intake_node(state, MagicMock())

        assert result["status"] == AuditStatus.IN_PROGRESS
        # All three resource blocks must be present — no parse-time filtering
        assert len(result["parsed_resources"]) == 3

        resource_types = {r["resource_type"] for r in result["parsed_resources"]}
        assert "aws_db_instance" in resource_types
        assert "aws_s3_bucket" in resource_types
        # Previously filtered — now correctly forwarded to the auditor
        assert "aws_unsupported_resource" in resource_types

        # resource_types list must mirror the set of found types
        assert set(result["resource_types"]) == resource_types


class TestPolicyAnalystAgent:
    """Unit tests for the policy_analyst_node."""

    def _make_state(self, resource_types=None):
        return {
            "iac_code": "",
            "file_path": "test.tf",
            "messages": [],
            "parsed_resources": [],
            "retrieved_policies": [],
            "resource_types": ["aws_db_instance"] if resource_types is None else resource_types,
            "violations": [],
            "status": AuditStatus.IN_PROGRESS,
            "current_node": "intake",
            "error_message": "",
        }

    def test_offline_mode_loads_disk_policies(self, monkeypatch):
        """Offline mode (default) returns policies loaded from disk."""
        from agents.policy_analyst import policy_analyst_node

        monkeypatch.delenv("USE_RAG", raising=False)
        result = policy_analyst_node(self._make_state())

        assert result["current_node"] == "policy_analyst"
        # Built-in policies directory is non-empty
        assert len(result["retrieved_policies"]) > 0
        # resource_types passed through unchanged
        assert result["resource_types"] == ["aws_db_instance"]
        # Status must NOT be ERROR
        assert result.get("status") != AuditStatus.ERROR

    def test_empty_resource_types_skips_retrieval(self, monkeypatch):
        """When no resource types are present, retrieval is skipped."""
        from agents.policy_analyst import policy_analyst_node

        monkeypatch.delenv("USE_RAG", raising=False)
        result = policy_analyst_node(self._make_state(resource_types=[]))

        assert result["retrieved_policies"] == []
        assert result["resource_types"] == []
        assert result["current_node"] == "policy_analyst"

    def test_rag_mode_uses_fetch_function(self, monkeypatch):
        """RAG mode calls _fetch_rag_chunks and maps chunks to Policy objects."""
        import agents.policy_analyst as pa

        monkeypatch.setenv("USE_RAG", "true")
        monkeypatch.setenv("ADAG_APPID", "testapp")

        fake_chunk = {
            "document": "# Encryption\nAll data must be encrypted.",
            "metadata": {
                "id": "encryption_at_rest",
                "title": "Encryption At Rest",
                "severity": "HIGH",
                "scope": ["aws_db_instance"],
            },
            "distance": 0.1,
        }

        monkeypatch.setattr(pa, "_fetch_rag_chunks", lambda *a, **kw: [fake_chunk])

        result = pa.policy_analyst_node(self._make_state())

        assert result["current_node"] == "policy_analyst"
        assert len(result["retrieved_policies"]) == 1
        p = result["retrieved_policies"][0]
        assert p["id"] == "encryption_at_rest"
        assert p["severity"] == "HIGH"
        # Scope must come from chunk metadata, NOT from state resource_types
        assert p["scope"] == ["aws_db_instance"]

    def test_rag_mode_falls_back_to_disk_on_empty_chunks(self, monkeypatch):
        """RAG mode falls back to disk policies when no chunks are returned."""
        import agents.policy_analyst as pa

        monkeypatch.setenv("USE_RAG", "true")
        monkeypatch.setattr(pa, "_fetch_rag_chunks", lambda *a, **kw: [])

        result = pa.policy_analyst_node(self._make_state())

        assert result["current_node"] == "policy_analyst"
        # Should fall back to disk — built-in policies are non-empty
        assert len(result["retrieved_policies"]) > 0
        assert result.get("status") != AuditStatus.ERROR

    def test_rag_mode_returns_error_on_network_failure(self, monkeypatch):
        """A network failure in RAG mode returns ERROR without leaking exception details."""
        import agents.policy_analyst as pa

        monkeypatch.setenv("USE_RAG", "true")
        monkeypatch.setattr(
            pa, "_fetch_rag_chunks",
            lambda *a, **kw: (_ for _ in ()).throw(ConnectionError("http://internal-host:8000 unreachable"))
        )

        result = pa.policy_analyst_node(self._make_state())

        assert result["status"] == AuditStatus.ERROR
        # Internal URL must NOT appear in the error message
        assert "internal-host" not in result["error_message"]
        assert "internal-host" not in result["messages"][0]

    def test_appid_is_url_encoded(self, monkeypatch):
        """ADAG_APPID containing path-traversal characters must be URL-encoded."""
        import agents.policy_analyst as pa

        monkeypatch.setenv("USE_RAG", "true")
        monkeypatch.setenv("ADAG_APPID", "../evil")

        captured = {}

        def fake_fetch(endpoint, query, resource_types):
            captured["endpoint"] = endpoint
            return []

        monkeypatch.setattr(pa, "_fetch_rag_chunks", fake_fetch)
        # Trigger offline fallback (empty chunks) — we only care about the endpoint
        pa.policy_analyst_node(self._make_state())

        assert "../evil" not in captured.get("endpoint", "")
        assert "%2F" in captured.get("endpoint", "") or "%2E" in captured.get("endpoint", "")

    def test_fetch_rag_chunks_passes_timeout(self, monkeypatch):
        """_fetch_rag_chunks must pass a timeout to requests.post."""
        import agents.policy_analyst as pa
        import requests as req

        captured = {}

        def fake_post(url, json=None, headers=None, timeout=None):
            captured["timeout"] = timeout
            m = MagicMock()
            m.raise_for_status = lambda: None
            m.json.return_value = {"relevant_chunks": []}
            return m

        monkeypatch.setattr(req, "post", fake_post)
        pa._fetch_rag_chunks("http://localhost:8000/context-augment/app", "query", [])

        assert captured.get("timeout") is not None
        assert captured["timeout"] > 0
