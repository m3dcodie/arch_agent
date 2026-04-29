# Allowed Regions Policy

## Policy ID

`allowed_regions`

## Severity

**MEDIUM**

## Description

All AWS resources MUST be deployed only in approved AWS regions to ensure compliance with data sovereignty requirements, regulatory constraints, and organizational standards. Deploying resources in unauthorized regions can violate data residency laws and create security, compliance, and operational risks.

## Scope

This policy applies to ALL AWS resources across all services.

## Requirements

1. **Approved Regions:** Resources must only be deployed in organization-approved regions
2. **Default Regions:** Typically limited to specific geographic areas
3. **Documentation:** Region selection must be documented and justified
4. **Exceptions:** Must be explicitly approved by security and compliance teams

### Example Approved Region Lists

**US-Only Organization:**

- `us-east-1` (N. Virginia)
- `us-east-2` (Ohio)
- `us-west-1` (N. California)
- `us-west-2` (Oregon)

**EU-Only Organization:**

- `eu-west-1` (Ireland)
- `eu-west-2` (London)
- `eu-central-1` (Frankfurt)

**Global Organization:**

- `us-east-1` (Primary)
- `us-west-2` (DR)
- `eu-west-1` (Europe)
- `ap-southeast-1` (Asia Pacific)

## Enforcement: Canonical Approved Region List

The following regions are the **only** approved regions for this organisation.
Any region NOT in this list is a **MEDIUM** severity violation:

```
us-east-1
us-east-2
us-west-1
us-west-2
eu-west-1
eu-west-2
eu-central-1
ap-southeast-1
ap-southeast-2
```

If a `provider` block specifies a `region` that is not in the list above, it MUST be flagged as a violation.

## Rationale

Region restrictions are critical for:

1. **Data Sovereignty:** Comply with GDPR, CCPA, and other data residency laws
2. **Regulatory Compliance:** Meet industry-specific requirements (HIPAA, PCI-DSS)
3. **Cost Optimization:** Avoid expensive regions
4. **Latency Management:** Deploy near users
5. **Disaster Recovery:** Control DR region placement
6. **Security:** Limit attack surface to known regions
7. **Operational Excellence:** Standardize on supported regions

## Examples

### ✅ Compliant - RDS in Approved Region (us-east-1)

```hcl
provider "aws" {
  region = "us-east-1"  # ✓ Approved region
}

resource "aws_db_instance" "production" {
  identifier           = "prod-database"
  engine               = "postgres"
  instance_class       = "db.r5.large"
  allocated_storage    = 100

  # Implicitly in us-east-1 (provider region)

  username = "admin"
  password = var.db_password

  tags = {
    Environment = "production"
    Region      = "us-east-1"
  }
}
```

### ✅ Compliant - Multi-Region with Approved Regions

```hcl
# Primary region (approved)
provider "aws" {
  alias  = "primary"
  region = "us-east-1"  # ✓ Approved
}

# DR region (approved)
provider "aws" {
  alias  = "dr"
  region = "us-west-2"  # ✓ Approved
}

resource "aws_db_instance" "primary" {
  provider = aws.primary

  identifier           = "prod-database-primary"
  engine               = "postgres"
  instance_class       = "db.r5.large"
  allocated_storage    = 100

  username = "admin"
  password = var.db_password

  tags = {
    Environment = "production"
    Region      = "us-east-1"
    Role        = "primary"
  }
}

resource "aws_db_instance" "dr" {
  provider = aws.dr

  identifier           = "prod-database-dr"
  replicate_source_db  = aws_db_instance.primary.arn
  instance_class       = "db.r5.large"

  tags = {
    Environment = "production"
    Region      = "us-west-2"
    Role        = "disaster-recovery"
  }
}
```

### ✅ Compliant - S3 Bucket in Approved Region

```hcl
provider "aws" {
  region = "us-east-1"
}

resource "aws_s3_bucket" "data" {
  bucket = "company-data-bucket"

  tags = {
    Environment = "production"
    Region      = "us-east-1"
  }
}

# Explicitly set bucket region
resource "aws_s3_bucket" "regional" {
  bucket = "company-regional-data"

  # S3 buckets inherit provider region

  tags = {
    Environment = "production"
    Region      = "us-east-1"
  }
}
```

### ✅ Compliant - Lambda in Approved Region

```hcl
provider "aws" {
  region = "us-east-1"  # ✓ Approved
}

resource "aws_lambda_function" "processor" {
  filename      = "lambda_function.zip"
  function_name = "prod-data-processor"
  role          = aws_iam_role.lambda.arn
  handler       = "index.handler"
  runtime       = "python3.11"

  tags = {
    Environment = "production"
    Region      = "us-east-1"
  }
}
```

