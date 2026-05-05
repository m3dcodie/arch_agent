"""
Deterministic HCL/Terraform parser.

Pure parsing utilities — no LLM, no policy dependencies, no side effects.
Extracts provider and resource blocks from Terraform source text.

Limitations:
  - Only top-level scalar attributes are parsed (bool, int, float, quoted string).
  - Complex values (lists, maps, variable references, function calls, heredocs)
    are returned as raw strings. Callers must treat them as opaque unless they
    perform additional parsing.
  - This is a best-effort regex parser. For full fidelity, consider python-hcl2.
"""

import re
from typing import Any, Dict


def parse_hcl_value(raw: str) -> Any:
    """
    Best-effort conversion of a raw HCL scalar string to a Python type.

    Handles: booleans, integers, floats, single- and double-quoted strings.
    Complex HCL expressions (lists, maps, references, function calls) are
    returned as-is so callers can detect and handle them explicitly.
    """
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
    # Strip surrounding quotes (single or double)
    if (raw.startswith('"') and raw.endswith('"')) or (
        raw.startswith("'") and raw.endswith("'")
    ):
        return raw[1:-1]
    return raw


def extract_flat_attrs(body: str) -> Dict[str, Any]:
    """
    Extract top-level scalar key = value pairs from an HCL block body.

    Ignores nested blocks (tags {}, lifecycle {}, etc.) — only scalar
    assignments at the current brace depth are captured.

    Complex values (lists, maps, variable references, function calls) are
    returned as raw strings; callers that require structured access must
    inspect the raw string or use a full HCL parser.
    """
    attrs: Dict[str, Any] = {}
    # Match lines of the form:  key = <non-block-starting value>
    # A value starting with '{' opens a nested block and is excluded.
    for m in re.finditer(r"^\s*(\w+)\s*=\s*([^{\n][^\n]*)", body, re.MULTILINE):
        key = m.group(1)
        raw_val = m.group(2).split("#")[0].strip()  # strip trailing inline comments
        attrs[key] = parse_hcl_value(raw_val)
    return attrs


def extract_block_body(text: str, start: int) -> tuple[str, int]:
    """
    Given `text` and the index of the opening '{', find the matching '}'
    using brace depth tracking and return (body, index_after_closing_brace).

    Args:
        text:  Full source text.
        start: Index of the opening '{'.

    Returns:
        Tuple of (text between braces, index immediately after the closing '}').
        If no matching '}' is found, returns the remainder of the text.
    """
    depth = 0
    i = start
    while i < len(text):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i], i + 1
        i += 1
    # Unmatched opening brace — return whatever remains
    return text[start + 1 :], len(text)


def extract_provider_blocks(iac_code: str) -> list:
    """
    Extract all provider blocks from Terraform source text.

    Returns:
        List of dicts, each with keys:
          resource_type ("provider"), resource_name, attributes, line_number.
    """
    providers = []
    pattern = re.compile(r'provider\s+"(\w+)"\s*\{', re.DOTALL)
    for m in pattern.finditer(iac_code):
        provider_name = m.group(1)
        line_number = iac_code[: m.start()].count("\n") + 1
        body, _ = extract_block_body(iac_code, m.end() - 1)
        attrs = extract_flat_attrs(body)
        providers.append(
            {
                "resource_type": "provider",
                "resource_name": provider_name,
                "attributes": attrs,
                "line_number": line_number,
            }
        )
    return providers


def extract_resource_blocks(iac_code: str) -> list:
    """
    Extract all resource blocks from Terraform source text.

    Returns every ``resource "TYPE" "NAME" { ... }`` block found, regardless
    of resource type.  Policy-based filtering is the responsibility of
    downstream pipeline stages (policy_analyst, auditor), not the parser.

    Returns:
        List of dicts, each with keys:
          resource_type, resource_name, attributes, line_number.
    """
    resources = []
    pattern = re.compile(r'resource\s+"([\w]+)"\s+"([\w\-]+)"\s*\{', re.DOTALL)
    for m in pattern.finditer(iac_code):
        resource_type = m.group(1)
        resource_name = m.group(2)
        line_number = iac_code[: m.start()].count("\n") + 1
        body, _ = extract_block_body(iac_code, m.end() - 1)
        attrs = extract_flat_attrs(body)
        resources.append(
            {
                "resource_type": resource_type,
                "resource_name": resource_name,
                "attributes": attrs,
                "line_number": line_number,
            }
        )
    return resources
