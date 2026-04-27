# Policies

This document covers the 10 built-in policies, the policy Markdown template, how to write custom policies, and how to index policies into the RAG pipeline.

---

## Table of Contents

1. [Built-in Policies](#1-built-in-policies)
2. [Policy Markdown Template](#2-policy-markdown-template)
3. [Writing a Custom Policy](#3-writing-a-custom-policy)
4. [Severity Guidelines](#4-severity-guidelines)
5. [Indexing Policies into RAG (Mode 3)](#5-indexing-policies-into-rag-mode-3)
6. [Worked Example — New Policy from Scratch](#6-worked-example--new-policy-from-scratch)

---

## 1. Built-in Policies

ADAG ships with 10 policies in the `policies/` directory. These cover the most common AWS security and reliability requirements.

| File                           | Policy ID                   | Title                           | Severity | Resource Types                                                       |
| ------------------------------ | --------------------------- | ------------------------------- | -------- | -------------------------------------------------------------------- |
| `delete_protection.md`         | `delete_protection`         | Deletion Protection Required    | HIGH     | `aws_db_instance`, `aws_rds_cluster`                                 |
| `encryption_at_rest.md`        | `encryption_at_rest`        | Encryption at Rest Required     | HIGH     | `aws_db_instance`, `aws_rds_cluster`, `aws_s3_bucket`, `aws_kms_key` |
| `public_access_block.md`       | `public_access_block`       | S3 Public Access Block Required | HIGH     | `aws_s3_bucket`                                                      |
| `multi_az_requirement.md`      | `multi_az_requirement`      | Multi-AZ Deployment Required    | MEDIUM   | `aws_db_instance`, `aws_rds_cluster`                                 |
| `backup_retention.md`          | `backup_retention`          | Backup Retention Period         | MEDIUM   | `aws_db_instance`, `aws_rds_cluster`                                 |
| `automated_backups_enabled.md` | `automated_backups_enabled` | Automated Backups Required      | MEDIUM   | `aws_db_instance`                                                    |
| `kms_key_rotation.md`          | `kms_key_rotation`          | KMS Key Rotation Required       | MEDIUM   | `aws_kms_key`                                                        |
| `allowed_regions.md`           | `allowed_regions`           | Allowed AWS Regions             | MEDIUM   | All                                                                  |
| `required_tagging.md`          | `required_tagging`          | Required Tags                   | LOW      | All                                                                  |
| `naming_conventions.md`        | `naming_conventions`        | Naming Conventions              | LOW      | All                                                                  |

### Policy Descriptions

**`delete_protection`** — Ensures that RDS instances and Aurora clusters have `deletion_protection = true`. Prevents accidental or malicious permanent data loss. A database without deletion protection can be deleted with a single API call.

**`encryption_at_rest`** — Ensures storage is encrypted. For RDS: `storage_encrypted = true`. For S3: companion `aws_s3_bucket_server_side_encryption_configuration` resource must be present. For KMS: key must use AES-256 or similar.

**`public_access_block`** — For S3 buckets, a companion `aws_s3_bucket_public_access_block` resource must be present with `block_public_acls`, `block_public_policy`, `ignore_public_acls`, and `restrict_public_buckets` all set to `true`.

**`multi_az_requirement`** — RDS instances must have `multi_az = true`. Aurora clusters achieve HA through replica placement — at least one replica in a different AZ is required.

**`backup_retention`** — RDS instances and Aurora clusters must set `backup_retention_period` to at least 7 days (production) or 1 day (non-production). Zero disables automated backups entirely.

**`automated_backups_enabled`** — A `backup_retention_period` of 0 explicitly disables automated backups. This must not appear in production resources.

**`kms_key_rotation`** — KMS keys used for encryption must have `enable_key_rotation = true` to rotate the key material annually and limit the blast radius of key compromise.

**`allowed_regions`** — Infrastructure must be deployed only in organisation-approved AWS regions. Detected via the `provider` block's `region` attribute.

**`required_tagging`** — All resources must include a set of required tags: `Environment`, `Owner`, `Project`, `CostCenter`. Missing tags make cost attribution and incident response difficult.

**`naming_conventions`** — Resource names must follow the `<env>-<service>-<purpose>` pattern (e.g., `prod-rds-userdb`). Enforces searchability and operational clarity.

---

## 2. Policy Markdown Template

Every policy file follows this structure. All sections are parsed by the offline policy loader and by the RAG indexing script.

````markdown
# <Human-readable policy title>

## Policy ID `<policy_id>`

## Severity **HIGH** | **MEDIUM** | **LOW**

## Description

A concise 2-3 sentence explanation of what this policy enforces and why.

## Scope

The Terraform resource types this policy applies to:

- `aws_resource_type_one`
- `aws_resource_type_two`

## Requirements

The specific attribute-level requirements. Be precise — the LLM auditor reads this verbatim.

- `attribute_name` MUST be set to `value`
- `other_attribute` MUST NOT be set to `false`
- Companion resource `aws_companion_resource` MUST be present

## Rationale

Why this policy exists. Include security impact, compliance frameworks (SOC 2, ISO 27001, CIS Benchmarks), and operational consequences of non-compliance.

## Examples

### ✅ Compliant

\```hcl
resource "aws_db_instance" "compliant_example" {
identifier = "prod-rds-main"
deletion_protection = true

# ... other attributes

}
\```

### ❌ Non-Compliant

\```hcl
resource "aws_db_instance" "non_compliant_example" {
identifier = "prod-rds-main"
deletion_protection = false # VIOLATION: must be true

# ... other attributes

}
\```

## Remediation

Step-by-step fix instructions. Include the exact Terraform attribute to add or change.

1. Open the resource block in your `.tf` file.
2. Add or change `attribute_name = correct_value`.
3. Run `terraform plan` to verify no destructive changes.
4. Apply and verify in the AWS Console.

## Exceptions

Conditions under which this policy may be waived. If none, write "No exceptions."

## References

- [AWS Documentation link]
- [Relevant CIS Benchmark]
- [Internal runbook or ADR link]
````

---

## 3. Writing a Custom Policy

### Step 1: Choose a Policy ID

Use snake_case. Should describe the requirement, not the resource type.

```
Good:  vpc_flow_logs_enabled
Good:  s3_lifecycle_policy_required
Avoid: aws_s3_bucket_check
Avoid: policy_001
```

### Step 2: Determine Scope

List every Terraform resource type the policy applies to. Only types that the intake agent extracts will be checked. If you need to add a new resource type to the extractor, see [CONTRIBUTING.md](CONTRIBUTING.md).

Currently extractable resource types:

- `aws_db_instance`
- `aws_rds_cluster`
- `aws_rds_cluster_instance`
- `aws_kms_key`
- `aws_s3_bucket`
- `aws_s3_bucket_public_access_block`
- `aws_s3_bucket_server_side_encryption_configuration`
- `provider`

### Step 3: Write the Requirements Section Precisely

The auditor LLM reads the Requirements section verbatim. Ambiguous requirements produce inconsistent results.

**Too vague:**

> Encryption should be configured.

**Precise:**

> `storage_encrypted` MUST be set to `true`. The value `false` or the absence of this attribute is a violation.

### Step 4: Write Both Examples

The `Examples` section is the most important part for LLM accuracy. The compliant example shows exactly what pass looks like; the non-compliant example shows exactly what fail looks like. Include comments on the non-compliant example explaining which attribute is wrong and why.

### Step 5: Save to the Policies Directory

```bash
cp template.md policies/my_policy.md
# edit the file
```

ADAG will automatically pick it up on the next scan (offline mode) or after re-indexing (RAG mode).

### Step 6: Test Your Policy

```bash
# Write a small .tf file that should trigger your policy
cat > /tmp/test_policy.tf << 'EOF'
resource "aws_db_instance" "test" {
  identifier = "test-db"
  # deliberately missing your new required attribute
}
EOF

adag scan /tmp/test_policy.tf --policies-dir ./policies/
```

Verify the violation appears and the remediation hint is correct.

---

## 4. Severity Guidelines

Use this table to choose the right severity for your policy.

| Severity | When to use                                                                                                                            | CI behavior                                                          |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| `HIGH`   | Security breach or data loss risk. Regulatory requirement (SOC 2, HIPAA, PCI DSS).                                                     | Should block merge/deployment.                                       |
| `MEDIUM` | Reliability risk. Operational best practice with significant incident impact. Missing in production is a concern but not an emergency. | Should trigger a review comment. May block at the team's discretion. |
| `LOW`    | Housekeeping. Tagging, naming, cost visibility. Non-compliance does not pose a security or reliability risk.                           | Advisory only. Never blocks.                                         |

**Examples by severity:**

| Policy              | Severity | Reason                              |
| ------------------- | -------- | ----------------------------------- |
| Deletion protection | HIGH     | Permanent data loss if violated     |
| Encryption at rest  | HIGH     | Data breach risk                    |
| Multi-AZ            | MEDIUM   | Availability risk, not security     |
| Backup retention    | MEDIUM   | Recovery risk, not immediate danger |
| Required tags       | LOW      | Cost/ops issue, no safety impact    |
| Naming conventions  | LOW      | Operational discipline only         |

---

## 5. Indexing Policies into RAG (Mode 3)

When using Mode 3 (Advanced RAG), policies must be indexed into ChromaDB before they can be retrieved semantically at scan time.

### Run the indexing script

```bash
# Make sure the RAG microservices are running first
# See RAG_PIPELINE.md for startup instructions

python scripts/index_policies.py
```

This script:

1. Reads all `.md` files from the `policies/` directory
2. Extracts metadata (Policy ID, title, severity, scope)
3. POSTs each file through the full ingestion pipeline:
   - `POST /ingest/{appid}` — register document
   - `POST /chunk/{appid}` — split into chunks (200 tokens, 50 overlap)
   - `POST /embed/{appid}` — generate embeddings
   - `POST /add_vectors` — store in ChromaDB

### Re-index after adding or modifying policies

The indexing script currently re-adds all policies on every run. For large policy sets, consider adding a `--policy-id` flag to index only changed files.

```bash
# After adding vpc_flow_logs_enabled.md
python scripts/index_policies.py
```

### Verify indexing

```bash
# Query the vector store directly
curl -X POST http://localhost:8000/context-augment/archapp \
  -H "Content-Type: application/json" \
  -d '{"query": "deletion protection database RDS"}'
```

The response should include chunks from `delete_protection.md`.

---

## 6. Worked Example — New Policy from Scratch

**Goal:** Write a policy that requires VPC Flow Logs to be enabled for all VPCs.

### 6.1 Create the file

```bash
touch policies/vpc_flow_logs_enabled.md
```

### 6.2 Write the policy

````markdown
# VPC Flow Logs Required

## Policy ID `vpc_flow_logs_enabled`

## Severity **MEDIUM**

## Description

All VPCs must have flow logs enabled to capture IP traffic information for security monitoring, forensics, and troubleshooting. Without flow logs, network activity is invisible to security tooling.

## Scope

- `aws_flow_log`

## Requirements

For every `aws_vpc` resource present, a corresponding `aws_flow_log` resource MUST exist with:

- `vpc_id` referencing the VPC
- `traffic_type` set to `ALL`
- `iam_role_arn` set to a valid IAM role ARN
- `log_destination` or `log_group_name` must be specified

Capturing only `ACCEPT` or `REJECT` traffic is a violation — `ALL` is required.

## Rationale

VPC Flow Logs are required by CIS AWS Foundations Benchmark (v1.4 Control 3.9) and are a prerequisite for anomaly detection, incident response, and forensic investigation. Without them, lateral movement within a VPC is undetectable.

## Examples

### ✅ Compliant

\```hcl
resource "aws_vpc" "main" {
cidr_block = "10.0.0.0/16"
}

resource "aws_flow_log" "main" {
vpc_id = aws_vpc.main.id
traffic_type = "ALL"
iam_role_arn = aws_iam_role.flow_log.arn
log_destination = aws_cloudwatch_log_group.flow_log.arn
}
\```

### ❌ Non-Compliant

\```hcl
resource "aws_vpc" "main" {
cidr_block = "10.0.0.0/16"

# VIOLATION: no aws_flow_log resource present for this VPC

}
\```

\```hcl
resource "aws_flow_log" "main" {
vpc_id = aws_vpc.main.id
traffic_type = "REJECT" # VIOLATION: must be ALL
iam_role_arn = aws_iam_role.flow_log.arn
}
\```

## Remediation

1. Add an `aws_flow_log` resource for each VPC in your Terraform.
2. Set `traffic_type = "ALL"`.
3. Provide `iam_role_arn` with a role that has CloudWatch Logs write permissions.
4. Set `log_destination` to a CloudWatch log group or S3 bucket ARN.
5. Run `terraform plan` and verify no destructive changes.

## Exceptions

Sandbox or personal development VPCs with explicit approval may be exempt. Document the exception in the resource's tags: `FlowLogExemption = "sandbox"`.

## References

- [AWS VPC Flow Logs documentation](https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs.html)
- [CIS AWS Foundations Benchmark v1.4 — Control 3.9](https://www.cisecurity.org/benchmark/amazon_web_services)
````

### 6.3 Add the resource type to the intake agent

`aws_vpc` and `aws_flow_log` are not currently in the intake agent's extraction list. Add them:

```python
# agents/intake.py
AUDITABLE_RESOURCE_TYPES = {
    "aws_db_instance",
    "aws_rds_cluster",
    "aws_rds_cluster_instance",
    "aws_kms_key",
    "aws_s3_bucket",
    "aws_s3_bucket_public_access_block",
    "aws_s3_bucket_server_side_encryption_configuration",
    "aws_vpc",           # add
    "aws_flow_log",      # add
    "provider",
}
```

### 6.4 Test it

```bash
cat > /tmp/test_vpc.tf << 'EOF'
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
}
EOF

adag scan /tmp/test_vpc.tf
```

Expected: one `MEDIUM` violation for missing VPC flow logs.
