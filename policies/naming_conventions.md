# Naming Conventions Policy

## Policy ID

`naming_conventions`

## Severity

**LOW**

## Description

All AWS resources MUST follow standardized naming conventions to ensure consistency, improve searchability, and enable automated operations. Proper naming conventions make infrastructure more maintainable and reduce operational errors.

## Scope

This policy applies to **AWS-facing name attributes only**. Terraform resource block labels
(the identifier inside `resource "TYPE" "LABEL" {}`) are **not** subject to this policy;
Terraform convention uses underscores for block labels and they are internal to Terraform.

Checked attributes per resource type:

- `aws_db_instance` → `identifier`
- `aws_rds_cluster` → `cluster_identifier`
- `aws_s3_bucket` → `bucket`
- `aws_kms_key` → `Name` tag (the `description` field is free-text, not a naming-convention field)
- `aws_ec2_instance` → `Name` tag
- `aws_lambda_function` → `function_name`
- `aws_security_group` → `name`
- `aws_vpc` → `Name` tag
- `aws_iam_role` → `name`
- If a resource has none of the above attributes present in the parsed JSON, **skip** the naming check.

## Requirements

### General Naming Rules

1. **Lowercase Only:** All names must be lowercase
2. **Hyphen Separator:** Use hyphens (`-`) not underscores (`_`)
3. **No Spaces:** No spaces allowed
4. **Alphanumeric:** Start with letter, contain only letters, numbers, and hyphens
5. **Length:** 3-63 characters (varies by resource type)

### Naming Pattern

```
<environment>-<application>-<resource-type>-<identifier>
```

**Examples:**

- `prod-api-db-primary`
- `staging-web-cache-redis`
- `dev-analytics-bucket-raw`

### Environment Prefixes

- `prod-` for production
- `staging-` for staging
- `dev-` for development
- `test-` for testing

## Rationale

Naming conventions are critical for:

1. **Consistency:** Predictable resource identification
2. **Searchability:** Easy to find related resources
3. **Automation:** Enable scripted operations
4. **Troubleshooting:** Quick identification during incidents
5. **Cost Tracking:** Group resources by naming patterns
6. **Security:** Identify resource purpose and sensitivity
7. **Team Collaboration:** Clear ownership and purpose

## Examples

### ✅ Compliant - RDS Database

```hcl
resource "aws_db_instance" "primary" {
  identifier = "prod-api-db-primary"  # ✓ Follows pattern
  engine     = "postgres"
  instance_class = "db.r5.large"

  username = "admin"
  password = var.db_password

  tags = {
    Name = "prod-api-db-primary"
  }
}
```

### ✅ Compliant - Aurora Cluster

```hcl
resource "aws_rds_cluster" "main" {
  cluster_identifier = "prod-orders-aurora-cluster"  # ✓ Descriptive
  engine             = "aurora-postgresql"
  engine_version     = "14.6"

  tags = {
    Name = "prod-orders-aurora-cluster"
  }
}
```

### ✅ Compliant - S3 Bucket

```hcl
resource "aws_s3_bucket" "data" {
  bucket = "prod-analytics-data-raw"  # ✓ Follows pattern

  tags = {
    Name = "prod-analytics-data-raw"
  }
}
```

### ✅ Compliant - Lambda Function

```hcl
resource "aws_lambda_function" "processor" {
  function_name = "prod-orders-processor-v2"  # ✓ Includes version
  runtime       = "python3.11"
  handler       = "index.handler"
  role          = aws_iam_role.lambda.arn

  tags = {
    Name = "prod-orders-processor-v2"
  }
}
```

### ✅ Compliant - Security Group

```hcl
resource "aws_security_group" "app" {
  name        = "prod-api-sg-application"  # ✓ Clear purpose
  description = "Security group for production API application servers"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "prod-api-sg-application"
  }
}
```

### ✅ Compliant - EC2 Instance

```hcl
resource "aws_instance" "web" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.large"

  tags = {
    Name = "prod-web-server-01"  # ✓ Numbered for multiple instances
  }
}
```

### ✅ Compliant - VPC

```hcl
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"

  tags = {
    Name = "prod-main-vpc"  # ✓ Simple and clear
  }
}
```

### ✅ Compliant - IAM Role

```hcl
resource "aws_iam_role" "lambda" {
  name = "prod-orders-lambda-execution-role"  # ✓ Descriptive

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}
```

### ❌ Non-Compliant - RDS with Uppercase

```hcl
resource "aws_db_instance" "primary" {
  identifier = "Prod-API-Database"  # ✗ Contains uppercase letters
  engine     = "postgres"
  instance_class = "db.r5.large"

  username = "admin"
  password = var.db_password
}
```

### ❌ Non-Compliant - RDS with Underscores

