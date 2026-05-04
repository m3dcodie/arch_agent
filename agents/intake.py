"""
Intake agent — validates and parses Terraform/IaC source into resource definitions.
"""

import logging
from typing import Dict, Any

from langchain_core.language_models import BaseChatModel

from core.hcl_parser import extract_provider_blocks, extract_resource_blocks
from core.state import AgentState
from models.violations import AuditStatus

logger = logging.getLogger(__name__)

# Hard upper bound on accepted IaC payload size (bytes).
# Prevents ReDoS and memory exhaustion from adversarially large inputs.
MAX_IAC_BYTES = 2 * 1024 * 1024  # 2 MB


def intake_node(state: AgentState, llm: BaseChatModel) -> Dict[str, Any]:
    """
    Validate and parse Terraform code; extract resources deterministically.

    The LLM is not used for parsing — regex extraction ensures attributes such
    as deletion_protection and storage_encrypted are never hallucinated or
    dropped.  The `llm` parameter is retained for interface uniformity across
    all agent nodes.

    All resources are extracted regardless of type; policy-based filtering is
    the responsibility of downstream pipeline stages (policy_analyst, auditor).

    Args:
        state: Current agent state.
        llm:   Language model instance (unused; present for interface compatibility).

    Returns:
        Dict with updated state fields.
    """
    try:
        iac_code = state["iac_code"]

        # --- Input validation ---
        if not isinstance(iac_code, str) or not iac_code.strip():
            return {
                "parsed_resources": [],
                "resource_types": [],
                "current_node": "intake",
                "status": AuditStatus.ERROR,
                "error_message": "iac_code must be a non-empty string.",
                "messages": ["[INTAKE] ERROR: iac_code must be a non-empty string."],
            }

        if len(iac_code.encode("utf-8")) > MAX_IAC_BYTES:
            return {
                "parsed_resources": [],
                "resource_types": [],
                "current_node": "intake",
                "status": AuditStatus.ERROR,
                "error_message": "iac_code exceeds the 2 MB size limit.",
                "messages": ["[INTAKE] ERROR: iac_code exceeds the 2 MB size limit."],
            }

        provider_resources = extract_provider_blocks(iac_code)
        resource_blocks = extract_resource_blocks(iac_code)
        all_resources = provider_resources + resource_blocks

        # Deduplicated list of resource types — consumed by policy_analyst (Phase 2 RAG).
        resource_types = list({r["resource_type"] for r in all_resources})

        return {
            "parsed_resources": all_resources,
            "resource_types": resource_types,
            "current_node": "intake",
            "status": AuditStatus.IN_PROGRESS,
            "messages": [
                f"[INTAKE] Parsed {len(all_resources)} resource(s) "
                f"({len(provider_resources)} provider block(s), "
                f"{len(resource_blocks)} resource block(s)) — deterministic parser"
            ],
        }

    except Exception:
        # Log the full traceback server-side; return a safe generic message to
        # the caller to avoid leaking filesystem paths or internal details.
        logger.exception("[INTAKE] Unexpected error during parsing")
        return {
            "parsed_resources": [],
            "resource_types": [],
            "current_node": "intake",
            "status": AuditStatus.ERROR,
            "error_message": "Intake parsing failed. Check server logs for details.",
            "messages": ["[INTAKE] ERROR: Parsing failed — see server logs."],
        }
