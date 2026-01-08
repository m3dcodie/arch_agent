"""
Main entry point for the ADAG (AI-Driven Architecture Guardrail) system.
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import after loading env vars
from core.graph import create_graph
from models.violations import AuditStatus, Severity


def print_banner():
    """Print application banner"""
    print("=" * 70)
    print("  ADAG - AI-Driven Architecture Guardrail")
    print("  Phase 1: Deletion Protection Checker")
    print("=" * 70)
    print()


def print_results(result: dict):
    """
    Print audit results in a readable format.
    
    Args:
        result: Final state from the graph execution
    """
    print("\n" + "=" * 70)
    print("AUDIT RESULTS")
    print("=" * 70)
    
    # Print status
    status = result.get("status", AuditStatus.ERROR)
    status_symbol = {
        AuditStatus.PASSED: "✓",
        AuditStatus.FAILED: "✗",
        AuditStatus.ERROR: "⚠"
    }.get(status, "?")
    
    print(f"\nStatus: {status_symbol} {status.value.upper()}")
    print(f"File: {result.get('file_path', 'unknown')}")
    
    # Print resource count
    resources = result.get("parsed_resources", [])
    print(f"Resources Analyzed: {len(resources)}")
    
    # Print violations
    violations = result.get("violations", [])
    print(f"Violations Found: {len(violations)}")
    
    if violations:
        print("\n" + "-" * 70)
        print("VIOLATIONS")
        print("-" * 70)
        
        for i, violation in enumerate(violations, 1):
            severity_color = {
                Severity.HIGH: "🔴",
                Severity.MEDIUM: "🟡",
                Severity.LOW: "🟢"
            }.get(violation.severity, "⚪")
            
            print(f"\n{i}. {severity_color} [{violation.severity.value}] {violation.resource_name}")
            print(f"   Type: {violation.resource_type}")
            print(f"   Issue: {violation.description}")
            
            if violation.line_number:
                print(f"   Line: {violation.line_number}")
            
            if violation.remediation_hint:
                print(f"   Fix: {violation.remediation_hint}")
    
    # Print error message if any
    error_msg = result.get("error_message", "")
    if error_msg:
        print(f"\n⚠ Error: {error_msg}")
    
    # Print execution log
    messages = result.get("messages", [])
    if messages:
        print("\n" + "-" * 70)
        print("EXECUTION LOG")
        print("-" * 70)
        for msg in messages:
            print(f"  {msg}")
    
    print("\n" + "=" * 70)


def main():
    """Main execution function"""
    print_banner()
    
    # Check command line arguments
    if len(sys.argv) < 2:
        print("Usage: python main.py <terraform_file>")
        print("\nExample:")
        print("  python main.py tests/fixtures/bad_terraform.tf")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    # Check if file exists
    if not Path(file_path).exists():
        print(f"Error: File '{file_path}' not found")
        sys.exit(1)
    
    # Read the file
    print(f"Reading file: {file_path}")
    try:
        with open(file_path, 'r') as f:
            iac_code = f.read()
    except Exception as e:
        print(f"Error reading file: {str(e)}")
        sys.exit(1)
    
    # Create the graph
    print("Initializing ADAG system...")
    try:
        # Import providers to register them
        import core.bedrock_provider
        import core.sqlite_provider
        
        graph = create_graph()
        print("✓ System initialized")
    except Exception as e:
        print(f"Error initializing system: {str(e)}")
        sys.exit(1)
    
    # Run the audit
    print(f"\nRunning audit on {file_path}...")
    print("-" * 70)
    
    try:
        result = graph.invo1ke(
            iac_code=iac_code,
            file_path=file_path
        )
        
        # Print results
        print_results(result)
        
        # Exit with appropriate code
        status = result.get("status", AuditStatus.ERROR)
        if status == AuditStatus.PASSED:
            sys.exit(0)
        elif status == AuditStatus.FAILED:
            sys.exit(1)
        else:
            sys.exit(2)
            
    except Exception as e:
        print(f"\n⚠ Execution Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()
