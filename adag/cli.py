"""
ADAG CLI — adag scan <path>

Usage:
    adag scan ./infra/
    adag scan main.tf --format json
    adag scan ./infra/ --no-rag --policies-dir ./my-policies
    adag scan ./infra/ --format sarif > results.sarif.json
"""
import json
import logging
import os
import sys
from pathlib import Path

import click
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))

# Configure structured logging once at import time.
# LOG_LEVEL=INFO  → show timing, cost, and agent events (default: WARNING)
# LOG_FORMAT=json → machine-readable JSON lines (default: text)
from core.logging_config import configure_logging  # noqa: E402
configure_logging()


@click.group()
@click.version_option(version="1.0.0", prog_name="adag")
def main():
    """ADAG — AI-Driven Architecture Guardrail

    Audit Terraform files against architecture policies using LLM-powered agents.
    """


@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--policies-dir", "-p",
    default=None,
    metavar="DIR",
    help="Custom policies directory (default: built-in bundle).",
)
@click.option(
    "--llm-provider", "-l",
    default=None,
    metavar="PROVIDER",
    help="LLM provider: bedrock (default) or openai.",
)
@click.option(
    "--format", "-f", "output_format",
    default="text",
    type=click.Choice(["text", "json", "sarif"]),
    help="Output format (default: text).",
)
@click.option(
    "--no-rag",
    is_flag=True,
    default=False,
    help="Disable RAG. Load policies from disk only (fully offline).",
)
@click.option(
    "--quiet", "-q",
    is_flag=True,
    default=False,
    help="Suppress headers; output only violations.",
)
def scan(path, policies_dir, llm_provider, output_format, no_rag, quiet):
    """Scan Terraform file(s) for policy violations.

    PATH can be a single .tf file or a directory (scanned recursively).

    Exit codes:
      0 — all checks passed
      1 — one or more violations found
      2 — error (file not found, LLM failure, etc.)
    """
    from adag.runner import ADAGRunner

    path_obj = Path(path)

    try:
        runner = ADAGRunner(
            terraform_dir=str(path_obj) if path_obj.is_dir() else None,
            terraform_file=str(path_obj) if path_obj.is_file() else None,
            policies_dir=policies_dir,
            llm_provider=llm_provider,
            use_rag=False if no_rag else (os.getenv("USE_RAG", "false").lower() == "true"),
        )
    except Exception as e:
        click.echo(f"Error initialising ADAG: {e}", err=True)
        sys.exit(2)

    if not quiet and output_format == "text":
        click.echo("=" * 70)
        click.echo("  ADAG — AI-Driven Architecture Guardrail")
        click.echo("=" * 70)
        click.echo(f"  Scanning:  {path}")
        click.echo(f"  Policies:  {policies_dir or 'built-in'}")
        click.echo(f"  RAG:       {'disabled (disk only)' if no_rag else 'enabled'}")
        click.echo()

    try:
        results = runner.scan()
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(2)
    except Exception as e:
        click.echo(f"Audit error: {e}", err=True)
        sys.exit(2)

    # ---- Output ----
    if output_format == "json":
        click.echo(json.dumps([r.to_json() for r in results], indent=2))
    elif output_format == "sarif":
        sarif = _merge_sarif([r.to_sarif() for r in results])
        click.echo(json.dumps(sarif, indent=2))
    else:
        _print_text(results, quiet)

    # ---- Exit code ----
    total_violations = sum(len(r.violations) for r in results)
    any_error = any(r.status.value == "error" for r in results)

    if any_error:
        sys.exit(2)
    elif total_violations > 0:
        sys.exit(1)
    else:
        sys.exit(0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_text(results, quiet: bool):
    total_violations = 0

    # Build a lookup: violation_id → patch dict for quick inline rendering
    def _patch_index(result) -> dict:
        idx = {}
        for s in result.suggestions:
            vid = s.get("violation_id") if isinstance(s, dict) else getattr(s, "violation_id", None)
            if vid:
                idx[vid] = s
        return idx

    for result in results:
        symbol = {"passed": "✓", "failed": "✗", "error": "⚠"}.get(
            result.status.value, "?"
        )
        if not quiet:
            click.echo(f"File:         {result.file_path}")
            click.echo(f"Status:       {symbol} {result.status.value.upper()}")
            click.echo(f"Resources:    {result.total_resources}")
            click.echo(f"Violations:   {len(result.violations)}")
            click.echo(f"Suggestions:  {len(result.suggestions)}")

        if result.status.value == "error" and result.error_message:
            click.echo(f"  Error: {result.error_message}")

        if result.violations:
            total_violations += len(result.violations)
            patch_idx = _patch_index(result)
            click.echo()
            for i, v in enumerate(result.violations, 1):
                badge = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(
                    v.severity.value, "⚪"
                )
                click.echo(f"  {i}. {badge} [{v.severity.value}] {v.resource_name}")
                click.echo(f"     Issue:  {v.description}")
                if v.remediation_hint:
                    click.echo(f"     Hint:   {v.remediation_hint}")
                if v.line_number:
                    click.echo(f"     Line:   {v.line_number}")

                # --- Inline suggestion (GitHub Copilot style) ---
                patch = patch_idx.get(v.id)
                if patch:
                    before = (patch.get("before_block") if isinstance(patch, dict)
                              else getattr(patch, "before_block", ""))
                    after = (patch.get("after_block") if isinstance(patch, dict)
                             else getattr(patch, "after_block", ""))
                    explanation = (patch.get("explanation") if isinstance(patch, dict)
                                   else getattr(patch, "explanation", ""))
                    click.echo()
                    click.echo(f"     💡 Suggested fix  ({explanation})")
                    click.echo("     " + "─" * 50)
                    for line in before.splitlines():
                        click.echo(click.style(f"     - {line}", fg="red"))
                    for line in after.splitlines():
                        click.echo(click.style(f"     + {line}", fg="green"))
                    click.echo("     " + "─" * 50)
                click.echo()
        click.echo()

    if not quiet:
        click.echo("=" * 70)
        if total_violations == 0:
            click.echo("  ✓ All checks passed")
        else:
            click.echo(f"  ✗ {total_violations} violation(s) found")
        click.echo("=" * 70)


def _merge_sarif(sarif_list: list) -> dict:
    """Merge per-file SARIF outputs into a single run."""
    if not sarif_list:
        return {}
    base = sarif_list[0]
    for s in sarif_list[1:]:
        extra = s.get("runs", [{}])[0].get("results", [])
        base["runs"][0]["results"].extend(extra)
    return base


if __name__ == "__main__":
    main()
