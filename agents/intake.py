"""
Intake agent - Parses Terraform/IaC code and extracts resource definitions.
"""
import json
from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.language_models import BaseChatModel

from core.state import AgentState
from models.violations import TerraformResource, ResourceList, AuditStatus


INTAKE_PROMPT = """You are a Terraform code parser. Your task is to extract all database-related resources from the provided Terraform code.

Focus on these resource types:
- aws_db_instance
- aws_rds_cluster
- aws_db_cluster_instance

For each resource, extract:
1. resource_type: The Terraform resource type
2. resource_name: The resource identifier/name
3. attributes: All configuration attributes as a dictionary
4. line_number: Approximate line number (if determinable)

Terraform Code:
```
{iac_code}
```

Return ONLY a valid JSON object with this structure:
{{
  "resources": [
    {{
      "resource_type": "aws_db_instance",
      "resource_name": "example",
      "attributes": {{"key": "value"}},
      "line_number": 10
    }}
  ]
}}

If no database resources are found, return: {{"resources": []}}
"""


def intake_node(state: AgentState, llm: BaseChatModel) -> Dict[str, Any]:
    """
    Parse Terraform code and extract database resources.
    
    Args:
        state: Current agent state
        llm: Language model instance
        
    Returns:
        Dict with updated state fields
    """
    try:
        # Create prompt
        prompt = ChatPromptTemplate.from_template(INTAKE_PROMPT)
        
        # Use structured output with Pydantic model
        structured_llm = llm.with_structured_output(ResourceList)
        
        # Create chain
        chain = prompt | structured_llm
        
        # Invoke the chain
        result = chain.invoke({"iac_code": state["iac_code"]})
        
        # Extract resources
        parsed_resources = result.resources if result else []
        
        return {
            "parsed_resources": parsed_resources,
            "current_node": "intake",
            "status": AuditStatus.IN_PROGRESS,
            "messages": [f"[INTAKE] Parsed {len(parsed_resources)} database resources"]
        }
        
    except Exception as e:
        return {
            "parsed_resources": [],
            "current_node": "intake",
            "status": AuditStatus.ERROR,
            "error_message": f"Intake parsing failed: {str(e)}",
            "messages": [f"[INTAKE] ERROR: {str(e)}"]
        }