### ✅ Compliant - EC2 with Explicit Region Check

```hcl
provider "aws" {
  region = "us-east-1"

  # Allowed regions validation
  allowed_account_ids = [var.aws_account_id]
}

data "aws_region" "current" {}

# Validate region at plan time
resource "null_resource" "region_check" {
  triggers = {
    region = data.aws_region.current.name
  }

  provisioner "local-exec" {
    command = <<-EOT
      if [[ ! "${data.aws_region.current.name}" =~ ^(us-east-1|us-west-2)$ ]]; then
        echo "ERROR: Region ${data.aws_region.current.name} is not approved"
        exit 1
      fi
    EOT
  }
}

resource "aws_instance" "app" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.large"

  depends_on = [null_resource.region_check]

  tags = {
    Name        = "prod-app-server"
    Environment = "production"
    Region      = data.aws_region.current.name
  }
}
```

### ❌ Non-Compliant - RDS in Unapproved Region

```hcl
provider "aws" {
  region = "ap-south-1"  # ✗ Not in approved list (Mumbai)
}

resource "aws_db_instance" "production" {
  identifier           = "prod-database"
  engine               = "postgres"
  instance_class       = "db.r5.large"
  allocated_storage    = 100

  username = "admin"
  password = var.db_password

  tags = {
    Environment = "production"
    Region      = "ap-south-1"  # ✗ Unapproved region
  }
}
```

### ❌ Non-Compliant - S3 in Restricted Region

```hcl
provider "aws" {
  region = "cn-north-1"  # ✗ China region (requires special account)
}

resource "aws_s3_bucket" "data" {
  bucket = "company-data-bucket"

  tags = {
    Environment = "production"
    Region      = "cn-north-1"  # ✗ Restricted region
  }
}
```

### ❌ Non-Compliant - Lambda in Non-Compliant Region

```hcl
provider "aws" {
  region = "eu-south-1"  # ✗ Milan - not approved for this org
}

resource "aws_lambda_function" "processor" {
  filename      = "lambda_function.zip"
  function_name = "prod-processor"
  role          = aws_iam_role.lambda.arn
  handler       = "index.handler"
  runtime       = "python3.11"

  tags = {
    Environment = "production"
    Region      = "eu-south-1"  # ✗ Unapproved
  }
}
```

### ❌ Non-Compliant - Multi-Region with Unapproved DR

```hcl
provider "aws" {
  alias  = "primary"
  region = "us-east-1"  # ✓ Approved
}

provider "aws" {
  alias  = "dr"
  region = "ap-northeast-1"  # ✗ Tokyo - not approved for DR
}

resource "aws_db_instance" "primary" {
  provider = aws.primary
  identifier = "prod-database-primary"
  # ... configuration ...
}

resource "aws_db_instance" "dr" {
  provider = aws.dr  # ✗ Using unapproved region
  identifier = "prod-database-dr"
  # ... configuration ...
}
```

### ❌ Non-Compliant - EC2 in GovCloud (Requires Special Access)

```hcl
provider "aws" {
  region = "us-gov-west-1"  # ✗ GovCloud requires special authorization
}

resource "aws_instance" "app" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.large"

  tags = {
    Environment = "production"
    Region      = "us-gov-west-1"  # ✗ Unauthorized GovCloud usage
  }
}
```

## Remediation

### Update Provider Region

```hcl
# Before (non-compliant)
provider "aws" {
  region = "ap-south-1"  # Unapproved
}

# After (compliant)
provider "aws" {
  region = "us-east-1"  # Approved
}
```

### Migrate Resources to Approved Region

**⚠️ Warning:** Cross-region migration requires careful planning

**Migration Steps:**

1. **Backup Data:** Create snapshots/backups
2. **Copy to Approved Region:** Use AWS services (S3 replication, DB snapshot copy)
3. **Recreate Resources:** Deploy in approved region
4. **Update DNS/Endpoints:** Point to new region
5. **Verify:** Test thoroughly
6. **Decommission Old:** Remove resources from unapproved region

### Example: RDS Cross-Region Migration

