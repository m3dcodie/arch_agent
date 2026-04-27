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

        with patch("agents.auditor._invoke_structured", return_value=mock_result):
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

        with patch("agents.auditor._invoke_structured", return_value=mock_result):
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
    """Test intake agent's dynamic resource discovery from policies"""

    def test_intake_discovers_resources_from_policies(self):
        """Test that intake agent dynamically discovers resource types from policies"""
        from agents.intake import _get_auditable_resource_types

        # Get discovered resource types
        resource_types = _get_auditable_resource_types()

        # Should be a non-empty set
        assert isinstance(resource_types, set)
        assert len(resource_types) > 0

        # Should include at least the built-in resources
        assert "aws_db_instance" in resource_types
        assert "aws_s3_bucket" in resource_types
        assert "aws_kms_key" in resource_types
        assert "provider" in resource_types

    def test_intake_extracts_resources_from_builtin_policies(self):
        """Test intake agent extracts resources based on built-in policies"""
        from agents.intake import intake_node
        from models.violations import AuditStatus

        tf_code = """
resource "aws_db_instance" "main" {
  engine            = "postgres"
  deletion_protection = true
}

resource "aws_s3_bucket" "logs" {
  bucket = "my-logs"
}

resource "aws_unsupported_resource" "test" {
  name = "should-be-ignored"
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

        from unittest.mock import MagicMock

        mock_llm = MagicMock()

        result = intake_node(state, mock_llm)

        # Should have parsed the supported resources
        assert len(result["parsed_resources"]) >= 2

        # Verify correct resources were extracted
        resource_types = {r["resource_type"] for r in result["parsed_resources"]}
        assert "aws_db_instance" in resource_types
        assert "aws_s3_bucket" in resource_types

        # Unsupported resource should be ignored
        assert "aws_unsupported_resource" not in resource_types
