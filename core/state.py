"""
LangGraph state schema for the ADAG system.
"""
from typing import Annotated, List
from typing_extensions import TypedDict
import operator

from models.violations import Violation, TerraformResource, AuditStatus
from models.policy import Policy
from models.remediation import RemediationPatch, RemediationStatus


class AgentState(TypedDict):
    """
    State object for the LangGraph workflow.
    
    This state is passed between all nodes in the graph and maintains
    the complete context of the audit process.
    """
    
    # Append-only message history for debugging and logging
    messages: Annotated[list, operator.add]
    
    # Input data
    iac_code: str  # Raw Terraform/IaC code content
    file_path: str  # Path to the source file being audited
    
    # Processing data
    parsed_resources: List[TerraformResource]  # Extracted resource definitions
    retrieved_policies: List[Policy]  # Policies retrieved from RAG (Phase 2)
    resource_types: List[str]  # Resource types extracted for policy retrieval (Phase 2)
    
    # Output data
    violations: List[Violation]  # Found policy violations
    status: AuditStatus  # Current audit status

    # Remediation output
    remediation_patches: List[RemediationPatch]  # Inline patch suggestions (one per violation)
    remediation_status: RemediationStatus  # Outcome of the remediation pass

    # Metadata
    current_node: str  # Current node being executed (for debugging)
    error_message: str  # Error message if status is ERROR
