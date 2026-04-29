"""
Policy model for representing architecture policies.
"""
from pydantic import BaseModel, Field
from typing import List, Optional


class Policy(BaseModel):
    """Represents a single architecture policy retrieved from RAG."""
    
    id: str = Field(description="Unique policy identifier (e.g., 'delete_protection')")
    title: str = Field(description="Human-readable policy name")
    severity: str = Field(description="HIGH, MEDIUM, or LOW")
    description: str = Field(description="What the policy enforces")
    scope: List[str] = Field(description="Resource types this applies to", default_factory=list)
    requirements: str = Field(description="Specific technical requirements")
    examples_compliant: str = Field(description="Example of compliant code", default="")
    examples_non_compliant: str = Field(description="Example of violations", default="")
    remediation: str = Field(description="How to fix violations", default="")
    
    # Metadata for retrieval
    file_path: Optional[str] = Field(default=None, description="Source file path")
    chunk_id: Optional[str] = Field(default=None, description="Chunk identifier if applicable")
    distance: Optional[float] = Field(default=None, description="Semantic distance from query")


class PolicyList(BaseModel):
    """List of policies for structured output."""
    
    policies: List[Policy] = Field(description="List of retrieved policies")
