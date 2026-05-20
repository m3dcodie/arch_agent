"""
Auditor agent — checks parsed resources against retrieved policies.
"""

import json
import logging
import uuid
from typing import Dict, Any, List

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.language_models import BaseChatModel

from agents.prompts import build_dynamic_prompt
from core.state import AgentState
from core.llm_utils import invoke_structured
from models.violations import (
    Violation,
    ViolationList,
    AuditStatus,
    TerraformResource,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _format_resources_for_prompt(resources: list) -> str:
    """
    Serialise a list of TerraformResource objects or raw dicts to a JSON string
    suitable for embedding in an LLM prompt.
    """
    resources_data = []
    for resource in resources:
        if isinstance(resource, dict):
            resources_data.append(resource)
        else:
            resources_data.append(
                {
                    "resource_type": resource.resource_type,
                    "resource_name": resource.resource_name,
                    "attributes": resource.attributes,
                    "line_number": resource.line_number,
                }
            )
    return json.dumps(resources_data, indent=2)


def _assign_violation_ids(violations: List[Violation]) -> None:
    """
    Assign a unique, deterministic ID to any violation that has a placeholder ID.

    Uses a short UUID suffix to avoid collisions across concurrent audit runs.
    Mutates the list in place.
    """
    run_prefix = uuid.uuid4().hex[:6].upper()
    for i, violation in enumerate(violations, 1):
        if not violation.id or violation.id in ("unique-id", ""):
            violation.id = f"V{run_prefix}-{i:03d}"


# ---------------------------------------------------------------------------
# Agent node
# ---------------------------------------------------------------------------

def auditor_node(state: AgentState, llm: BaseChatModel) -> Dict[str, Any]:
    """
    Audit parsed resources against retrieved policies.

    Errors out if no policies are available — auditing without policies is not permitted.

    Args:
        state: Current agent state.
        llm:   Configured language model instance.

    Returns:
        Dict with updated state fields.
    """
    try:
        parsed_resources = state.get("parsed_resources", [])
        retrieved_policies = state.get("retrieved_policies", [])

        if not parsed_resources:
            return {
                "violations": [],
                "current_node": "auditor",
                "status": AuditStatus.PASSED,
                "messages": ["[AUDITOR] No resources found — audit passed"],
            }

        resources_json = _format_resources_for_prompt(parsed_resources)

        if not retrieved_policies:
            return {
                "violations": [],
                "current_node": "auditor",
                "status": AuditStatus.ERROR,
                "error_message": "No policies available — auditing requires explicit policies. Add policy files to the policies/ directory or configure RAG.",
                "messages": ["[AUDITOR] ERROR: No policies retrieved — cannot audit without policies."],
            }

        prompt_text = build_dynamic_prompt(retrieved_policies)
        message_prefix = f"[AUDITOR] Auditing against {len(retrieved_policies)} retrieved policies"

        prompt = ChatPromptTemplate.from_template(prompt_text)
        result = invoke_structured(
            llm, prompt, {"resources_json": resources_json}, ViolationList, agent_role="auditor"
        )

        violations = result.violations if result else []
        _assign_violation_ids(violations)

        if violations:
            status = AuditStatus.FAILED
            outcome_msg = f"[AUDITOR] Found {len(violations)} violation(s)"
        else:
            status = AuditStatus.PASSED
            outcome_msg = "[AUDITOR] All resources are compliant"

        return {
            "violations": [
                v.model_dump() if hasattr(v, "model_dump") else v for v in violations
            ],
            "current_node": "auditor",
            "status": status,
            "messages": [message_prefix, outcome_msg],
        }

    except Exception:
        # Log full traceback server-side; return a safe generic message.
        logger.exception("[AUDITOR] Unexpected error during audit")
        return {
            "violations": [],
            "current_node": "auditor",
            "status": AuditStatus.ERROR,
            "error_message": "Auditor failed. Check server logs for details.",
            "messages": ["[AUDITOR] ERROR: Audit failed — see server logs."],
        }
