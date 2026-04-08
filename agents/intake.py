"""
Intake agent - Parses Terraform/IaC code and extracts resource definitions.
"""
import json
import re
from typing import Dict, Any, Type, TypeVar
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

from core.state import AgentState
from models.violations import TerraformResource, ResourceList, AuditStatus

T = TypeVar("T", bound=BaseModel)


def _invoke_structured(llm: BaseChatModel, prompt: ChatPromptTemplate, inputs: dict, schema: Type[T]) -> T:
    """
    Invoke the LLM and parse the result into a Pydantic model.

    Uses with_structured_output for providers that support tool/function calling
    (e.g. Bedrock). Falls back to plain invocation + JSON extraction for Ollama,
    which does not reliably support schema-enforced structured output.
    """
    try:
        from langchain_ollama import ChatOllama
        is_ollama = isinstance(llm, ChatOllama)
    except ImportError:
        is_ollama = False

    if is_ollama:
        # Plain invocation — strip <think> blocks and parse JSON from text
        chain = prompt | llm
        response = chain.invoke(inputs)
        raw = response.content if hasattr(response, "content") else str(response)
        # Remove reasoning blocks and markdown fences
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
        raw = re.sub(r"```(?:json)?", "", raw).strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON found in model output: {raw[:300]}")
        return schema(**json.loads(match.group()))
    else:
        chain = prompt | llm.with_structured_output(schema)
        return chain.invoke(inputs)


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

        # Invoke with provider-aware structured output
        result = _invoke_structured(llm, prompt, {"iac_code": state["iac_code"]}, ResourceList)
        
        # Extract resources — return as plain dicts so LangGraph's SQLite
        # checkpointer can serialize them with json.dumps (Pydantic objects are not
        # JSON-serializable by default in the checkpoint metadata path).
        parsed_resources = [r.model_dump() for r in (result.resources if result else [])]
        
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