```hcl
resource "aws_db_instance" "primary" {
  identifier = "prod_api_db_primary"  # ✗ Uses underscores instead of hyphens
  engine     = "postgres"
  instance_class = "db.r5.large"

  username = "admin"
  password = var.db_password
}
```

### ❌ Non-Compliant - S3 Bucket with Spaces

```hcl
resource "aws_s3_bucket" "data" {
  bucket = "prod analytics data"  # ✗ Contains spaces (invalid)

  tags = {
    Name = "Production Analytics Data"
  }
}
```

### ❌ Non-Compliant - Lambda with Poor Naming

```hcl
resource "aws_lambda_function" "processor" {
  function_name = "myFunction123"  # ✗ No environment, camelCase
  runtime       = "python3.11"
  handler       = "index.handler"
  role          = aws_iam_role.lambda.arn
}
```

### ❌ Non-Compliant - Security Group Generic Name

```hcl
resource "aws_security_group" "app" {
  name        = "sg-12345"  # ✗ Non-descriptive
  description = "Security group"
  vpc_id      = aws_vpc.main.id
}
```

### ❌ Non-Compliant - EC2 with No Pattern

```hcl
resource "aws_instance" "web" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.large"

  tags = {
    Name = "WebServer"  # ✗ No environment, no hyphen separation
  }
}
```

### ❌ Non-Compliant - VPC Too Generic

```hcl
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"

  tags = {
    Name = "vpc1"  # ✗ Too generic, no environment
  }
}
```

### ❌ Non-Compliant - IAM Role with Mixed Case

```hcl
resource "aws_iam_role" "lambda" {
  name = "LambdaExecutionRole"  # ✗ CamelCase, no environment/app context

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}
```

### ❌ Non-Compliant - Aurora with Numbers Only

```hcl
resource "aws_rds_cluster" "main" {
  cluster_identifier = "cluster-12345"  # ✗ No environment or application context
  engine             = "aurora-postgresql"
}
```

## Remediation

### Rename Resources to Follow Convention

```hcl
# Before (non-compliant)
identifier = "MyDatabase"

# After (compliant)
identifier = "prod-api-db-primary"
```

### Use Terraform Variables for Consistency

```hcl
variable "environment" {
  description = "Environment name"
  type        = string
  default     = "prod"
}

variable "application" {
  description = "Application name"
  type        = string
  default     = "api"
}

resource "aws_db_instance" "primary" {
  identifier = "${var.environment}-${var.application}-db-primary"
  # ... other configuration ...
}
```

### Use Terraform Locals for Complex Naming

```hcl
locals {
  name_prefix = "${var.environment}-${var.application}"

  resource_names = {
    database       = "${local.name_prefix}-db-primary"
    cache          = "${local.name_prefix}-cache-redis"
    bucket_raw     = "${local.name_prefix}-data-raw"
    bucket_processed = "${local.name_prefix}-data-processed"
  }
}

resource "aws_db_instance" "primary" {
  identifier = local.resource_names.database
  # ... configuration ...
}

resource "aws_s3_bucket" "raw" {
  bucket = local.resource_names.bucket_raw
  # ... configuration ...
}
```

## Naming Patterns by Resource Type

### Databases

```
<env>-<app>-db-<purpose>
Examples:
- prod-api-db-primary
- prod-api-db-replica-01
- staging-analytics-db-warehouse
```

### Storage

```
<env>-<app>-<storage-type>-<purpose>
Examples:
- prod-media-s3-uploads
- prod-logs-s3-application
- dev-backup-s3-snapshots
```

### Compute

```
<env>-<app>-<compute-type>-<identifier>
Examples:
- prod-web-ec2-01
- prod-api-lambda-processor
- staging-worker-ecs-task
```

### Networking

```
<env>-<purpose>-<network-type>-<identifier>
Examples:
- prod-main-vpc
- prod-public-subnet-1a
- prod-private-subnet-1b
- prod-api-sg-application
- prod-web-alb-public
```

### Security

```
<env>-<app>-<security-type>-<purpose>
Examples:
- prod-api-iam-role-execution
- prod-web-kms-key-encryption
- prod-app-secret-db-password
```

## Resource-Specific Rules

### S3 Buckets

- **Global Uniqueness:** Must be globally unique
- **DNS Compliance:** No uppercase, no underscores
- **Length:** 3-63 characters
- **Pattern:** `<company>-<env>-<app>-<purpose>`

```hcl
bucket = "acme-prod-api-data-raw"
```

### RDS Identifiers

- **Length:** 1-63 characters
- **Start:** Must begin with letter
- **Pattern:** `<env>-<app>-db-<purpose>`

```hcl
identifier = "prod-orders-db-primary"
```

### Lambda Functions

- **Length:** 1-64 characters
- **Pattern:** `<env>-<app>-<function>-<version>`

```hcl
function_name = "prod-orders-processor-v2"
```

### IAM Roles

