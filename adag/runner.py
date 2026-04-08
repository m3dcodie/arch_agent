"""
ADAGRunner — the main public API for the ADAG package.

Wraps the LangGraph workflow so callers never interact with the graph directly.

Examples:

    # Scan a directory, offline (no RAG)
    runner = ADAGRunner(terraform_dir="./infra", use_rag=False)
    results = runner.scan()

    # Scan a single file with custom policies
    runner = ADAGRunner(
        terraform_file="./main.tf",
        policies_dir="./my-policies",
    )
    results = runner.scan()
    print(results[0].to_json())
"""
import os
import logging
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class ADAGRunner:
    """
    High-level runner for ADAG audits.

    Args:
        terraform_dir:  Scan all .tf files recursively in this directory.
        terraform_file: Scan a single .tf file.
        policies_dir:   Path to a directory of policy .md files.
                        Defaults to the built-in policies/ bundle.
        llm_provider:   'bedrock' (default) or 'openai'.
        use_rag:        True  → retrieve policies via the RAG microservices.
                        False → load policies directly from disk (offline mode).
                        Default: reads USE_RAG env var, falls back to False.
        env_file:       Optional path to a .env file to load.
    """

    def __init__(
        self,
        terraform_dir: Optional[str] = None,
        terraform_file: Optional[str] = None,
        policies_dir: Optional[str] = None,
        llm_provider: Optional[str] = None,
        use_rag: Optional[bool] = None,
        env_file: Optional[str] = None,
    ):
        # Load environment
        load_dotenv(env_file) if env_file else load_dotenv()

        if not terraform_dir and not terraform_file:
            raise ValueError("Provide either terraform_dir or terraform_file")
        if terraform_dir and terraform_file:
            raise ValueError("Provide terraform_dir OR terraform_file, not both")

        self.terraform_dir = Path(terraform_dir) if terraform_dir else None
        self.terraform_file = Path(terraform_file) if terraform_file else None
        self.policies_dir = policies_dir
        self.llm_provider = llm_provider

        # Configure RAG mode via env so agents pick it up
        if use_rag is not None:
            os.environ["USE_RAG"] = "true" if use_rag else "false"
        else:
            # Default to offline (disk) mode unless explicitly set
            if "USE_RAG" not in os.environ:
                os.environ["USE_RAG"] = "false"

        if policies_dir:
            os.environ["POLICIES_DIR"] = str(policies_dir)

        # Register providers (trigger their @register decorators)
        # Only import bedrock if it will be used — boto3 credential lookup
        # can hang when no AWS config is present.
        _llm = (llm_provider or os.getenv("LLM_PROVIDER", "bedrock")).lower()
        if _llm == "bedrock":
            import core.bedrock_provider  # noqa: F401
        import core.ollama_provider   # noqa: F401
        import core.sqlite_provider   # noqa: F401

        # Lazy-initialise the graph on first scan()
        self._graph = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan(self) -> List:
        """
        Run the audit on the configured Terraform file(s).

        Returns:
            List of AuditResult objects, one per .tf file scanned.
        """
        from models.violations import AuditResult, AuditStatus

        graph = self._get_graph()
        tf_files = self._get_tf_files()
        results = []

        for tf_file in tf_files:
            logger.info(f"Scanning: {tf_file}")
            try:
                iac_code = tf_file.read_text(encoding="utf-8")
                raw = graph.invoke(iac_code=iac_code, file_path=str(tf_file))
                result = AuditResult(
                    status=raw.get("status", AuditStatus.ERROR),
                    file_path=raw.get("file_path", str(tf_file)),
                    total_resources=len(raw.get("parsed_resources", [])),
                    violations=raw.get("violations", []),
                    summary=self._build_summary(raw),
                )
            except Exception as e:
                logger.error(f"Error scanning {tf_file}: {e}")
                result = AuditResult(
                    status=AuditStatus.ERROR,
                    file_path=str(tf_file),
                    total_resources=0,
                    violations=[],
                    summary=f"Scan failed: {e}",
                )
            results.append(result)

        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_graph(self):
        if self._graph is None:
            from core.graph import create_graph
            self._graph = create_graph(llm_provider=self.llm_provider)
        return self._graph

    def _get_tf_files(self) -> List[Path]:
        if self.terraform_file:
            if not self.terraform_file.exists():
                raise FileNotFoundError(f"File not found: {self.terraform_file}")
            return [self.terraform_file]

        if not self.terraform_dir.exists():
            raise FileNotFoundError(f"Directory not found: {self.terraform_dir}")

        files = sorted(self.terraform_dir.rglob("*.tf"))
        if not files:
            raise ValueError(f"No .tf files found in: {self.terraform_dir}")
        return files

    @staticmethod
    def _build_summary(raw: dict) -> str:
        violations = raw.get("violations", [])
        resources = raw.get("parsed_resources", [])
        status = raw.get("status")
        if status and status.value == "passed":
            return f"All {len(resources)} resource(s) passed all policy checks."
        elif violations:
            return (
                f"Found {len(violations)} violation(s) across "
                f"{len(resources)} resource(s)."
            )
        return "Audit complete."
