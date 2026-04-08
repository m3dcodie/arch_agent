"""
Auditor agent - Checks resources against retrieved policies (Phase 2: RAG-enabled).
"""
import json
import re
import uuid
from typing import Dict, Any, List, Type, TypeVar
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

from core.state import AgentState
from models.violations import Violation, ViolationList, Severity, AuditStatus, TerraformResource
from models.policy import Policy

T = TypeVar("T", bound=BaseModel)


def _invoke_structured(llm: BaseChatModel, prompt: ChatPromptTemplate, inputs: dict, schema: Type[T]) -> T:
    """
    Invoke the LLM and parse the result into a Pydantic model.

    Tries with_structured_output first; if the provider doesn't support it
    (e.g. Ollama, or HF router models), falls back to plain invoke + JSON extraction.
    """
    def _plain_invoke():
        chain = prompt | llm
        response = chain.invoke(inputs)
        raw = response.content if hasattr(response, "content") else str(response)
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
        raw = re.sub(r"```(?:json)?", "", raw).strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON found in model output: {raw[:300]}")
        return schema(**json.loads(match.group()))

    # Try structured output first; fall back on any API/tool-call error
    try:
        chain = prompt | llm.with_structured_output(schema)
        return chain.invoke(inputs)
    except Exception:
        return _plain_invoke()


# Fallback prompt for when RAG is disabled or no policies retrieved
FALLBACK_AUDITOR_PROMPT = """You are a security auditor specializing in database infrastructure compliance.

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
    Audit parsed resources against retrieved policies (Phase 2: RAG-enabled).
    
    This agent now uses policies retrieved by the policy_analyst node to
    perform dynamic, multi-policy auditing instead of hardcoded rules.
    
    Args:
        state: Current agent state
        llm: Language model instance
        
    Returns:
        Dict with updated state fields
    """
    try:
        parsed_resources = state.get("parsed_resources", [])
        retrieved_policies = state.get("retrieved_policies", [])
        
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
        
        # Build prompt based on whether we have retrieved policies
        if retrieved_policies:
            # Phase 2: Dynamic prompt from retrieved policies
            prompt_text = _build_dynamic_prompt(parsed_resources, retrieved_policies)
            message_prefix = f"[AUDITOR] Auditing against {len(retrieved_policies)} retrieved policies"
        else:
            # Fallback: Use hardcoded prompt — pass raw template (with {{ }} escapes)
            # directly to ChatPromptTemplate; don't pre-render via .format()
            prompt_text = FALLBACK_AUDITOR_PROMPT
            message_prefix = "[AUDITOR] Using fallback policy (RAG disabled or no policies found)"
        
        # Create prompt
        prompt = ChatPromptTemplate.from_template(prompt_text)

        # Invoke with provider-aware structured output
        result = _invoke_structured(llm, prompt, {"resources_json": resources_json}, ViolationList)
        
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
            "violations": [v.model_dump() if hasattr(v, "model_dump") else v for v in violations],
            "current_node": "auditor",
            "status": status,
            "messages": [message_prefix, message]
        }
        
    except Exception as e:
        return {
            "violations": [],
            "current_node": "auditor",
            "status": AuditStatus.ERROR,
            "error_message": f"Auditor failed: {str(e)}",
            "messages": [f"[AUDITOR] ERROR: {str(e)}"]
        }


def _build_dynamic_prompt(resources: List[TerraformResource], policies: List[Policy]) -> str:
    """
    Build a dynamic audit prompt from retrieved policies.
    
    Args:
        resources: List of parsed Terraform resources
        policies: List of retrieved Policy objects
        
    Returns:
        Formatted prompt string with policies and resources
    """
    prompt = """You are a security auditor specializing in infrastructure compliance.

Your task is to audit the provided Terraform resources against the following policies.

"""
    
    # Add each policy to the prompt
    prompt += "=" * 80 + "\n"
    prompt += "POLICIES TO ENFORCE:\n"
    prompt += "=" * 80 + "\n\n"
    
    for i, policy in enumerate(policies, 1):
        # Policy may be a dict (serialized for checkpoint) or a Pydantic object
        if isinstance(policy, dict):
            title = policy.get("title", "Unknown")
            pol_id = policy.get("id", "unknown")
            severity = policy.get("severity", "MEDIUM")
            description = policy.get("description", "")
            requirements = policy.get("requirements", "")
            remediation = policy.get("remediation", "")
        else:
            title = policy.title
            pol_id = policy.id
            severity = policy.severity
            description = policy.description
            requirements = policy.requirements
            remediation = policy.remediation

        # Escape braces in policy content so ChatPromptTemplate doesn't treat
        # {something} in policy text as template variables.
        description = description.replace("{", "{{").replace("}", "}}")
        requirements = requirements.replace("{", "{{").replace("}", "}}")
        if remediation:
            remediation = remediation.replace("{", "{{").replace("}", "}}")

        prompt += f"### Policy {i}: {title}\n"
        prompt += f"**Policy ID:** `{pol_id}`\n"
        prompt += f"**Severity:** {severity}\n"
        prompt += f"**Description:** {description}\n\n"

        # Include requirements (truncated if too long)
        requirements = requirements[:1000] if len(requirements) > 1000 else requirements
        prompt += f"**Requirements:**\n{requirements}\n\n"

        if remediation:
            prompt += f"**Remediation:** {remediation}\n\n"

        prompt += "-" * 80 + "\n\n"
    
    # Add resources section
    prompt += "=" * 80 + "\n"
    prompt += "RESOURCES TO AUDIT:\n"
    prompt += "=" * 80 + "\n\n"
    prompt += "{resources_json}\n\n"
    
    # Add instructions
    prompt += """
INSTRUCTIONS:
1. Check each resource against ALL applicable policies above
2. For each violation found, identify:
   - Which policy was violated (use the policy_ref field with the Policy ID)
   - The specific resource and attribute causing the violation
   - The severity level from the policy
   - A clear description of what's wrong
   - A remediation hint on how to fix it

Return violations in this JSON format:
{{
  "violations": [
    {{
      "id": "unique-id",
      "resource_type": "aws_db_instance",
      "resource_name": "resource_name",
      "severity": "HIGH",
      "policy_ref": "policy_id_from_above",
      "description": "Clear description of the violation",
      "line_number": 10,
      "remediation_hint": "How to fix this violation"
    }}
  ]
}}

If all resources are compliant with all policies, return: {{"violations": []}}

Be thorough: check each resource against each applicable policy.
"""
    
    return prompt


def _format_resources_for_prompt(resources: List[TerraformResource]) -> str:
    """Format resources as JSON string for the prompt.

    Accepts either TerraformResource objects or plain dicts (from checkpoint).
    """
    resources_data = []
    for resource in resources:
        if isinstance(resource, dict):
            resources_data.append(resource)
        else:
            resources_data.append({
                "resource_type": resource.resource_type,
                "resource_name": resource.resource_name,
                "attributes": resource.attributes,
                "line_number": resource.line_number
            })

    import json
    return json.dumps(resources_data, indent=2)