```hcl
# Step 1: Create snapshot in source region
resource "aws_db_snapshot" "migration" {
  provider               = aws.source
  db_instance_identifier = aws_db_instance.old.id
  db_snapshot_identifier = "migration-snapshot-${formatdate("YYYY-MM-DD", timestamp())}"
}

# Step 2: Copy snapshot to target region
resource "aws_db_snapshot_copy" "target" {
  provider                  = aws.target
  source_db_snapshot_identifier = aws_db_snapshot.migration.db_snapshot_arn
  target_db_snapshot_identifier = "migration-snapshot-copy"

  kms_key_id = aws_kms_key.target_region.arn  # Re-encrypt with target region key
}

# Step 3: Restore in target region
resource "aws_db_instance" "new" {
  provider            = aws.target
  identifier          = "prod-database-new"
  snapshot_identifier = aws_db_snapshot_copy.target.id
  instance_class      = "db.r5.large"

  tags = {
    Environment = "production"
    Region      = "us-east-1"
    MigratedFrom = "ap-south-1"
    MigrationDate = formatdate("YYYY-MM-DD", timestamp())
  }
}
```

## Enforcement Strategies

### 1. Terraform Validation

```hcl
# variables.tf
variable "allowed_regions" {
  description = "List of approved AWS regions"
  type        = list(string)
  default     = ["us-east-1", "us-west-2"]
}

variable "aws_region" {
  description = "AWS region for resources"
  type        = string

  validation {
    condition     = contains(var.allowed_regions, var.aws_region)
    error_message = "Region must be one of: ${join(", ", var.allowed_regions)}."
  }
}

provider "aws" {
  region = var.aws_region
}
```

### 2. AWS Organizations Service Control Policy (SCP)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyUnapprovedRegions",
      "Effect": "Deny",
      "Action": "*",
      "Resource": "*",
      "Condition": {
        "StringNotEquals": {
          "aws:RequestedRegion": ["us-east-1", "us-west-2"]
        }
      }
    }
  ]
}
```

### 3. AWS Config Rule

```hcl
resource "aws_config_config_rule" "approved_regions" {
  name = "approved-regions-only"

  source {
    owner             = "AWS"
    source_identifier = "APPROVED_AMIS_BY_TAG"
  }

  input_parameters = jsonencode({
    approvedRegions = "us-east-1,us-west-2"
  })
}
```

### 4. Pre-Commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-commit

ALLOWED_REGIONS="us-east-1 us-west-2"

# Check for unapproved regions in Terraform files
for region in $(git diff --cached --name-only | grep -E '\.tf$' | xargs grep -h 'region.*=' | grep -oP '(?<=region = ")[^"]+'); do
  if [[ ! " ${ALLOWED_REGIONS} " =~ " ${region} " ]]; then
    echo "ERROR: Unapproved region detected: ${region}"
    echo "Allowed regions: ${ALLOWED_REGIONS}"
    exit 1
  fi
done

echo "Region validation passed"
```

### 5. Terraform Module with Region Lock

```hcl
# modules/region-lock/main.tf
variable "allowed_regions" {
  type = list(string)
}

data "aws_region" "current" {}

resource "null_resource" "region_validation" {
  triggers = {
    region = data.aws_region.current.name
  }

  provisioner "local-exec" {
    command = <<-EOT
      ALLOWED="${join(" ", var.allowed_regions)}"
      CURRENT="${data.aws_region.current.name}"

      if [[ ! " $ALLOWED " =~ " $CURRENT " ]]; then
        echo "ERROR: Region $CURRENT is not in allowed list: $ALLOWED"
        exit 1
      fi

      echo "✓ Region $CURRENT is approved"
    EOT
  }
}

output "validated_region" {
  value = data.aws_region.current.name
  depends_on = [null_resource.region_validation]
}

# Usage
module "region_check" {
  source = "./modules/region-lock"

  allowed_regions = ["us-east-1", "us-west-2"]
}
```

## Region Selection Criteria

### Factors to Consider

| Factor                   | Considerations                                     |
| ------------------------ | -------------------------------------------------- |
| **Data Sovereignty**     | GDPR (EU), CCPA (California), local data laws      |
| **Latency**              | Proximity to users/customers                       |
| **Cost**                 | Regional pricing variations (up to 30% difference) |
| **Service Availability** | Not all services in all regions                    |
| **Disaster Recovery**    | Geographic separation for DR                       |
| **Compliance**           | Industry-specific requirements                     |
| **Operational Support**  | Team timezone alignment                            |

### Regional Cost Comparison (Example)

| Region     | EC2 t3.large | RDS db.r5.large | S3 Storage |
| ---------- | ------------ | --------------- | ---------- |
| us-east-1  | $0.0832/hr   | $0.29/hr        | $0.023/GB  |
| us-west-2  | $0.0832/hr   | $0.29/hr        | $0.023/GB  |
| eu-west-1  | $0.0928/hr   | $0.322/hr       | $0.023/GB  |
| ap-south-1 | $0.0776/hr   | $0.27/hr        | $0.023/GB  |

## Common Region Strategies

### Strategy 1: Single Region (Simplest)

