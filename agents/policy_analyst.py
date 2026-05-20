"""
Policy Analyst agent — retrieves relevant policies for auditing.

Operates in two modes controlled by the USE_RAG environment variable:
  - Offline/disk mode (USE_RAG=false, default): loads all policies from the
    local policies/ directory (or POLICIES_DIR). No external services required.
  - RAG mode (USE_RAG=true): queries the external RAG microservices
    (https://github.com/m3dcodie/rag-pipeline) for semantically relevant
    policy chunks. Falls back to disk if the API returns no results.
"""
import logging
import os
from typing import Dict, Any, List
from urllib.parse import quote

import requests

from core.state import AgentState
from models.policy import Policy
from models.violations import AuditStatus
from core.policy_loader import load_policies_from_dir

logger = logging.getLogger(__name__)

# Hard timeout (seconds) for the RAG context-augmentation API call.
_RAG_REQUEST_TIMEOUT = 10


def _fetch_rag_chunks(endpoint: str, query: str, resource_types: List[str]) -> List[dict]:
    """
    Call the context-augmentation REST endpoint and return the chunk list.

    Raises:
        requests.RequestException: on any network or HTTP error.
    """
    payload = {
        "question": query,
        "metadata": {"resource_types": resource_types},
    }
    response = requests.post(
        endpoint,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=_RAG_REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json().get("relevant_chunks", [])


def _policy_from_chunk(chunk: dict) -> Policy:
    """
    Construct a Policy object from a single RAG chunk dict.

    The policy scope is read from the chunk metadata (set by the RAG indexer
    when the policy was ingested).  If the metadata carries no scope, the
    scope defaults to an empty list — the auditor will apply the policy
    universally in that case.
    """
    metadata = chunk.get("metadata", {})
    content = chunk.get("document", "")
    return Policy(
        id=metadata.get("id", "unknown"),
        title=metadata.get("title", "Unknown Policy"),
        severity=metadata.get("severity", "MEDIUM"),
        description=_extract_description(content),
        scope=metadata.get("scope", []),
        requirements=content,
        examples_compliant=_extract_section(content, "Compliant Example"),
        examples_non_compliant=_extract_section(content, "Non-Compliant Example"),
        remediation=_extract_section(content, "Remediation"),
        file_path=metadata.get("file_path"),
        distance=chunk.get("distance"),
    )


def policy_analyst_node(state: AgentState) -> Dict[str, Any]:
    """
    Retrieve relevant policies based on parsed resources.

    In offline mode (USE_RAG=false or unset): loads all policies from disk.
    In RAG mode (USE_RAG=true): queries the context augmentation microservice
    for semantically relevant policy chunks; falls back to disk if the service
    returns no results.

    Args:
        state: Current agent state. Expects ``resource_types`` and
               ``parsed_resources`` to have been populated by the intake node.

    Returns:
        Dict with updated state fields:
            - retrieved_policies: List of serialised Policy dicts
            - resource_types: Unchanged pass-through from intake
            - current_node: "policy_analyst"
            - messages: Status messages
    """
    try:
        # Use resource_types already extracted by the intake node — avoids
        # duplicating extraction logic and ensures a single source of truth.
        resource_types: List[str] = state.get("resource_types") or []

        # If no resource types, nothing to retrieve policies for.
        if not resource_types:
            return {
                "retrieved_policies": [],
                "resource_types": [],
                "current_node": "policy_analyst",
                "messages": ["[POLICY_ANALYST] No resource types found — skipping policy retrieval"],
            }

        # Check if RAG is enabled. Default to OFF — enable explicitly with USE_RAG=true.
        use_rag = os.getenv("USE_RAG", "false").lower() == "true"

        if not use_rag:
            # Offline mode: load policies directly from disk — no microservices needed.
            # Respects POLICIES_DIR env var; falls back to built-in policies/ bundle.
            policies_dir = os.getenv("POLICIES_DIR")
            disk_policies = load_policies_from_dir(policies_dir)
        if not disk_policies:
            return {
                "retrieved_policies": [],
                "resource_types": resource_types,
                "current_node": "policy_analyst",
                "status": AuditStatus.ERROR,
                "error_message": (
                    "No policy files found. Add .md files to the policies/ directory "
                    "(or set POLICIES_DIR) before running an audit."
                ),
                "messages": [
                    "[POLICY_ANALYST] ERROR: No policies found on disk — cannot audit without policies.",
                ],
            }
        return {
            "retrieved_policies": [p.model_dump() for p in disk_policies],
            "resource_types": resource_types,
            "current_node": "policy_analyst",
            "messages": [
                f"[POLICY_ANALYST] RAG disabled — loaded {len(disk_policies)} policies from disk",
                f"[POLICY_ANALYST] Resource types: {', '.join(resource_types)}",
            ],
        }

        # RAG mode: build a semantic query and call the context augmentation service.
        query = " ".join([
            f"Policies for {', '.join(resource_types)} resources",
            "security compliance requirements",
            "database infrastructure policies",
        ])

        # URL-encode the app ID to prevent path traversal via a crafted env var.
        appid = quote(os.getenv("ADAG_APPID", "archapp"), safe="")
        base_url = os.getenv("RAG_CONTEXT_URL", "http://localhost:8000")
        endpoint = f"{base_url}/context-augment/{appid}"

        try:
            chunks = _fetch_rag_chunks(endpoint, query, resource_types)
        except Exception:
            # Log the full exception server-side; return a safe generic message.
            logger.exception("[POLICY_ANALYST] RAG API call failed")
            return {
                "retrieved_policies": [],
                "resource_types": resource_types,
                "current_node": "policy_analyst",
                "status": AuditStatus.ERROR,
                "error_message": "RAG API call failed. Check server logs for details.",
                "messages": ["[POLICY_ANALYST] ERROR: RAG API call failed — see server logs."],
            }

        # If the service returns no chunks, error out — do not silently fall back.
        if not chunks:
            return {
                "retrieved_policies": [],
                "resource_types": resource_types,
                "current_node": "policy_analyst",
                "status": AuditStatus.ERROR,
                "error_message": (
                    "RAG returned no policies for these resource types. "
                    "Ensure policies are indexed in the RAG pipeline before running an audit."
                ),
                "messages": [
                    "[POLICY_ANALYST] ERROR: RAG returned no policies — cannot audit without policies.",
                ],
            }

        retrieved_policies = [_policy_from_chunk(chunk) for chunk in chunks]
        return {
            "retrieved_policies": [p.model_dump() for p in retrieved_policies],
            "resource_types": resource_types,
            "current_node": "policy_analyst",
            "messages": [
                f"[POLICY_ANALYST] Retrieved {len(retrieved_policies)} relevant policies via RAG",
                f"[POLICY_ANALYST] Resource types: {', '.join(resource_types)}",
            ],
        }

    except Exception:
        logger.exception("[POLICY_ANALYST] Unexpected error during policy retrieval")
        return {
            "retrieved_policies": [],
            "resource_types": [],
            "current_node": "policy_analyst",
            "status": AuditStatus.ERROR,
            "error_message": "Policy analyst failed. Check server logs for details.",
            "messages": ["[POLICY_ANALYST] ERROR: Policy retrieval failed — see server logs."],
        }


def _extract_description(content: str) -> str:
    """
    Extract a brief description from policy markdown content.

    Returns the first non-header, non-bold line, capped at 200 characters.
    Falls back to the first 200 characters of content if no such line exists.
    """
    if not content:
        return ""
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("**"):
            return stripped[:200] + ("..." if len(stripped) > 200 else "")
    return content[:200] + ("..." if len(content) > 200 else "")


def _extract_section(content: str, section_name: str) -> str:
    """
    Extract a named section from policy markdown content.

    Sections are delimited by headings (lines starting with ``#``).
    Returns the section body as a stripped string, or ``""`` if not found.
    """
    if not content:
        return ""
    in_section = False
    section_lines: List[str] = []
    for line in content.split("\n"):
        if line.strip().startswith("#"):
            if section_name.lower() in line.lower():
                in_section = True
                continue
            if in_section:
                break  # next heading closes the current section
        if in_section:
            section_lines.append(line)
    return "\n".join(section_lines).strip()

