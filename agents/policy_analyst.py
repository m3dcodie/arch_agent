"""
Policy Analyst agent - Retrieves relevant policies via RAG.
"""
import os
from typing import Dict, Any, List
from core.state import AgentState
from models.policy import Policy
from models.violations import AuditStatus
from core.policy_loader import load_policies_from_dir


def policy_analyst_node(state: AgentState) -> Dict[str, Any]:
    """
    Retrieve relevant policies based on parsed resources.
    
    This agent uses RAG (Retrieval-Augmented Generation) to find policies
    that are relevant to the resources parsed by the intake agent.
    
    Args:
        state: Current agent state containing parsed_resources
        
    Returns:
        Dict with updated state fields:
            - retrieved_policies: List of Policy objects
            - resource_types: List of resource type strings
            - current_node: Current node name
            - messages: Status messages
    """
    try:
        parsed_resources = state.get("parsed_resources", [])
        
        # If no resources to analyze, return empty policies
        if not parsed_resources:
            return {
                "retrieved_policies": [],
                "resource_types": [],
                "current_node": "policy_analyst",
                "messages": ["[POLICY_ANALYST] No resources to analyze"]
            }
        
        # Extract unique resource types — resources may be dicts (serialized for checkpoint)
        resource_types = list(set(
            r.get("resource_type", "") if isinstance(r, dict) else r.resource_type
            for r in parsed_resources
        ))
        
        # Build semantic query for RAG retrieval
        # Include resource types and general security/compliance terms
        query_parts = [
            f"Policies for {', '.join(resource_types)} resources",
            "security compliance requirements",
            "database infrastructure policies"
        ]
        query = " ".join(query_parts)
        
        # Check if RAG is enabled
        use_rag = os.getenv("USE_RAG", "true").lower() == "true"
        
        if not use_rag:
            # Offline mode: load policies directly from disk — no microservices needed.
            # Respects POLICIES_DIR env var; falls back to built-in policies/ bundle.
            policies_dir = os.getenv("POLICIES_DIR")
            disk_policies = load_policies_from_dir(policies_dir)
            return {
                "retrieved_policies": [p.model_dump() for p in disk_policies],
                "resource_types": resource_types,
                "current_node": "policy_analyst",
                "messages": [
                    f"[POLICY_ANALYST] RAG disabled — loaded {len(disk_policies)} policies from disk",
                    f"[POLICY_ANALYST] Resource types: {', '.join(resource_types)}"
                ]
            }
        
        # Call REST API for context augmentation
        import requests
        from rag_service_config import CONTEXT_AUG_URL, APPID
        endpoint = CONTEXT_AUG_URL.format(appid=APPID)
        payload = {
            "question": query,
            "metadata": {"resource_types": resource_types}
        }
        headers = {"Content-Type": "application/json"}
        try:
            response = requests.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            return {
                "retrieved_policies": [],
                "resource_types": resource_types,
                "current_node": "policy_analyst",
                "status": AuditStatus.ERROR,
                "error_message": f"RAG API call failed: {str(e)}",
                "messages": [f"[POLICY_ANALYST] ERROR: RAG API call failed: {str(e)}"]
            }

        # Parse relevant_chunks from API response
        relevant_chunks = data.get("relevant_chunks", [])
        retrieved_policies = []
        for chunk in relevant_chunks:
            metadata = chunk.get("metadata", {})
            content = chunk.get("document", "")
            policy = Policy(
                id=metadata.get("id", "unknown"),
                title=metadata.get("title", "Unknown Policy"),
                severity=metadata.get("severity", "MEDIUM"),
                description=_extract_description(content),
                scope=resource_types,
                requirements=content,
                examples_compliant=_extract_section(content, "Compliant Example"),
                examples_non_compliant=_extract_section(content, "Non-Compliant Example"),
                remediation=_extract_section(content, "Remediation"),
                file_path=metadata.get("file_path"),
                distance=chunk.get("distance")
            )
            retrieved_policies.append(policy)

        return {
            "retrieved_policies": [p.model_dump() for p in retrieved_policies],
            "resource_types": resource_types,
            "current_node": "policy_analyst",
            "messages": [
                f"[POLICY_ANALYST] Retrieved {len(retrieved_policies)} relevant policies via REST API",
                f"[POLICY_ANALYST] Resource types: {', '.join(resource_types)}"
            ]
        }
        
    except Exception as e:
        return {
            "retrieved_policies": [],
            "resource_types": [],
            "current_node": "policy_analyst",
            "status": AuditStatus.ERROR,
            "error_message": f"Policy analyst failed: {str(e)}",
            "messages": [f"[POLICY_ANALYST] ERROR: {str(e)}"]
        }


def _extract_description(content: str) -> str:
    """
    Extract a brief description from policy content.
    
    Args:
        content: Full policy markdown content
        
    Returns:
        First paragraph or first 200 characters
    """
    if not content:
        return ""
    
    # Try to find the first paragraph after the title
    lines = content.split('\n')
    for i, line in enumerate(lines):
        line = line.strip()
        # Skip headers and empty lines
        if line and not line.startswith('#') and not line.startswith('**'):
            # Return first substantial paragraph
            return line[:200] + "..." if len(line) > 200 else line
    
    # Fallback: return first 200 characters
    return content[:200] + "..." if len(content) > 200 else content


def _extract_section(content: str, section_name: str) -> str:
    """
    Extract a specific section from policy markdown.
    
    Args:
        content: Full policy markdown content
        section_name: Name of section to extract (e.g., "Remediation")
        
    Returns:
        Content of the section, or empty string if not found
    """
    if not content:
        return ""
    
    lines = content.split('\n')
    in_section = False
    section_content = []
    
    for line in lines:
        # Check if we're entering the target section
        if section_name.lower() in line.lower() and line.strip().startswith('#'):
            in_section = True
            continue
        
        # Check if we're entering a new section (exit current)
        if in_section and line.strip().startswith('#'):
            break
        
        # Collect lines in the section
        if in_section:
            section_content.append(line)
    
    return '\n'.join(section_content).strip()
