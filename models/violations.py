"""
Pydantic models for violations and audit results.
"""
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field


class Severity(str, Enum):
    """Violation severity levels"""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class Violation(BaseModel):
    """Represents a single policy violation"""
    
    id: str = Field(
        description="Unique identifier for this violation"
    )
    resource_type: str = Field(
        description="Type of resource (e.g., 'aws_db_instance')"
    )
    resource_name: str = Field(
        description="Name of the resource in the IaC code"
    )
    severity: Severity = Field(
        description="Severity level of the violation"
    )
    policy_ref: str = Field(
        description="Reference to the policy that was violated"
    )
    description: str = Field(
        description="Human-readable description of the violation"
    )
    line_number: Optional[int] = Field(
        default=None,
        description="Line number in the source file where violation occurs"
    )
    remediation_hint: Optional[str] = Field(
        default=None,
        description="Suggestion on how to fix the violation"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "V001",
                "resource_type": "aws_db_instance",
                "resource_name": "main",
                "severity": "HIGH",
                "policy_ref": "delete_protection",
                "description": "Database instance does not have deletion protection enabled",
                "line_number": 10,
                "remediation_hint": "Add 'deletion_protection = true' to the resource"
            }
        }


class ViolationList(BaseModel):
    """List of violations returned by auditor"""
    
    model_config = {"json_schema_extra": {"description": "List of policy violations found during audit"}}
    
    violations: List[Violation] = Field(
        default_factory=list,
        description="List of policy violations found"
    )


class TerraformResource(BaseModel):
    """Represents a parsed Terraform resource"""
    
    resource_type: str = Field(
        description="Terraform resource type (e.g., 'aws_db_instance')"
    )
    resource_name: str = Field(
        description="Resource name/identifier"
    )
    attributes: dict = Field(
        default_factory=dict,
        description="Resource attributes and their values"
    )
    line_number: Optional[int] = Field(
        default=None,
        description="Starting line number in source file"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "resource_type": "aws_db_instance",
                "resource_name": "main",
                "attributes": {
                    "identifier": "mydb",
                    "engine": "postgres",
                    "deletion_protection": True
                },
                "line_number": 10
            }
        }


class ResourceList(BaseModel):
    """List of parsed Terraform resources"""
    
    model_config = {"json_schema_extra": {"description": "List of parsed Terraform resources from IaC code"}}
    
    resources: List[TerraformResource] = Field(
        default_factory=list,
        description="List of parsed resources"
    )


class AuditStatus(str, Enum):
    """Status of the audit process"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


class AuditResult(BaseModel):
    """Final audit result"""

    status: AuditStatus = Field(
        description="Overall audit status"
    )
    file_path: str = Field(
        description="Path to the audited file"
    )
    total_resources: int = Field(
        default=0,
        description="Total number of resources analyzed"
    )
    violations: List[Violation] = Field(
        default_factory=list,
        description="List of violations found"
    )
    summary: str = Field(
        default="",
        description="Human-readable summary of the audit"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error detail when status is ERROR"
    )
    
    @property
    def has_violations(self) -> bool:
        """Check if there are any violations"""
        return len(self.violations) > 0
    
    @property
    def high_severity_count(self) -> int:
        """Count of high severity violations"""
        return sum(1 for v in self.violations if v.severity == Severity.HIGH)
    
    @property
    def medium_severity_count(self) -> int:
        """Count of medium severity violations"""
        return sum(1 for v in self.violations if v.severity == Severity.MEDIUM)
    
    @property
    def low_severity_count(self) -> int:
        """Count of low severity violations"""
        return sum(1 for v in self.violations if v.severity == Severity.LOW)

    def to_json(self) -> dict:
        """Serialise the result to a plain dictionary (JSON-friendly)."""
        out = {
            "status": self.status.value,
            "file_path": self.file_path,
            "total_resources": self.total_resources,
            "summary": self.summary,
            "violation_counts": {
                "total": len(self.violations),
                "high": self.high_severity_count,
                "medium": self.medium_severity_count,
                "low": self.low_severity_count,
            },
            "violations": [
                {
                    "id": v.id,
                    "resource_type": v.resource_type,
                    "resource_name": v.resource_name,
                    "severity": v.severity.value,
                    "policy_ref": v.policy_ref,
                    "description": v.description,
                    "line_number": v.line_number,
                    "remediation_hint": v.remediation_hint,
                }
                for v in self.violations
            ],
        }
        if self.error_message:
            out["error_message"] = self.error_message
        return out

    def to_sarif(self) -> dict:
        """
        Serialise the result to SARIF 2.1.0 format.

        Compatible with GitHub Advanced Security code scanning upload:
            github/codeql-action/upload-sarif
        """
        _level_map = {
            Severity.HIGH: "error",
            Severity.MEDIUM: "warning",
            Severity.LOW: "note",
            Severity.INFO: "note",
        }

        rules = [
            {
                "id": v.policy_ref,
                "name": v.policy_ref.replace("_", " ").title(),
                "shortDescription": {"text": v.description},
                "helpUri": "https://github.com/your-org/adag/blob/main/policies/"
                           + v.policy_ref + ".md",
                "defaultConfiguration": {"level": _level_map.get(v.severity, "warning")},
            }
            for v in self.violations
        ]

        results = [
            {
                "ruleId": v.policy_ref,
                "level": _level_map.get(v.severity, "warning"),
                "message": {"text": v.description
                            + (f" Fix: {v.remediation_hint}" if v.remediation_hint else "")},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {
                                "uri": self.file_path,
                                "uriBaseId": "%SRCROOT%",
                            },
                            "region": {"startLine": v.line_number or 1},
                        }
                    }
                ],
            }
            for v in self.violations
        ]

        return {
            "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "ADAG",
                            "version": "0.1.0",
                            "informationUri": "https://github.com/your-org/adag",
                            "rules": rules,
                        }
                    },
                    "results": results,
                }
            ],
        }