```hcl
# All resources in one region
provider "aws" {
  region = "us-east-1"
}
```

**Pros:** Simple, low cost, easy management  
**Cons:** No geographic redundancy, single point of failure

### Strategy 2: Primary + DR (Recommended)

```hcl
provider "aws" {
  alias  = "primary"
  region = "us-east-1"
}

provider "aws" {
  alias  = "dr"
  region = "us-west-2"
}
```

**Pros:** Disaster recovery, geographic redundancy  
**Cons:** Higher cost, more complex

### Strategy 3: Multi-Region Active-Active

```hcl
provider "aws" {
  alias  = "us"
  region = "us-east-1"
}

provider "aws" {
  alias  = "eu"
  region = "eu-west-1"
}

provider "aws" {
  alias  = "apac"
  region = "ap-southeast-1"
}
```

**Pros:** Low latency globally, high availability  
**Cons:** Most expensive, most complex

## Exceptions

### Acceptable Unapproved Region Usage

1. **Global Services:** CloudFront, Route53, IAM (region-agnostic)
2. **Temporary Testing:** Short-lived proof-of-concepts (< 7 days)
3. **Service Requirements:** Some services only available in specific regions
4. **Customer Requirements:** Contractual obligations for specific regions
5. **Compliance Testing:** Validating multi-region compliance

### Exception Documentation

```hcl
provider "aws" {
  alias  = "exception"
  region = "ap-northeast-1"  # Tokyo - exception
}

resource "aws_db_instance" "customer_requirement" {
  provider = aws.exception

  identifier = "customer-japan-db"
  # ... configuration ...

  tags = {
    Environment     = "production"
    Region          = "ap-northeast-1"
    RegionException = "true"
    ExceptionReason = "Customer contractual requirement for Japan data residency"
    ApprovedBy      = "legal-team@company.com"
    ApprovalDate    = "2024-01-15"
    ReviewDate      = "2024-07-15"
    CustomerName    = "Acme Japan KK"
  }
}
```

## Monitoring and Compliance

### CloudWatch Events for Unauthorized Regions

```hcl
resource "aws_cloudwatch_event_rule" "unauthorized_region" {
  name        = "detect-unauthorized-region-usage"
  description = "Alert on resource creation in unauthorized regions"

  event_pattern = jsonencode({
    detail-type = ["AWS API Call via CloudTrail"]
    detail = {
      eventName = ["RunInstances", "CreateDBInstance", "CreateBucket"]
      awsRegion = [{
        "anything-but": ["us-east-1", "us-west-2"]
      }]
    }
  })
}

resource "aws_cloudwatch_event_target" "sns" {
  rule      = aws_cloudwatch_event_rule.unauthorized_region.name
  target_id = "SendToSNS"
  arn       = aws_sns_topic.security_alerts.arn
}
```

### Compliance Report Script

```bash
#!/bin/bash
# Check all resources across regions

ALLOWED_REGIONS="us-east-1 us-west-2"
ALL_REGIONS=$(aws ec2 describe-regions --query 'Regions[].RegionName' --output text)

echo "Region Compliance Report"
echo "========================"
echo "Allowed Regions: $ALLOWED_REGIONS"
echo ""

for region in $ALL_REGIONS; do
  # Check if region is allowed
  if [[ ! " $ALLOWED_REGIONS " =~ " $region " ]]; then
    # Count resources in unapproved region
    ec2_count=$(aws ec2 describe-instances --region $region --query 'length(Reservations[].Instances[])' --output text 2>/dev/null || echo "0")
    rds_count=$(aws rds describe-db-instances --region $region --query 'length(DBInstances)' --output text 2>/dev/null || echo "0")

    if [ "$ec2_count" != "0" ] || [ "$rds_count" != "0" ]; then
      echo "⚠️  VIOLATION: Resources found in unapproved region $region"
      echo "   EC2 Instances: $ec2_count"
      echo "   RDS Instances: $rds_count"
    fi
  fi
done
```

## References

- [AWS Regions and Availability Zones](https://aws.amazon.com/about-aws/global-infrastructure/regions_az/)
- [AWS Service Control Policies](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_scps.html)
- [GDPR Data Residency Requirements](https://gdpr-info.eu/)
- [AWS Regional Services List](https://aws.amazon.com/about-aws/global-infrastructure/regional-product-services/)
- [Terraform AWS Provider Configuration](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [AWS Well-Architected Framework - Reliability](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/plan-for-disaster-recovery-dr.html)
- [AWS China Regions](https://www.amazonaws.cn/en/about-aws/regional-product-services/)
- [AWS GovCloud](https://aws.amazon.com/govcloud-us/)
