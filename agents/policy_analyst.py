"""
Policy Analyst agent - Retrieves relevant policies via RAG.
"""
import os
from typing import Dict, Any, List
from core.state import AgentState
from core.rag_provider import RAGFactory
from models.policy import Policy
from models.violations import AuditStatus


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
        
        # Extract unique resource types from parsed resources
        resource_types = list(set([r.resource_type for r in parsed_resources]))
        
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
            return {
                "retrieved_policies": [],
                "resource_types": resource_types,
                "current_node": "policy_analyst",
                "messages": ["[POLICY_ANALYST] RAG disabled, skipping policy retrieval"]
            }
        
        # Initialize RAG provider
        rag_provider = os.getenv("RAG_PROVIDER", "chroma")
        chroma_dir = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma")
        
        rag = RAGFactory.create_provider(rag_provider, persist_directory=chroma_dir)
        rag.initialize(collection_name="policies")
        
        # Check if collection has documents
        stats = rag.get_collection_stats()
        if stats.get("document_count", 0) == 0:
            return {
                "retrieved_policies": [],
                "resource_types": resource_types,
                "current_node": "policy_analyst",
                "status": AuditStatus.ERROR,
                "error_message": "No policies indexed. Run: python scripts/index_policies.py",
                "messages": ["[POLICY_ANALYST] ERROR: No policies found in vector database"]
            }
        
        # Retrieve relevant policies (top 5 by default)
        top_k = int(os.getenv("RAG_TOP_K", "5"))
        results = rag.retrieve(query, top_k=top_k)
        
        # Convert RAG results to Policy objects
        retrieved_policies = []
        for result in results:
            metadata = result.get("metadata", {})
            
            # Create Policy object from retrieved document
            policy = Policy(
                id=result.get("id", "unknown"),
                title=metadata.get("title", "Unknown Policy"),
                severity=metadata.get("severity", "MEDIUM"),
                description=_extract_description(result.get("content", "")),
                scope=resource_types,  # Scope is the resource types we're checking
                requirements=result.get("content", ""),  # Full policy content
                examples_compliant=_extract_section(result.get("content", ""), "Compliant Example"),
                examples_non_compliant=_extract_section(result.get("content", ""), "Non-Compliant Example"),
                remediation=_extract_section(result.get("content", ""), "Remediation"),
                file_path=metadata.get("file_path"),
                distance=result.get("distance")
            )
            retrieved_policies.append(policy)
        
        return {
            "retrieved_policies": retrieved_policies,
            "resource_types": resource_types,
            "current_node": "policy_analyst",
            "messages": [
                f"[POLICY_ANALYST] Retrieved {len(retrieved_policies)} relevant policies",
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
