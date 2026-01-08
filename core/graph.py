"""
LangGraph workflow construction for the ADAG system.
"""
import os
from typing import Optional
from langgraph.graph import StateGraph, END
from langchain_core.language_models import BaseChatModel

from core.state import AgentState
from core.llm_provider import LLMFactory
from core.database_provider import DatabaseFactory
from agents.intake import intake_node
from agents.policy_analyst import policy_analyst_node
from agents.auditor import auditor_node
from models.violations import AuditStatus


class ADAGGraph:
    """
    AI-Driven Architecture Guardrail Graph.
    
    This class constructs and manages the LangGraph workflow for
    auditing infrastructure-as-code files.
    """
    
    def __init__(
        self,
        llm_provider: Optional[str] = None,
        db_provider: Optional[str] = None,
        **config
    ):
        """
        Initialize the ADAG graph.
        
        Args:
            llm_provider: Name of LLM provider (default: from env or 'bedrock')
            db_provider: Name of database provider (default: from env or 'sqlite')
            **config: Additional configuration options
        """
        # Get provider names from env or use defaults
        self.llm_provider_name = llm_provider or os.getenv("LLM_PROVIDER", "bedrock")
        self.db_provider_name = db_provider or os.getenv("DB_PROVIDER", "sqlite")
        
        # Create providers
        self.llm_provider = LLMFactory.create_provider(self.llm_provider_name)
        self.db_provider = DatabaseFactory.create_provider(self.db_provider_name)
        
        # Get LLM model
        self.llm = self.llm_provider.get_model()
        
        # Build the graph
        self.graph = self._build_graph()
    
    def _build_graph(self):
        """
        Build the LangGraph workflow.
        
        Phase 2 workflow:
        START -> intake -> policy_analyst -> auditor -> END
        
        Returns:
            Compiled graph ready for execution
        """
        # Create the state graph
        workflow = StateGraph(AgentState)
        
        # Add nodes with LLM binding
        workflow.add_node("intake", lambda state: intake_node(state, self.llm))
        workflow.add_node("policy_analyst", lambda state: policy_analyst_node(state))
        workflow.add_node("auditor", lambda state: auditor_node(state, self.llm))
        
        # Define the flow
        workflow.set_entry_point("intake")
        
        # Add conditional edge from intake
        workflow.add_conditional_edges(
            "intake",
            self._should_continue_after_intake,
            {
                "policy_analyst": "policy_analyst",
                "end": END
            }
        )
        
        # Add conditional edge from policy_analyst
        workflow.add_conditional_edges(
            "policy_analyst",
            self._should_continue_after_policy_analyst,
            {
                "auditor": "auditor",
                "end": END
            }
        )
        
        # Auditor always goes to END
        workflow.add_edge("auditor", END)
        
        # Compile with checkpointer
        checkpointer = self.db_provider.get_checkpointer()
        return workflow.compile(checkpointer=checkpointer)
    
    def _should_continue_after_intake(self, state: AgentState) -> str:
        """
        Determine if we should continue to policy_analyst or end.
        
        Args:
            state: Current agent state
            
        Returns:
            Next node name or 'end'
        """
        # If intake failed, end the workflow
        if state.get("status") == AuditStatus.ERROR:
            return "end"
        
        # If no resources were parsed, end the workflow
        if not state.get("parsed_resources"):
            return "end"
        
        # Otherwise, continue to policy_analyst
        return "policy_analyst"
    
    def _should_continue_after_policy_analyst(self, state: AgentState) -> str:
        """
        Determine if we should continue to auditor or end.
        
        Args:
            state: Current agent state
            
        Returns:
            Next node name or 'end'
        """
        # If policy analyst failed, end the workflow
        if state.get("status") == AuditStatus.ERROR:
            return "end"
        
        # If no policies were retrieved, we can still continue to auditor
        # (it will handle the fallback to hardcoded policies)
        # But if explicitly disabled, end here
        use_rag = os.getenv("USE_RAG", "true").lower() == "true"
        if not use_rag and not state.get("retrieved_policies"):
            return "end"
        
        # Otherwise, continue to auditor
        return "auditor"
    
    def invoke(self, iac_code: str, file_path: str, **kwargs):
        """
        Run the audit workflow on IaC code.
        
        Args:
            iac_code: Raw infrastructure-as-code content
            file_path: Path to the source file
            **kwargs: Additional invoke options (e.g., config for checkpointing)
            
        Returns:
            Final state after workflow execution
        """
        initial_state = {
            "iac_code": iac_code,
            "file_path": file_path,
            "messages": [],
            "parsed_resources": [],
            "retrieved_policies": [],
            "resource_types": [],
            "violations": [],
            "status": AuditStatus.PENDING,
            "current_node": "",
            "error_message": ""
        }
        
        # Provide config with thread_id for checkpointing
        if "config" not in kwargs:
            kwargs["config"] = {"configurable": {"thread_id": "default"}}
        
        return self.graph.invoke(initial_state, **kwargs)
    
    def stream(self, iac_code: str, file_path: str, **kwargs):
        """
        Stream the audit workflow execution.
        
        Args:
            iac_code: Raw infrastructure-as-code content
            file_path: Path to the source file
            **kwargs: Additional stream options
            
        Yields:
            State updates as the workflow progresses
        """
        initial_state = {
            "iac_code": iac_code,
            "file_path": file_path,
            "messages": [],
            "parsed_resources": [],
            "retrieved_policies": [],
            "resource_types": [],
            "violations": [],
            "status": AuditStatus.PENDING,
            "current_node": "",
            "error_message": ""
        }
        
        for state in self.graph.stream(initial_state, **kwargs):
            yield state


def create_graph(
    llm_provider: Optional[str] = None,
    db_provider: Optional[str] = None,
    **config
) -> ADAGGraph:
    """
    Factory function to create an ADAG graph.
    
    Args:
        llm_provider: Name of LLM provider
        db_provider: Name of database provider
        **config: Additional configuration
        
    Returns:
        Configured ADAGGraph instance
    """
    return ADAGGraph(
        llm_provider=llm_provider,
        db_provider=db_provider,
        **config
    )
