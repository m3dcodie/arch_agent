"""
ADAG MCP Server — Mode 2

Exposes ADAG's audit engine as MCP tools so any MCP-aware agent
(Claude Desktop, Cursor, Continue.dev, etc.) can call it mid-conversation.

Running standalone (stdio transport):
    python -m adag.mcp_server

Claude Desktop config (~/.claude_desktop_config.json):
    {
      "mcpServers": {
        "adag": {
          "command": "python",
          "args": ["-m", "adag.mcp_server"],
          "env": { "USE_RAG": "false" }
        }
      }
    }

Available tools:
    check_terraform_file(path)   — scan a single .tf file
    scan_terraform_dir(path)     — scan all .tf files in a directory
    list_policies()              — list active policies and their severity
    query_rag(question)          — query the RAG store (requires USE_RAG=true)
    ingest_document(path)        — add a doc to the RAG store (requires USE_RAG=true)
"""
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP(
    name="adag",
    instructions=(
        "ADAG is an AI-Driven Architecture Guardrail. "
        "Use check_terraform_file or scan_terraform_dir to audit Terraform code "
        "against infrastructure policies before suggesting deployments. "
        "Use list_policies to see what rules are active."
    ),
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _policies_dir() -> Path:
    """Return the active policies directory (env override or built-in bundle)."""
    env_dir = os.getenv("POLICIES_DIR")
    if env_dir:
        return Path(env_dir)
    # Built-in bundle: <repo_root>/policies/
    return Path(__file__).parent.parent / "policies"


def _parse_policy_metadata(md_path: Path) -> dict:
    """Parse Policy ID and Severity from a policy Markdown file."""
    text = md_path.read_text(encoding="utf-8")

    policy_id_match = re.search(r"## Policy ID\s+`([^`]+)`", text)
    severity_match = re.search(r"## Severity\s+\*\*([A-Z]+)\*\*", text)
    title_match = re.search(r"^# (.+)$", text, re.MULTILINE)

    return {
        "policy_id": policy_id_match.group(1) if policy_id_match else md_path.stem,
        "severity": severity_match.group(1) if severity_match else "UNKNOWN",
        "title": title_match.group(1) if title_match else md_path.stem,
        "file": md_path.name,
    }


def _format_results(results: list) -> dict[str, Any]:
    """Convert a list of AuditResult objects to a plain JSON-ready dict."""
    return {
        "files_scanned": len(results),
        "total_violations": sum(len(r.violations) for r in results),
        "results": [r.to_json() for r in results],
    }


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def check_terraform_file(path: str) -> dict[str, Any]:
    """
    Scan a single Terraform (.tf) file for policy violations.

    Args:
        path: Absolute or relative path to the .tf file to scan.

    Returns:
        Audit result with status, violations list, and remediation hints.
    """
    from adag.runner import ADAGRunner

    try:
        runner = ADAGRunner(terraform_file=path)
        results = runner.scan()
        return _format_results(results)
    except (FileNotFoundError, ValueError) as exc:
        return {"error": str(exc), "files_scanned": 0, "total_violations": 0, "results": []}


@mcp.tool()
def scan_terraform_dir(path: str) -> dict[str, Any]:
    """
    Scan all Terraform (.tf) files in a directory (recursive) for policy violations.

    Args:
        path: Absolute or relative path to the directory to scan.

    Returns:
        Aggregated audit results: one entry per .tf file, with all violations.
    """
    from adag.runner import ADAGRunner

    try:
        runner = ADAGRunner(terraform_dir=path)
        results = runner.scan()
        return _format_results(results)
    except (FileNotFoundError, ValueError) as exc:
        return {"error": str(exc), "files_scanned": 0, "total_violations": 0, "results": []}


@mcp.tool()
def list_policies() -> dict[str, Any]:
    """
    List all active ADAG policies and their severity levels.

    Returns:
        A list of policies with their ID, title, severity, and source file.
    """
    policies_path = _policies_dir()

    if not policies_path.exists():
        return {
            "error": f"Policies directory not found: {policies_path}",
            "policies": [],
        }

    policies = sorted(
        (_parse_policy_metadata(f) for f in policies_path.glob("*.md")),
        key=lambda p: (p["severity"], p["policy_id"]),
    )

    severity_counts: dict[str, int] = {}
    for p in policies:
        severity_counts[p["severity"]] = severity_counts.get(p["severity"], 0) + 1

    return {
        "policies_dir": str(policies_path),
        "total": len(policies),
        "by_severity": severity_counts,
        "policies": policies,
    }


@mcp.tool()
def query_rag(question: str) -> dict[str, Any]:
    """
    Query the RAG (Retrieval-Augmented Generation) store for architecture policies
    or standards relevant to a free-text question.

    Requires the RAG microservices to be running and USE_RAG=true.

    Args:
        question: Natural-language question about architecture policies or standards.

    Returns:
        Retrieved context chunks most relevant to the question.
    """
    use_rag = os.getenv("USE_RAG", "false").lower() == "true"
    if not use_rag:
        return {
            "error": (
                "RAG is not enabled. Set USE_RAG=true and ensure the RAG "
                "microservices are running to use this tool. "
                "See Mode 3 in the ADAG documentation."
            ),
            "context": [],
        }

    import requests
    appid = os.getenv("ADAG_APPID", "archapp")
    url   = os.getenv("RAG_CONTEXT_URL", "http://localhost:8000") + f"/context-augment/{appid}"
    try:
        response = requests.post(
            url,
            json={"question": question, "metadata": {}},
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return {
            "question": question,
            "context": data.get("context", data),
        }
    except requests.RequestException as exc:
        return {
            "error": f"RAG service unavailable: {exc}",
            "context": [],
        }


@mcp.tool()
def ingest_document(path: str) -> dict[str, Any]:
    """
    Ingest an architecture document (Markdown, ADR, diagram) into the RAG store
    so future audits can reference it.

    Requires the RAG microservices to be running and USE_RAG=true.
    This is a Mode 3 (Advanced RAG) feature.

    Args:
        path: Path to the document to ingest (.md, .txt, .pdf supported).

    Returns:
        Confirmation of ingestion or error details.
    """
    use_rag = os.getenv("USE_RAG", "false").lower() == "true"
    if not use_rag:
        return {
            "error": (
                "RAG is not enabled. Set USE_RAG=true and ensure the RAG "
                "microservices are running to use this tool. "
                "Run: cd /path/to/rag && ./run_all_services.sh"
            ),
        }

    doc_path = Path(path)
    if not doc_path.exists():
        return {"error": f"File not found: {path}"}

    import requests
    appid = os.getenv("ADAG_APPID", "archapp")
    url   = os.getenv("RAG_INGEST_URL", "http://localhost:8001") + f"/ingest/{appid}"
    try:
        payload = {
            "source_type": "local",
            "config": {"paths": [str(doc_path.resolve())]},
        }
        response = requests.post(
            url,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        return {
            "ingested": path,
            "appid": appid,
            "result": response.json(),
        }
    except requests.RequestException as exc:
        return {"error": f"Ingestion failed: {exc}"}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
