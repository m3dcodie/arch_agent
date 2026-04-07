"""
ADAG — AI-Driven Architecture Guardrail

Usage:
    from adag import ADAGRunner

    runner = ADAGRunner(terraform_dir="./infra")
    results = runner.scan()
    for result in results:
        if result.violations:
            print(result.to_json())
"""
from adag.runner import ADAGRunner

__version__ = "0.1.0"
__all__ = ["ADAGRunner"]