- **Length:** 1-64 characters
- **Pattern:** `<env>-<app>-<service>-role-<purpose>`

```hcl
name = "prod-api-lambda-role-execution"
```

## Validation

### Terraform Validation

```hcl
variable "db_identifier" {
  type = string

  validation {
    condition = can(regex("^[a-z][a-z0-9-]*$", var.db_identifier))
    error_message = "DB identifier must start with a letter and contain only lowercase letters, numbers, and hyphens."
  }

  validation {
    condition = length(var.db_identifier) >= 3 && length(var.db_identifier) <= 63
    error_message = "DB identifier must be between 3 and 63 characters."
  }

  validation {
    condition = can(regex("^(prod|staging|dev|test)-", var.db_identifier))
    error_message = "DB identifier must start with environment prefix (prod-, staging-, dev-, test-)."
  }
}
```

### Pre-commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-commit

# Check for naming convention violations in Terraform files
echo "Checking naming conventions..."

# Check for uppercase in identifiers
if git diff --cached --name-only | grep -E '\.tf$' | xargs grep -E 'identifier.*=.*"[^"]*[A-Z]'; then
  echo "ERROR: Found uppercase letters in resource identifiers"
  exit 1
fi

# Check for underscores in names
if git diff --cached --name-only | grep -E '\.tf$' | xargs grep -E '(identifier|bucket|function_name).*=.*"[^"]*_'; then
  echo "ERROR: Found underscores in resource names (use hyphens)"
  exit 1
fi

echo "Naming conventions check passed"
```

## Automation

### Automated Naming Module

```hcl
# modules/naming/main.tf
variable "environment" {
  type = string
}

variable "application" {
  type = string
}

variable "resource_type" {
  type = string
}

variable "identifier" {
  type = string
}

output "name" {
  value = "${var.environment}-${var.application}-${var.resource_type}-${var.identifier}"
}

# Usage
module "db_name" {
  source = "./modules/naming"

  environment   = "prod"
  application   = "api"
  resource_type = "db"
  identifier    = "primary"
}

resource "aws_db_instance" "primary" {
  identifier = module.db_name.name  # Results in: prod-api-db-primary
  # ... configuration ...
}
```

## Migration Strategy

### Renaming Existing Resources

**⚠️ Warning:** Renaming resources typically causes recreation

### Safe Migration Steps

1. **Create New Resource:** With correct name
2. **Migrate Data:** Copy data to new resource
3. **Update References:** Point applications to new resource
4. **Verify:** Test thoroughly
5. **Delete Old:** Remove old resource

### Example Migration

```hcl
# Step 1: Create new resource with correct name
resource "aws_db_instance" "primary_new" {
  identifier = "prod-api-db-primary"  # Correct name
  # ... same configuration as old ...

  lifecycle {
    prevent_destroy = true
  }
}

# Step 2: Keep old resource temporarily
resource "aws_db_instance" "primary_old" {
  identifier = "MyDatabase"  # Old name
  # ... configuration ...

  lifecycle {
    prevent_destroy = true
  }
}

# Step 3: After migration, remove old resource
```

## Exceptions

### Acceptable Deviations

1. **AWS-Managed Resources:** Default VPCs, CloudWatch log groups
2. **Legacy Resources:** Documented exceptions for existing resources
3. **Third-Party Integrations:** External naming requirements
4. **Compliance Requirements:** Specific naming mandated by regulations

### Exception Documentation

```hcl
resource "aws_db_instance" "legacy" {
  identifier = "OldDatabaseName"  # Legacy system

  tags = {
    NamingException = "true"
    ExceptionReason = "Legacy database, migration planned Q2 2024"
    ApprovedBy      = "architecture-team@company.com"
  }
}
```

## Benefits

### Operational Benefits

- **Faster Troubleshooting:** Identify resources quickly
- **Automated Operations:** Script operations by naming patterns
- **Cost Tracking:** Group costs by naming conventions
- **Security:** Identify sensitive resources by name

### Team Benefits

- **Onboarding:** New team members understand naming
- **Collaboration:** Consistent naming across teams
- **Documentation:** Self-documenting infrastructure
- **Reduced Errors:** Clear identification prevents mistakes

## References

- [AWS Resource Naming Best Practices](https://docs.aws.amazon.com/whitepapers/latest/tagging-best-practices/naming-your-resources.html)
- [S3 Bucket Naming Rules](https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucketnamingrules.html)
- [RDS DB Instance Naming](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_Limits.html)
- [Lambda Function Naming](https://docs.aws.amazon.com/lambda/latest/dg/API_CreateFunction.html)
- [Terraform Naming Conventions](https://www.terraform-best-practices.com/naming)
- [AWS Well-Architected Framework - Operational Excellence](https://docs.aws.amazon.com/wellarchitected/latest/operational-excellence-pillar/welcome.html)
