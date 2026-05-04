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
"""

from __future__ import annotations

from typing import List, Union

from models.policy import Policy


# ---------------------------------------------------------------------------
# Fallback prompt — used when no policies were retrieved from the RAG pipeline
# ---------------------------------------------------------------------------

FALLBACK_AUDITOR_PROMPT = """\
You are a security auditor specializing in database infrastructure compliance.

Your task is to check if database resources have deletion protection enabled.

POLICY: All production database instances MUST have deletion_protection = true

Resources to audit:
{resources_json}

CRITICAL RULES — READ BEFORE AUDITING:
1. The resource JSON above is the GROUND TRUTH. Trust it completely.
2. If deletion_protection is present and set to `true`, the resource IS compliant — do NOT flag it.
3. ONLY flag a resource if deletion_protection is explicitly `false` or completely absent.
4. Do NOT infer anything from resource names, descriptions, or any other source.

IMPORTANT S3 RULES:
- S3 encryption is configured via a SEPARATE "aws_s3_bucket_server_side_encryption_configuration" resource.
  If such a resource exists referencing the bucket, the bucket IS encrypted — do NOT flag it.
- S3 public access is configured via a SEPARATE "aws_s3_bucket_public_access_block" resource.
  If such a resource exists with block_public_acls=true, the bucket IS compliant — do NOT flag it.
- Only flag an aws_s3_bucket if no companion encryption/public-access-block resource exists in the list above.

For each resource, check if:
1. The resource is a database (aws_db_instance, aws_rds_cluster, etc.)
2. The "deletion_protection" attribute exists
3. The "deletion_protection" attribute is set to true

For any violations found, return them in this format:
{{
  "violations": [
    {{
      "id": "unique-id",
      "resource_type": "aws_db_instance",
      "resource_name": "resource_name",
      "severity": "HIGH",
      "policy_ref": "delete_protection",
      "description": "Clear description of the violation",
      "line_number": 10,
      "remediation_hint": "Add 'deletion_protection = true' to the resource block"
    }}
  ]
}}

If all resources are compliant, return: {{"violations": []}}

Be strict: if deletion_protection is missing or set to false, it is a HIGH severity violation.\
"""


# ---------------------------------------------------------------------------
# Dynamic prompt — built from RAG-retrieved policies at runtime
# ---------------------------------------------------------------------------

_SEPARATOR = "=" * 80
_RULE_SEPARATOR = "-" * 80

_DYNAMIC_HEADER = [
    "You are a security auditor specializing in infrastructure compliance.",
    "",
    "Your task is to audit the provided Terraform resources against the following policies.",
    "",
    _SEPARATOR,
    "POLICIES TO ENFORCE:",
    _SEPARATOR,
    "",
]

_DYNAMIC_FOOTER = [
    _SEPARATOR,
    "RESOURCES TO AUDIT:",
    _SEPARATOR,
    "",
    "{resources_json}",
    "",
    "CRITICAL RULES — READ BEFORE AUDITING:",
    "1. The resource JSON above is the GROUND TRUTH. Trust it completely.",
    "2. If an attribute is present and set to `true`, the resource IS compliant — do NOT flag it.",
    "3. If an attribute is present and set to a number >= threshold, the resource IS compliant — do NOT flag it.",
    "4. ONLY flag a resource if the attribute is EXPLICITLY non-compliant OR completely absent.",
    "5. Do NOT infer or assume missing attributes from resource names or descriptions.",
    "6. NAMING CONVENTIONS: apply ONLY to AWS-facing name attributes such as `identifier`, `bucket`,",
    "   `name`, `cluster_identifier`, `function_name`, and the `Name` tag value.",
    '   Do NOT flag the Terraform resource block label (the second string in `resource "TYPE" "LABEL" {{}}`);',
    "   Terraform block labels use underscores by convention and are NOT subject to naming policies.",
    "   If a resource type has no naming-relevant attribute in the JSON, skip the naming check entirely.",
    "",
    "IMPORTANT S3 RULES:",
    '- S3 encryption is configured via a SEPARATE "aws_s3_bucket_server_side_encryption_configuration" resource.',
    "  If such a resource exists referencing the bucket, the bucket IS encrypted — do NOT flag it.",
    '- S3 public access is configured via a SEPARATE "aws_s3_bucket_public_access_block" resource.',
    "  If such a resource exists with block_public_acls=true, the bucket IS compliant — do NOT flag it.",
    "- Only flag an aws_s3_bucket if no companion resource exists in the resource list above.",
    "",
    "INSTRUCTIONS:",
    "1. Check each resource against ALL applicable policies above.",
    "2. For each violation, identify the policy_ref, resource, severity, description, and remediation.",
    "",
    "Return violations in this JSON format:",
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
    "",
    'If all resources are compliant with all policies, return: {{"violations": []}}',
    "",
    "Be thorough: check each resource against each applicable policy.",
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
