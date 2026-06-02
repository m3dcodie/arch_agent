"""
Pydantic models for the Remediation Agent Designer.

A RemediationPatch is the direct equivalent of a GitHub Copilot inline
PR suggestion: a before/after code block scoped to a single violation.
The user decides whether to apply it — nothing is auto-written to disk.
"""
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class RemediationStatus(str, Enum):
    """Outcome of the remediation pass."""
    PROPOSED = "proposed"   # one or more patches generated
    SKIPPED = "skipped"     # no violations — nothing to fix
    ERROR = "error"         # LLM or structural failure


class RemediationPatch(BaseModel):
    """
    A single inline suggestion tied to one Violation.

    Mirrors the shape of a GitHub Copilot PR suggestion:
      - ``before_block``: the original HCL snippet (as found in the file)
      - ``after_block``:  the corrected HCL snippet (ready to copy-paste or apply)
    """
    violation_id: str = Field(
        description="ID of the Violation this patch resolves (e.g. 'VA3F2B-001')"
    )
    resource_type: str = Field(
        description="Terraform resource type targeted by this patch"
    )
    resource_name: str = Field(
        description="Terraform resource name/label targeted by this patch"
    )
    before_block: str = Field(
        description="Original HCL snippet showing the non-compliant configuration"
    )
    after_block: str = Field(
        description="Corrected HCL snippet that resolves the violation"
    )
    explanation: str = Field(
        description="One-sentence rationale: what changed and why it fixes the policy"
    )
    line_number: Optional[int] = Field(
        default=None,
        description="Line in the source file where the patch should be applied"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "violation_id": "VA3F2B-001",
                "resource_type": "aws_db_instance",
                "resource_name": "main",
                "before_block": 'deletion_protection = false',
                "after_block": 'deletion_protection = true',
                "explanation": "Set deletion_protection to true to satisfy the delete_protection policy.",
                "line_number": 14,
            }
        }


class RemediationReport(BaseModel):
    """Structured output of the remediation node — one patch per violation."""

    model_config = {
        "json_schema_extra": {
            "description": "Inline patch suggestions for all violations found during the audit"
        }
    }

    patches: List[RemediationPatch] = Field(
        default_factory=list,
        description="One patch per violation, in the same order as violations[]"
    )
    status: RemediationStatus = Field(
        default=RemediationStatus.PROPOSED,
        description="Overall outcome of the remediation pass"
    )
