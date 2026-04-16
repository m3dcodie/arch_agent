"""
Intake agent - Parses Terraform/IaC code and extracts resource definitions.
"""

import re
from typing import Dict, Any
from langchain_core.language_models import BaseChatModel

from core.state import AgentState
from models.violations import AuditStatus


_AUDITABLE_RESOURCE_TYPES = {
    "aws_db_instance",
    "aws_rds_cluster",
    "aws_db_cluster_instance",
    "aws_kms_key",
    "aws_s3_bucket",
    "aws_s3_bucket_public_access_block",
    "aws_s3_bucket_server_side_encryption_configuration",
    "provider",
}


def _parse_hcl_value(raw: str) -> Any:
    """Best-effort conversion of a raw HCL value string to a Python type."""
    raw = raw.strip()
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    # Strip surrounding quotes
    if (raw.startswith('"') and raw.endswith('"')) or (
        raw.startswith("'") and raw.endswith("'")
    ):
        return raw[1:-1]
    return raw


def _extract_flat_attrs(body: str) -> Dict[str, Any]:
    """
    Extract simple key = value / key = "value" pairs from an HCL block body.
    Ignores nested blocks (tags {}, rule {}, etc.) — only top-level scalars.
    """
    attrs: Dict[str, Any] = {}
    # Match lines like:  key = value  or  key = "value"
    # Exclude lines that start a sub-block (value ends with '{')
    for m in re.finditer(r"^\s*(\w+)\s*=\s*([^{\n][^\n]*)", body, re.MULTILINE):
        key = m.group(1)
        raw_val = m.group(2).split("#")[0].strip()  # strip inline comments
        attrs[key] = _parse_hcl_value(raw_val)
    return attrs


def _extract_block_body(text: str, start: int) -> tuple[str, int]:
    """
    Given `text` and the index of the opening '{', find the matching '}'
    and return (body_between_braces, index_after_closing_brace).
    Handles nested braces.
    """
    depth = 0
    i = start
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i], i + 1
        i += 1
    return text[start + 1 :], len(text)


def _extract_provider_blocks(iac_code: str) -> list:
    """Deterministically extract provider blocks from Terraform code."""
    providers = []
    pattern = re.compile(r'provider\s+"(\w+)"\s*\{', re.DOTALL)
    for m in pattern.finditer(iac_code):
        provider_name = m.group(1)
        line_number = iac_code[: m.start()].count("\n") + 1
        body, _ = _extract_block_body(iac_code, m.end() - 1)
        attrs = _extract_flat_attrs(body)
        providers.append(
            {
                "resource_type": "provider",
                "resource_name": provider_name,
                "attributes": attrs,
                "line_number": line_number,
            }
        )
    return providers


def _extract_resource_blocks(iac_code: str) -> list:
    """
    Deterministically extract auditable resource blocks from Terraform code.
    Returns a list of dicts matching TerraformResource structure.
    """
    resources = []
    # Match:  resource "TYPE" "NAME" {
    pattern = re.compile(r'resource\s+"([\w]+)"\s+"([\w\-]+)"\s*\{', re.DOTALL)
    for m in pattern.finditer(iac_code):
        resource_type = m.group(1)
        resource_name = m.group(2)
        if resource_type not in _AUDITABLE_RESOURCE_TYPES:
            continue
        line_number = iac_code[: m.start()].count("\n") + 1
        body, _ = _extract_block_body(iac_code, m.end() - 1)
        attrs = _extract_flat_attrs(body)
        resources.append(
            {
                "resource_type": resource_type,
                "resource_name": resource_name,
                "attributes": attrs,
                "line_number": line_number,
            }
        )
    return resources


def intake_node(state: AgentState, llm: BaseChatModel) -> Dict[str, Any]:
    """
    Parse Terraform code and extract auditable resources deterministically.
    The LLM is no longer used for parsing — regex/AST extraction ensures
    attributes like deletion_protection, storage_encrypted, etc. are never
    hallucinated or dropped.

    Args:
        state: Current agent state
        llm: Language model instance (kept for interface compatibility)

    Returns:
        Dict with updated state fields
    """
    try:
        iac_code = state["iac_code"]
        provider_resources = _extract_provider_blocks(iac_code)
        resource_blocks = _extract_resource_blocks(iac_code)
        all_resources = provider_resources + resource_blocks

        return {
            "parsed_resources": all_resources,
            "current_node": "intake",
            "status": AuditStatus.IN_PROGRESS,
            "messages": [
                f"[INTAKE] Parsed {len(all_resources)} resource(s) "
                f"({len(provider_resources)} provider block(s), "
                f"{len(resource_blocks)} resource block(s)) — deterministic parser"
            ],
        }

    except Exception as e:
        return {
            "parsed_resources": [],
            "current_node": "intake",
            "status": AuditStatus.ERROR,
            "error_message": f"Intake parsing failed: {str(e)}",
            "messages": [f"[INTAKE] ERROR: {str(e)}"],
        }
