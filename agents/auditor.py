"""
Auditor agent - Checks for deletion protection policy compliance.
"""
import uuid
from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.language_models import BaseChatModel

from core.state import AgentState
from models.violations import Violation, ViolationList, Severity, AuditStatus, TerraformResource


AUDITOR_PROMPT = """You are a security auditor specializing in database infrastructure compliance.

Your task is to check if database resources have deletion protection enabled.

POLICY: All production database instances MUST have deletion_protection = true

Resources to audit:
{resources_json}

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

Be strict: if deletion_protection is missing or set to false, it's a HIGH severity violation.
"""


def auditor_node(state: AgentState, llm: BaseChatModel) -> Dict[str, Any]:
    """
    Audit parsed resources for deletion protection compliance.
    
    Args:
        state: Current agent state
        llm: Language model instance
        
    Returns:
        Dict with updated state fields
    """
    try:
        parsed_resources = state.get("parsed_resources", [])
        
        # If no resources to audit, pass the audit
        if not parsed_resources:
            return {
                "violations": [],
                "current_node": "auditor",
                "status": AuditStatus.PASSED,
                "messages": ["[AUDITOR] No database resources found - audit passed"]
            }
        
        # Convert resources to JSON for the prompt
        resources_json = _format_resources_for_prompt(parsed_resources)
        
        # Create prompt
        prompt = ChatPromptTemplate.from_template(AUDITOR_PROMPT)
        
        # Use structured output with Pydantic model
        structured_llm = llm.with_structured_output(ViolationList)
        
        # Create chain
        chain = prompt | structured_llm
        
        # Invoke the chain
        result = chain.invoke({"resources_json": resources_json})
        
        # Extract violations
        violations = result.violations if result else []
        
        # Ensure each violation has a unique ID
        for i, violation in enumerate(violations):
            if not violation.id or violation.id == "unique-id":
                violation.id = f"V{str(uuid.uuid4())[:8]}"
        
        # Determine status
        if violations:
            status = AuditStatus.FAILED
            message = f"[AUDITOR] Found {len(violations)} violation(s)"
        else:
            status = AuditStatus.PASSED
            message = "[AUDITOR] All resources are compliant"
        
        return {
            "violations": violations,
            "current_node": "auditor",
            "status": status,
            "messages": [message]
        }
        
    except Exception as e:
        return {
            "violations": [],
            "current_node": "auditor",
            "status": AuditStatus.ERROR,
            "error_message": f"Auditor failed: {str(e)}",
            "messages": [f"[AUDITOR] ERROR: {str(e)}"]
        }


def _format_resources_for_prompt(resources: List[TerraformResource]) -> str:
    """Format resources as JSON string for the prompt"""
    resources_data = []
    for resource in resources:
        resources_data.append({
            "resource_type": resource.resource_type,
            "resource_name": resource.resource_name,
            "attributes": resource.attributes,
            "line_number": resource.line_number
        })
    
    import json
    return json.dumps(resources_data, indent=2)
