"""
Disk-based policy loader for offline/local mode.

Reads policy markdown files directly from the filesystem — no vector DB,
no microservices required. Intended for Mode 1 (local package) and Mode 2
(MCP server) where the full RAG pipeline is not available or needed.

Usage:
    from core.policy_loader import load_policies_from_dir
    policies = load_policies_from_dir()              # built-in policies
    policies = load_policies_from_dir("./my-rules")  # custom policies dir
"""
import logging
from pathlib import Path
from typing import List, Optional

from models.policy import Policy

logger = logging.getLogger(__name__)

# Built-in policies directory (sibling of this file's parent)
_BUILTIN_POLICIES_DIR = Path(__file__).parent.parent / "policies"


def load_policies_from_dir(policies_dir: Optional[str] = None) -> List[Policy]:
    """
    Load all policy markdown files from a directory into Policy objects.

    Works fully offline — no RAG microservices or ChromaDB needed.
    Policies are passed directly into the auditor prompt; with Claude Sonnet's
    200K-token context window, up to ~100 policy docs fit comfortably.

    Args:
        policies_dir: Path to directory containing .md policy files.
                      Defaults to the built-in policies/ directory.

    Returns:
        List of Policy objects parsed from the markdown files.
    """
    target_dir = Path(policies_dir) if policies_dir else _BUILTIN_POLICIES_DIR

    if not target_dir.exists():
        logger.warning(f"[POLICY_LOADER] Policies directory not found: {target_dir}")
        return []

    policy_files = sorted(target_dir.glob("*.md"))
    if not policy_files:
        logger.warning(f"[POLICY_LOADER] No .md files found in: {target_dir}")
        return []

    policies = []
    for md_file in policy_files:
        try:
            policy = _parse_policy_file(md_file)
            if policy:
                policies.append(policy)
                logger.debug(f"[POLICY_LOADER] Loaded: {policy.id} ({policy.severity})")
        except Exception as e:
            logger.warning(f"[POLICY_LOADER] Failed to parse {md_file.name}: {e}")

    logger.info(f"[POLICY_LOADER] Loaded {len(policies)} policies from {target_dir}")
    return policies


def _parse_policy_file(file_path: Path) -> Optional[Policy]:
    """Parse a single policy markdown file into a Policy object."""
    content = file_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    # Defaults derived from filename
    policy_id = file_path.stem
    title = policy_id.replace("_", " ").title()
    severity = "MEDIUM"
    scope: List[str] = []
    in_scope_section = False
    id_found = False

    for line in lines:
        stripped = line.strip()

        # Extract title from first H1
        if stripped.startswith("# ") and title == policy_id.replace("_", " ").title():
            title = stripped[2:].strip()

        # Extract policy ID from backtick-wrapped identifier
        elif "`" in stripped and not id_found:
            parts = stripped.split("`")
            if len(parts) >= 3:
                candidate = parts[1].strip()
                if "_" in candidate or (candidate.islower() and len(candidate) > 2):
                    policy_id = candidate
                    id_found = True

        # Extract severity
        elif "**HIGH**" in stripped:
            severity = "HIGH"
        elif "**MEDIUM**" in stripped:
            severity = "MEDIUM"
        elif "**LOW**" in stripped:
            severity = "LOW"

        # Extract scope section
        elif "## Scope" in stripped:
            in_scope_section = True
        elif in_scope_section:
            if stripped.startswith("##"):
                in_scope_section = False
            elif stripped.startswith("- `") and "`" in stripped:
                resource_type = stripped.split("`")[1]
                if resource_type:
                    scope.append(resource_type)

    return Policy(
        id=policy_id,
        title=title,
        severity=severity,
        description=_extract_description(content),
        scope=scope,
        requirements=content,
        examples_compliant=_extract_section(content, "Compliant Example"),
        examples_non_compliant=_extract_section(content, "Non-Compliant Example"),
        remediation=_extract_section(content, "Remediation"),
        file_path=str(file_path),
    )


def _extract_description(content: str) -> str:
    """Return the first non-heading, non-empty line as the description."""
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("**"):
            return stripped[:200] + ("..." if len(stripped) > 200 else "")
    return content[:200]


def _extract_section(content: str, section_name: str) -> str:
    """Extract the content of a named markdown section."""
    lines = content.split("\n")
    in_section = False
    collected: List[str] = []

    for line in lines:
        if section_name.lower() in line.lower() and line.strip().startswith("#"):
            in_section = True
            continue
        if in_section and line.strip().startswith("#"):
            break
        if in_section:
            collected.append(line)

    return "\n".join(collected).strip()
