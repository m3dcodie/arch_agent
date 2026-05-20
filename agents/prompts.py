"""
Prompt templates for the ADAG auditor agent.

All user-visible LLM prompt text lives here so that prompt engineering
changes do not require touching agent logic.

Brace-escaping convention
-------------------------
ChatPromptTemplate interprets ``{name}`` as a template variable.  Any literal
brace that must survive rendering must be doubled: ``{{`` → ``{``, ``}}`` → ``}``.
Every prompt in this module follows that convention.  The only *real* template
variable is ``{resources_json}``.

Prompt Contract compliance
--------------------------
The dynamic prompt follows the 5-layer Prompt Contract architecture in cache-friendly
order: Role → Language → Policies → Scope → Reasoning → Objective.
See: https://github.com/m3dcodie/prompt-contract/
"""

from __future__ import annotations

from typing import List, Union

from models.policy import Policy


# ---------------------------------------------------------------------------
# Dynamic prompt — built from loaded policies at runtime
# Layer order (Prompt Contract cache-friendly): Role → Language → Policies → Scope → Reasoning → Objective
# ---------------------------------------------------------------------------

_SEPARATOR = "=" * 80
_RULE_SEPARATOR = "-" * 80

_DYNAMIC_HEADER = [
    "# ROLE",
    "You are a cloud infrastructure compliance auditor. Flag only confirmed violations",
    "based strictly on JSON attribute values — never infer compliance from resource",
    "names, block labels, or absent attributes.",
    "",
    "# OUTPUT FORMAT",
    "Output ONLY valid JSON — no markdown, no prose, no explanations.",
    "{{",
    '  "violations": [',
    "    {{",
    '      "id": "unique-id",',
    '      "resource_type": "aws_db_instance",',
    '      "resource_name": "resource_name",',
    '      "severity": "HIGH",',
    '      "policy_ref": "policy_id_from_above",',
    '      "description": "Clear description of the violation",',
    '      "line_number": 10,',
    '      "remediation_hint": "How to fix this violation"',
    "    }}",
    "  ]",
    "}}",
    'If all resources are compliant: {{"violations": []}}',
    "",
    "# VERIFICATION GATE",
    "Before adding ANY violation, confirm both conditions are true:",
    "  1. The specific attribute referenced by the policy EXISTS in the resource JSON.",
    "  2. Its value EXPLICITLY fails the policy rule (wrong value or absent).",
    "If either condition is false, do NOT add the violation — return nothing for that resource.",
    "",
    _SEPARATOR,
    "POLICIES TO ENFORCE:",
    _SEPARATOR,
    "",
]

_STATIC_FOOTER = [
    "# CONSTRAINTS",
    "- Naming policies apply ONLY to AWS-facing attributes (`identifier`, `bucket`, `name`,",
    "  `cluster_identifier`, `function_name`, `Name` tag). Terraform block labels are NOT subject",
    "  to naming policies and must never be flagged.",
    "- A missing or absent attribute means the requirement is NOT met — treat absence as non-compliant.",
    "- If an attribute is PRESENT and its value satisfies the policy, the resource IS compliant — do NOT flag it.",
    "- Do NOT flag a resource for a policy whose required attribute is present and correct in the JSON.",
]

_DYNAMIC_FOOTER = _STATIC_FOOTER + [
    "",
    "# TASK",
    "Audit these Terraform resources against ALL policies above:",
    "",
    "{resources_json}",
    "",
    'Return {{"violations": []}} if all resources are compliant.',
]

# Human message for the cached prompt path — plain f-string, no brace-escaping.
TASK_HUMAN_TEMPLATE = (
    "# TASK\n"
    "Audit these Terraform resources against ALL policies above:\n\n"
    "{resources_json}\n\n"
    'Return {{"violations": []}} if all resources are compliant.'
)

_MAX_REQUIREMENTS_LEN = 1000


def _esc(text: str) -> str:
    """Escape braces so ChatPromptTemplate does not interpret them as variables."""
    return text.replace("{", "{{").replace("}", "}}")


def _build_policy_lines(policies: List[Union[Policy, dict]]) -> List[str]:
    """Return the formatted policy section lines shared by both prompt builders."""
    lines: List[str] = []
    for i, policy in enumerate(policies, 1):
        if isinstance(policy, dict):
            title        = policy.get("title", "Unknown")
            pol_id       = policy.get("id", "unknown")
            severity     = policy.get("severity", "MEDIUM")
            description  = policy.get("description", "")
            requirements = policy.get("requirements", "")
            remediation  = policy.get("remediation", "")
        else:
            title        = policy.title
            pol_id       = policy.id
            severity     = policy.severity
            description  = policy.description
            requirements = policy.requirements
            remediation  = getattr(policy, "remediation", "")

        requirements = requirements[:_MAX_REQUIREMENTS_LEN]

        lines += [
            f"### Policy {i}: {title}",
            f"**Policy ID:** `{pol_id}`",
            f"**Severity:** {severity}",
            f"**Description:** {_esc(description)}",
            "",
            f"**Requirements:**\n{_esc(requirements)}",
            "",
        ]
        if remediation:
            lines.append(f"**Remediation:** {_esc(remediation)}")
            lines.append("")

        lines.append(_RULE_SEPARATOR)
        lines.append("")
    return lines


def build_system_prompt(policies: List[Union[Policy, dict]]) -> str:
    """
    Build the static system prompt text from a list of policies.

    Contains: Role + Output Format + Policies + Constraints.
    Does NOT include the dynamic task/resources section.

    Used by the Anthropic prompt-caching path in ``auditor_node`` — this text
    is placed in a ``SystemMessage`` with ``cache_control: ephemeral`` so the
    model can reuse the KV cache across repeated audits of different resources
    against the same policy set.

    Args:
        policies: Policy objects or plain dicts (from LangGraph checkpoints).

    Returns:
        Plain string (no template variables).
    """
    lines: List[str] = list(_DYNAMIC_HEADER) + _build_policy_lines(policies) + _STATIC_FOOTER
    return "\n".join(lines)


def build_dynamic_prompt(policies: List[Union[Policy, dict]]) -> str:
    """
    Build an audit prompt string from a list of retrieved policies.

    The returned string contains exactly one real template variable,
    ``{resources_json}``, which ChatPromptTemplate will fill at invoke time.

    Args:
        policies: Policy objects or plain dicts (from LangGraph checkpoints).

    Returns:
        Prompt string ready to pass to ``ChatPromptTemplate.from_template``.
    """
    lines: List[str] = list(_DYNAMIC_HEADER) + _build_policy_lines(policies) + _DYNAMIC_FOOTER
    return "\n".join(lines)
