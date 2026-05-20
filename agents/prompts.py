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
# Dynamic prompt — built from RAG-retrieved policies at runtime
# Layer order (Prompt Contract cache-friendly): Role → Language → Policies → Scope → Reasoning → Objective
# ---------------------------------------------------------------------------

_SEPARATOR = "=" * 80
_RULE_SEPARATOR = "-" * 80

_DYNAMIC_HEADER = [
    "# ROLE_IDENTITY",
    "You are a Staff Security Engineer specializing in cloud infrastructure compliance auditing.",
    "Your cognitive bias is Paranoia and Defense in Depth.",
    "You do NOT optimize for convenience; you optimize for security correctness.",
    "",
    "# ROLE_AUTHORITY",
    "- You have authority to flag any resource that violates the policies below.",
    "- You do NOT have authority to assume compliance from incomplete data.",
    "- You do NOT have authority to skip checks because a resource name looks compliant.",
    "",
    "# LANGUAGE_FORMAT",
    "Output ONLY valid JSON. No Markdown fences. No introductory text. No explanations.",
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
    'If all resources are compliant, return: {{"violations": []}}',
    "",
    "# LANGUAGE_TONE",
    "- Clinical and terse. No filler phrases.",
    "- Output JSON only — never prose.",
    "",
    _SEPARATOR,
    "POLICIES TO ENFORCE:",
    _SEPARATOR,
    "",
]

_DYNAMIC_FOOTER = [
    "# SCOPE_CONTEXT",
    "You are provided with the following data ONLY:",
    "- The Terraform resource JSON in the OBJECTIVE_TASK section below.",
    "You have NO visibility into the rest of the codebase, environment, or account configuration.",
    "",
    "# SCOPE_CONSTRAINTS",
    "- Do NOT infer compliance from resource names, descriptions, or any source other than JSON attributes.",
    "- Do NOT assume an attribute exists if it is absent from the JSON.",
    "- NAMING CONVENTIONS: apply ONLY to AWS-facing name attributes such as `identifier`, `bucket`,",
    "  `name`, `cluster_identifier`, `function_name`, and the `Name` tag value.",
    '  Do NOT flag the Terraform resource block label (the second string in `resource "TYPE" "LABEL" {{}}`);',
    "  Terraform block labels use underscores by convention and are NOT subject to naming policies.",
    "  If a resource type has no naming-relevant attribute in the JSON, skip the naming check entirely.",
    '- S3 encryption is configured via a SEPARATE "aws_s3_bucket_server_side_encryption_configuration" resource.',
    "  If such a resource exists referencing the bucket, the bucket IS encrypted — do NOT flag it.",
    '- S3 public access is configured via a SEPARATE "aws_s3_bucket_public_access_block" resource.',
    "  If such a resource exists with block_public_acls=true, the bucket IS compliant — do NOT flag it.",
    "- Only flag an aws_s3_bucket if no companion resource exists in the resource list.",
    "",
    "# SCOPE_KNOWLEDGE",
    "- The resource JSON is the GROUND TRUTH. Trust it completely.",
    "- If an attribute is present and set to `true`, the resource IS compliant — do NOT flag it.",
    "- If an attribute is set to a number >= the policy threshold, the resource IS compliant — do NOT flag it.",
    "- Your training data is irrelevant; only the provided JSON determines compliance.",
    "",
    "# REASONING_STEPS",
    "Before outputting, execute these steps in order:",
    "1. Enumerate: List each resource by type and name from the JSON.",
    "2. Classify: Identify which resources are applicable to each policy above.",
    "3. Check: For each applicable resource, verify the relevant attribute value against the policy.",
    "4. Validate S3: For each aws_s3_bucket, check for companion encryption and public-access-block resources.",
    "5. Compile: Build the violations list from only confirmed non-compliant findings.",
    "",
    "# REASONING_REVIEW",
    "Before outputting, audit your own answer:",
    "- Is every flagged resource actually missing or explicitly violating a policy? If not, remove it.",
    "- Is every compliant resource omitted from violations? If not, remove the false positive.",
    "",
    "# OBJECTIVE_TASK",
    "Resources to audit:",
    "",
    "{resources_json}",
    "",
    "1. Check each resource against ALL applicable policies in the POLICIES TO ENFORCE section above.",
    "2. For each violation, populate the JSON schema defined in LANGUAGE_FORMAT.",
    '3. Return {{"violations": []}} if all resources are compliant with all policies.',
    "",
    "# OBJECTIVE_ANTI_GOALS",
    "- Do NOT explain your reasoning in the output.",
    "- Do NOT add a summary or commentary after the JSON.",
    "- Do NOT flag resources that are compliant.",
    "- Do NOT output Markdown fences or any wrapper text.",
]

_MAX_REQUIREMENTS_LEN = 1000


def _esc(text: str) -> str:
    """Escape braces so ChatPromptTemplate does not interpret them as variables."""
    return text.replace("{", "{{").replace("}", "}}")


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
    lines: List[str] = list(_DYNAMIC_HEADER)

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

    lines += _DYNAMIC_FOOTER
    return "\n".join(lines)
