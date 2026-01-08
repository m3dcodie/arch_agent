"""
Unit tests for the ADAG system.
"""
import pytest
from pathlib import Path

# Mock LLM for testing without AWS credentials
from unittest.mock import Mock, MagicMock, patch
from langchain_core.messages import AIMessage

from models.violations import (
    Violation, Severity, AuditStatus, 
    TerraformResource, ResourceList, ViolationList
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
            description="Missing deletion protection"
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
            line_number=10
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
                description="test"
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
    
    def test_intake_with_mock_llm(self, mock_llm):
        """Test intake agent with mocked LLM"""
        from agents.intake import intake_node
        from core.state import AgentState
        
        # Mock the structured output
        mock_result = ResourceList(
            resources=[
                TerraformResource(
                    resource_type="aws_db_instance",
                    resource_name="main",
                    attributes={"engine": "postgres"},
                    line_number=1
                )
            ]
        )
        
        # Create a mock that properly returns the chain
        def mock_with_structured_output(schema):
            mock_chain = MagicMock()
            mock_chain.invoke = MagicMock(return_value=mock_result)
            return mock_chain
        
        mock_llm.with_structured_output = mock_with_structured_output
        
        # Create initial state
        state = {
            "iac_code": "resource \"aws_db_instance\" \"main\" {}",
            "file_path": "test.tf",
            "messages": [],
            "parsed_resources": [],
            "retrieved_policies": [],
            "resource_types": [],
            "violations": [],
            "status": AuditStatus.PENDING,
            "current_node": "",
            "error_message": ""
        }
        
        # Run intake
        result = intake_node(state, mock_llm)
        
        assert result["current_node"] == "intake"
        assert result["status"] == AuditStatus.IN_PROGRESS
        assert len(result["parsed_resources"]) == 1
        assert result["parsed_resources"][0].resource_type == "aws_db_instance"


class TestAuditorAgent:
    """Test auditor agent functionality"""
    
    def test_auditor_with_violations(self, mock_llm):
        """Test auditor detects violations"""
        from agents.auditor import auditor_node
        
        # Mock the structured output with violations
        mock_result = ViolationList(
            violations=[
                Violation(
                    id="V001",
                    resource_type="aws_db_instance",
                    resource_name="main",
                    severity=Severity.HIGH,
                    policy_ref="delete_protection",
                    description="Missing deletion protection",
                    remediation_hint="Add deletion_protection = true"
                )
            ]
        )
        
        # Create a mock that properly returns the chain
        def mock_with_structured_output(schema):
            mock_chain = MagicMock()
            mock_chain.invoke = MagicMock(return_value=mock_result)
            return mock_chain
        
        mock_llm.with_structured_output = mock_with_structured_output
        
        # Create state with parsed resources
        state = {
            "iac_code": "",
            "file_path": "test.tf",
            "messages": [],
            "parsed_resources": [
                TerraformResource(
                    resource_type="aws_db_instance",
                    resource_name="main",
                    attributes={"engine": "postgres"},
                    line_number=1
                )
            ],
            "retrieved_policies": [],
            "resource_types": [],
            "violations": [],
            "status": AuditStatus.IN_PROGRESS,
            "current_node": "intake",
            "error_message": ""
        }
        
        # Run auditor
        result = auditor_node(state, mock_llm)
        
        assert result["current_node"] == "auditor"
        assert result["status"] == AuditStatus.FAILED
        assert len(result["violations"]) == 1
        assert result["violations"][0].severity == Severity.HIGH
    
    def test_auditor_no_violations(self, mock_llm):
        """Test auditor passes compliant resources"""
        from agents.auditor import auditor_node
        
        # Mock the structured output with no violations
        mock_result = ViolationList(violations=[])
        
        # Create a mock that properly returns the chain
        def mock_with_structured_output(schema):
            mock_chain = MagicMock()
            mock_chain.invoke = MagicMock(return_value=mock_result)
            return mock_chain
        
        mock_llm.with_structured_output = mock_with_structured_output
        
        # Create state with compliant resources
        state = {
            "iac_code": "",
            "file_path": "test.tf",
            "messages": [],
            "parsed_resources": [
                TerraformResource(
                    resource_type="aws_db_instance",
                    resource_name="main",
                    attributes={"engine": "postgres", "deletion_protection": True},
                    line_number=1
                )
            ],
            "retrieved_policies": [],
            "resource_types": [],
            "violations": [],
            "status": AuditStatus.IN_PROGRESS,
            "current_node": "intake",
            "error_message": ""
        }
        
        # Run auditor
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
            "error_message": ""
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
        assert "deletion_protection" not in bad_terraform_code or "deletion_protection = false" in bad_terraform_code
    
    def test_good_terraform_exists(self, good_terraform_code):
        """Test good terraform fixture exists and has content"""
        assert good_terraform_code
        assert "aws_db_instance" in good_terraform_code
        assert "deletion_protection = true" in good_terraform_code
