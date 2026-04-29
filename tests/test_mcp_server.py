"""
Tests for the ADAG MCP server (adag/mcp_server.py).

Two tiers:
  - Fast / no-LLM  : list_policies, query_rag stub, ingest_document stub
  - Mocked-LLM     : check_terraform_file, scan_terraform_dir
                     (patch the graph so no AWS credentials are needed)
"""
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Fixtures shared with the rest of the test suite
FIXTURES = Path(__file__).parent / "fixtures"
BAD_TF   = str(FIXTURES / "bad_terraform.tf")
GOOD_TF  = str(FIXTURES / "good_terraform.tf")


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def rag_disabled(monkeypatch):
    """Ensure all MCP tests run with RAG disabled (offline mode)."""
    monkeypatch.setenv("USE_RAG", "false")


def _make_fake_graph(violations: list, status_value: str = "failed"):
    """
    Return a mock graph whose .invoke() returns a minimal state dict,
    mimicking what core/graph.py produces.
    """
    from models.violations import AuditStatus
    fake_graph = MagicMock()
    fake_graph.invoke.return_value = {
        "status": AuditStatus(status_value),
        "file_path": BAD_TF,
        "parsed_resources": [MagicMock()],
        "violations": violations,
    }
    return fake_graph


# ---------------------------------------------------------------------------
# list_policies — no LLM, no network
# ---------------------------------------------------------------------------

class TestListPolicies:
    def test_returns_ten_policies(self):
        from adag.mcp_server import list_policies
        result = list_policies()
        assert result["total"] == 10

    def test_known_policy_ids_present(self):
        from adag.mcp_server import list_policies
        result = list_policies()
        ids = {p["policy_id"] for p in result["policies"]}
        assert "encryption_at_rest" in ids
        assert "delete_protection" in ids
        assert "required_tagging" in ids

    def test_severity_counts(self):
        from adag.mcp_server import list_policies
        result = list_policies()
        by_sev = result["by_severity"]
        # Must have the three tiers; totals must sum to 10
        assert sum(by_sev.values()) == 10
        assert "HIGH" in by_sev

    def test_each_policy_has_required_fields(self):
        from adag.mcp_server import list_policies
        result = list_policies()
        for p in result["policies"]:
            assert "policy_id" in p
            assert "severity" in p
            assert "title" in p
            assert "file" in p

    def test_bad_policies_dir_returns_error(self, monkeypatch):
        monkeypatch.setenv("POLICIES_DIR", "/nonexistent-path")
        from adag.mcp_server import list_policies
        result = list_policies()
        assert "error" in result
        assert result["policies"] == []


# ---------------------------------------------------------------------------
# query_rag — stub behaviour when RAG is disabled
# ---------------------------------------------------------------------------

class TestQueryRagStub:
    def test_returns_error_when_rag_disabled(self):
        from adag.mcp_server import query_rag
        result = query_rag("What are the encryption policies?")
        assert "error" in result
        assert "USE_RAG" in result["error"]
        assert result["context"] == []

    def test_error_message_mentions_mode3(self):
        from adag.mcp_server import query_rag
        result = query_rag("anything")
        assert "Mode 3" in result["error"] or "USE_RAG" in result["error"]


# ---------------------------------------------------------------------------
# ingest_document — stub behaviour when RAG is disabled
# ---------------------------------------------------------------------------

class TestIngestDocumentStub:
    def test_returns_error_when_rag_disabled(self):
        from adag.mcp_server import ingest_document
        result = ingest_document(BAD_TF)
        assert "error" in result
        assert "USE_RAG" in result["error"]

    def test_file_not_found_when_rag_enabled(self, monkeypatch):
        monkeypatch.setenv("USE_RAG", "true")
        from adag.mcp_server import ingest_document
        result = ingest_document("/totally/nonexistent/file.md")
        assert "error" in result
        assert "not found" in result["error"].lower()


# ---------------------------------------------------------------------------
# check_terraform_file — mock the LangGraph to avoid AWS calls
# ---------------------------------------------------------------------------

class TestCheckTerraformFile:
    def test_returns_violations_for_bad_tf(self):
        from models.violations import Violation, Severity
        fake_violation = Violation(
            id="V001",
            resource_type="aws_db_instance",
            resource_name="main",
            severity=Severity.HIGH,
            policy_ref="delete_protection",
            description="Missing deletion protection",
            remediation_hint="Add deletion_protection = true",
        )

        with patch("core.graph.create_graph", return_value=_make_fake_graph([fake_violation])):
            from adag.mcp_server import check_terraform_file
            result = check_terraform_file(BAD_TF)

        assert result["files_scanned"] == 1
        assert result["total_violations"] == 1
        assert result["results"][0]["violations"][0]["policy_ref"] == "delete_protection"

    def test_returns_zero_violations_for_good_tf(self):
        with patch("core.graph.create_graph", return_value=_make_fake_graph([], status_value="passed")):
            from adag.mcp_server import check_terraform_file
            result = check_terraform_file(GOOD_TF)

        assert result["total_violations"] == 0

    def test_result_is_json_serialisable(self):
        from models.violations import Violation, Severity
        fake_violation = Violation(
            id="V002",
            resource_type="aws_s3_bucket",
            resource_name="assets",
            severity=Severity.MEDIUM,
            policy_ref="public_access_block",
            description="Public access block not enabled",
        )
        with patch("core.graph.create_graph", return_value=_make_fake_graph([fake_violation])):
            from adag.mcp_server import check_terraform_file
            result = check_terraform_file(BAD_TF)

        # Must not raise
        serialised = json.dumps(result)
        assert len(serialised) > 0

    def test_nonexistent_file_returns_error(self):
        with patch("core.graph.create_graph", return_value=_make_fake_graph([])):
            from adag.mcp_server import check_terraform_file
            result = check_terraform_file("/no/such/file.tf")

        # Tool catches FileNotFoundError and returns a structured error dict
        assert "error" in result
        assert result["files_scanned"] == 0


# ---------------------------------------------------------------------------
# scan_terraform_dir — mock the LangGraph
# ---------------------------------------------------------------------------

class TestScanTerraformDir:
    def test_scans_fixtures_directory(self):
        # fixtures/ has 2 .tf files
        with patch("core.graph.create_graph", return_value=_make_fake_graph([], status_value="passed")):
            from adag.mcp_server import scan_terraform_dir
            result = scan_terraform_dir(str(FIXTURES))

        assert result["files_scanned"] == 2
        assert "results" in result

    def test_nonexistent_dir_returns_error(self):
        with patch("core.graph.create_graph", return_value=_make_fake_graph([])):
            from adag.mcp_server import scan_terraform_dir
            result = scan_terraform_dir("/no/such/dir")

        # Tool catches FileNotFoundError and returns a structured error dict
        assert "error" in result
        assert result["files_scanned"] == 0
