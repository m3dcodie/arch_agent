# Functionality

This document describes what ADAG does: what it accepts as input, what policies it enforces, what outputs it produces, and how it integrates with CI/CD pipelines.

---

## Table of Contents

1. [Inputs](#1-inputs)
2. [Built-in Policy Engine](#2-built-in-policy-engine)
3. [Output Formats](#3-output-formats)
4. [Exit Codes](#4-exit-codes)
5. [CI/CD Integration](#5-cicd-integration)
6. [MCP Tool Surface](#6-mcp-tool-surface)

---

## 1. Inputs

### File or Directory

```bash
# Single file
adag scan ./infra/main.tf

# Entire directory (recursive .tf discovery)
adag scan ./infra/

# Programmatic API
from adag import ADAGRunner
runner = ADAGRunner(llm_provider="github-copilot")
result = runner.scan("./infra/main.tf")
```

ADAG reads `.tf` files as raw text. No Terraform CLI, no `terraform init`, no provider plugins are required. The intake agent parses HCL using a built-in regex parser.

### Supported Resource Types

The intake agent extracts these resource types (others are skipped):

| Resource Type                                        | Service                  |
| ---------------------------------------------------- | ------------------------ |
| `aws_db_instance`                                    | RDS                      |
| `aws_rds_cluster`                                    | Aurora                   |
| `aws_rds_cluster_instance`                           | Aurora instance          |
| `aws_kms_key`                                        | KMS                      |
| `aws_s3_bucket`                                      | S3                       |
| `aws_s3_bucket_public_access_block`                  | S3 public access config  |
| `aws_s3_bucket_server_side_encryption_configuration` | S3 encryption config     |
| `provider`                                           | Terraform provider block |

### Custom Policies Directory

```bash
adag scan ./infra/ --policies-dir ./my-company-policies/
```

Any directory of Markdown files following the [policy template](POLICIES.md) is accepted. Built-in policies are replaced entirely when this flag is used.

---

## 2. Built-in Policy Engine

ADAG ships with 10 built-in policies covering common AWS security and reliability requirements.

| Policy ID                   | Title                           | Severity | Resource Types                                                       |
| --------------------------- | ------------------------------- | -------- | -------------------------------------------------------------------- |
| `delete_protection`         | Deletion Protection Required    | HIGH     | `aws_db_instance`, `aws_rds_cluster`                                 |
| `encryption_at_rest`        | Encryption at Rest Required     | HIGH     | `aws_db_instance`, `aws_rds_cluster`, `aws_s3_bucket`, `aws_kms_key` |
| `public_access_block`       | S3 Public Access Block Required | HIGH     | `aws_s3_bucket`                                                      |
| `multi_az_requirement`      | Multi-AZ Deployment Required    | MEDIUM   | `aws_db_instance`, `aws_rds_cluster`                                 |
| `backup_retention`          | Backup Retention Period         | MEDIUM   | `aws_db_instance`, `aws_rds_cluster`                                 |
| `automated_backups_enabled` | Automated Backups Required      | MEDIUM   | `aws_db_instance`                                                    |
| `kms_key_rotation`          | KMS Key Rotation Required       | MEDIUM   | `aws_kms_key`                                                        |
| `allowed_regions`           | Allowed AWS Regions             | MEDIUM   | All resources                                                        |
| `required_tagging`          | Required Tags                   | LOW      | All resources                                                        |
| `naming_conventions`        | Naming Conventions              | LOW      | All resources                                                        |

### Severity Levels

| Severity | Meaning                                                                   |
| -------- | ------------------------------------------------------------------------- |
| `HIGH`   | Security or data-loss risk. Blocks deployment in strict CI modes.         |
| `MEDIUM` | Reliability or compliance risk. Should be addressed before production.    |
| `LOW`    | Operational best practice. Advisory — does not fail the build by default. |

---

## 3. Output Formats

### Text (default)

Human-readable output suitable for terminal use and code review feedback.

```
======================================================================
  ADAG - AI-Driven Architecture Guardrail
======================================================================

File: infra/main.tf
Resources Analyzed: 3
Violations Found: 2

----------------------------------------------------------------------
VIOLATIONS
----------------------------------------------------------------------

1. [HIGH] aws_db_instance / main
   Policy:      delete_protection
   Issue:       Database instance does not have deletion protection enabled.
   Line:        3
   Remediation: Add 'deletion_protection = true' to the resource block.

2. [MEDIUM] aws_db_instance / main
   Policy:      multi_az_requirement
   Issue:       Database instance does not have multi-AZ enabled.
   Line:        3
   Remediation: Add 'multi_az = true' to the resource block.

----------------------------------------------------------------------
Status: FAILED
```

### JSON

Machine-readable format. Use with `--format json`.

```json
[
  {
    "status": "FAILED",
    "file_path": "infra/main.tf",
    "total_resources": 3,
    "violations": [
      {
        "id": "V-001",
        "resource_type": "aws_db_instance",
        "resource_name": "main",
        "severity": "HIGH",
        "policy_ref": "delete_protection",
        "description": "Database instance does not have deletion protection enabled.",
        "line_number": 3,
        "remediation_hint": "Add 'deletion_protection = true' to the resource block."
      },
      {
        "id": "V-002",
        "resource_type": "aws_db_instance",
        "resource_name": "main",
        "severity": "MEDIUM",
        "policy_ref": "multi_az_requirement",
        "description": "Database instance does not have multi-AZ enabled.",
        "line_number": 3,
        "remediation_hint": "Add 'multi_az = true' to the resource block."
      }
    ],
    "summary": "2 violations found: 1 HIGH, 1 MEDIUM, 0 LOW"
  }
]
```

### SARIF

[SARIF 2.1.0](https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html) format for GitHub Advanced Security. Use with `--format sarif`.

```json
{
  "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
  "version": "2.1.0",
  "runs": [
    {
      "tool": {
            "driver": {
            "name": "ADAG",
            "version": "1.0.0",
          "rules": [
            {
              "id": "delete_protection",
              "name": "DeletionProtectionRequired",
              "shortDescription": { "text": "Deletion Protection Required" },
              "defaultConfiguration": { "level": "error" }
            }
          ]
        }
      },
      "results": [
        {
          "ruleId": "delete_protection",
          "level": "error",
          "message": {
            "text": "Database instance does not have deletion protection enabled."
          },
          "locations": [
            {
              "physicalLocation": {
                "artifactLocation": { "uri": "infra/main.tf" },
                "region": { "startLine": 3 }
              }
            }
          ]
        }
      ]
    }
  ]
}
```

**Uploading SARIF to GitHub:**

```bash
adag scan ./infra/ --format sarif > results.sarif
gh code-scanning upload --sarif results.sarif
```

This surfaces violations as native code scanning alerts in the GitHub Security tab and as PR annotations.

---

## 4. Exit Codes

| Code | Meaning                                          | Typical Use                  |
| ---- | ------------------------------------------------ | ---------------------------- |
| `0`  | All resources passed all policies                | CI step succeeds             |
| `1`  | One or more violations found                     | CI step fails (blocks merge) |
| `2`  | Scan error (parse failure, provider error, etc.) | CI step fails with error     |

The exit code allows ADAG to be used directly in shell conditionals:

```bash
if adag scan ./infra/; then
  echo "Compliance check passed"
else
  echo "Compliance check failed — see violations above"
  exit 1
fi
```

---

## 5. CI/CD Integration

### GitHub Actions

```yaml
name: Architecture Compliance

on: [pull_request]

jobs:
  compliance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install ADAG
        run: pip install adag

      - name: Run compliance scan (text output)
        env:
          LLM_PROVIDER: github-copilot
          GITHUB_COPILOT_TOKEN: ${{ secrets.GITHUB_COPILOT_TOKEN }}
        run: adag scan ./infra/

      - name: Run compliance scan (SARIF for code scanning)
        env:
          LLM_PROVIDER: github-copilot
          GITHUB_COPILOT_TOKEN: ${{ secrets.GITHUB_COPILOT_TOKEN }}
        run: adag scan ./infra/ --format sarif > results.sarif

      - name: Upload SARIF
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: results.sarif
```

### GitLab CI

```yaml
compliance:
  image: python:3.11
  script:
    - pip install adag
    - adag scan ./infra/
  variables:
    LLM_PROVIDER: github-copilot
    GITHUB_COPILOT_TOKEN: $GITHUB_COPILOT_TOKEN
```

### Pre-commit Hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: adag
        name: Architecture Compliance
        language: python
        entry: adag scan
        types: [terraform]
        pass_filenames: true
```

---

## 6. MCP Tool Surface

When running as an MCP server (`python -m adag.mcp_server`), ADAG exposes 5 tools that any MCP-compatible AI assistant can call.

| Tool                   | Parameters      | Returns                                   |
| ---------------------- | --------------- | ----------------------------------------- |
| `check_terraform_file` | `path: str`     | Violations dict or error dict             |
| `scan_terraform_dir`   | `path: str`     | List of per-file results                  |
| `list_policies`        | _(none)_        | List of `{id, title, severity, filename}` |
| `query_rag`            | `question: str` | RAG context chunks (Mode 3 only)          |
| `ingest_document`      | `path: str`     | Ingestion confirmation (Mode 3 only)      |

`query_rag` and `ingest_document` return `{"error": "RAG not enabled ..."}` when `USE_RAG=false` rather than raising an exception, so the calling AI agent can handle the failure gracefully.

See [MCP.md](MCP.md) for full configuration and usage examples.
