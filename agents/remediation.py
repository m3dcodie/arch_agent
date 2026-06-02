"""
Remediation Agent — proposes inline patch suggestions for violations found by the Auditor.

Analogous to GitHub Copilot inline PR suggestions: each RemediationPatch contains a
``before_block`` (original code) and an ``after_block`` (suggested fix). Nothing is
written to disk. The user decides whether to apply a suggestion.

One LangGraph node. One LLM call. Skipped when there are no violations.
"""
import json
import logging
from typing import Dict, Any, List

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.language_models import BaseChatModel

from agents.prompts import build_remediation_prompt
from core.state import AgentState
from core.llm_utils import invoke_structured
from models.remediation import RemediationPatch, RemediationReport, RemediationStatus
from models.violations import Violation

logger = logging.getLogger(__name__)


def _violations_to_json(violations: list) -> str:
    """Serialise violations from state (may be dicts or Violation objects)."""
    out = []
    for v in violations:
        if isinstance(v, dict):
            out.append(v)
        else:
            out.append(v.model_dump())
    return json.dumps(out, indent=2)


def remediation_node(state: AgentState, llm: BaseChatModel) -> Dict[str, Any]:
    """
    Generate inline patch suggestions for every violation in state.

    Returns:
        Dict with ``remediation_patches`` and ``remediation_status`` state fields.
    """
    violations: list = state.get("violations", [])
    iac_code: str = state.get("iac_code", "")

    # --- Skip when nothing to fix ---
    if not violations:
        return {
            "remediation_patches": [],
            "remediation_status": RemediationStatus.SKIPPED,
            "current_node": "remediation",
            "messages": ["[REMEDIATION] No violations — skipping remediation pass"],
        }

    violations_json = _violations_to_json(violations)
    n = len(violations)

    try:
        prompt = ChatPromptTemplate.from_template(build_remediation_prompt())
        result: RemediationReport | None = invoke_structured(
            llm,
            prompt,
            {"iac_code": iac_code, "violations_json": violations_json},
            RemediationReport,
            agent_role="remediation",
        )

        patches: List[RemediationPatch] = result.patches if result else []

        logger.info(
            "[REMEDIATION] Generated %d patch suggestion(s) for %d violation(s)",
            len(patches),
            n,
        )

        return {
            "remediation_patches": [
                p.model_dump() if hasattr(p, "model_dump") else p for p in patches
            ],
            "remediation_status": RemediationStatus.PROPOSED,
            "current_node": "remediation",
            "messages": [
                f"[REMEDIATION] {len(patches)} inline suggestion(s) proposed for {n} violation(s)"
            ],
        }

    except Exception:
        logger.exception("[REMEDIATION] Unexpected error during patch generation")
        return {
            "remediation_patches": [],
            "remediation_status": RemediationStatus.ERROR,
            "current_node": "remediation",
            "messages": ["[REMEDIATION] ERROR: Patch generation failed — see server logs."],
        }
