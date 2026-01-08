# Required Tagging Policy

## Policy ID
`required_tagging`

## Severity
**LOW**

## Description
All AWS resources MUST have a minimum set of required tags for cost allocation, resource management, and operational tracking. Consistent tagging enables financial accountability, automated operations, and compliance reporting.

## Scope
This policy applies to ALL AWS resources that support tagging, including but not limited to:
- `aws_db_instance` (RDS Database Instances)
- `aws_rds_cluster` (Aurora Clusters)
- `aws_s3_bucket` (S3 Buckets)
- `aws_ec2_instance` (EC2 Instances)
- `aws_ebs_volume` (EBS Volumes)
- `aws_vpc` (VPCs)
- `aws_security_group` (Security Groups)
- `aws_lambda_function` (Lambda Functions)
- `aws_dynamodb_table` (DynamoDB Tables)
- And all other taggable resources

## Requirements

### Mandatory Tags (All Resources)
1. **Environment:** `production`, `staging`, `development`, `testing`
2. **Owner:** Email or team identifier
3. **Application:** Application or service name
4. **CostCenter:** Cost center code for billing

### Recommended Tags
5. **ManagedBy:** `terraform`, `cloudformation`, `manual`
6. **Project:** Project identifier
7. **Compliance:** Compliance framework if applicable
8. **DataClassification:** `public`, `internal`, `confidential`, `restricted`

## Rationale
Consistent tagging is critical for:
1. **Cost Allocation:** Track spending by team, project, or environment
2. **Resource Management:** Identify ownership and purpose
3. **Automation:** Enable automated operations (backup, patching, cleanup)
4. **Compliance:** Meet audit and regulatory requirements
5. **Security:** Identify sensitive resources
6. **Operational Excellence:** Troubleshooting and incident response
7. **Financial Accountability:** Chargeback and showback reporting

## Examples

### ✅ Compliant - RDS with All Required Tags
```hcl
resource "aws_db_instance" "production" {
  identifier           = "prod-database"
  engine               = "postgres"
  instance_class       = "db.r5.large"
  allocated_storage    = 100
  
  username = "admin"
  password = var.db_password
  
  tags = {
    Environment        = "production"  # ✓ Required
    Owner              = "data-team@company.com"  # ✓ Required
    Application        = "core-api"  # ✓ Required
    CostCenter         = "CC-1234"  # ✓ Required
    ManagedBy          = "terraform"  # ✓ Recommended
    Project            = "customer-portal"
    DataClassification = "confidential"
  }
}
```

### ✅ Compliant - S3 Bucket with Required Tags
```hcl
resource "aws_s3_bucket" "data" {
  bucket = "company-data-bucket"
  
  tags = {
    Environment = "production"  # ✓ Required
    Owner       = "analytics-team@company.com"  # ✓ Required
    Application = "data-warehouse"  # ✓ Required
    CostCenter  = "CC-5678"  # ✓ Required
    ManagedBy   = "terraform"
    Compliance  = "GDPR"
  }
}
```

### ✅ Compliant - EC2 Instance with Comprehensive Tags
```hcl
resource "aws_instance" "app_server" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.large"
  
  tags = {
    Name               = "app-server-01"  # ✓ Name tag
    Environment        = "production"  # ✓ Required
    Owner              = "platform-team@company.com"  # ✓ Required
    Application        = "web-application"  # ✓ Required
    CostCenter         = "CC-9012"  # ✓ Required
    ManagedBy          = "terraform"
    Project            = "ecommerce-platform"
    BackupSchedule     = "daily"
    PatchGroup         = "production-group-1"
    DataClassification = "internal"
  }
}
```

### ✅ Compliant - Lambda Function with Tags
```hcl
resource "aws_lambda_function" "processor" {
  filename      = "lambda_function.zip"
  function_name = "data-processor"
  role          = aws_iam_role.lambda.arn
  handler       = "index.handler"
  runtime       = "python3.11"
  
  tags = {
    Environment = "production"  # ✓ Required
    Owner       = "data-engineering@company.com"  # ✓ Required
    Application = "data-pipeline"  # ✓ Required
    CostCenter  = "CC-3456"  # ✓ Required
    ManagedBy   = "terraform"
  }
}
```

### ✅ Compliant - VPC with Tags
```hcl
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
  
  tags = {
    Name        = "production-vpc"
    Environment = "production"  # ✓ Required
    Owner       = "network-team@company.com"  # ✓ Required
    Application = "infrastructure"  # ✓ Required
    CostCenter  = "CC-0001"  # ✓ Required
    ManagedBy   = "terraform"
  }
}
```

### ❌ Non-Compliant - RDS Missing All Tags
```hcl
resource "aws_db_instance" "production" {
  identifier           = "prod-database"
  engine               = "postgres"
  instance_class       = "db.r5.large"
  allocated_storage    = 100
  
  username = "admin"
  password = var.db_password
  
  # ✗ No tags defined at all
}
```

### ❌ Non-Compliant - S3 Bucket Missing Required Tags
```hcl
resource "aws_s3_bucket" "data" {
  bucket = "company-data-bucket"
  
  tags = {
    Environment = "production"  # Has Environment
    # ✗ Missing Owner
    # ✗ Missing Application
    # ✗ Missing CostCenter
  }
}
```

### ❌ Non-Compliant - EC2 with Incomplete Tags
```hcl
resource "aws_instance" "app_server" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.large"
  
  tags = {
    Name        = "app-server-01"
    Environment = "production"  # Has Environment
    Owner       = "platform-team@company.com"  # Has Owner
    # ✗ Missing Application
    # ✗ Missing CostCenter
  }
}
```

### ❌ Non-Compliant - Lambda with Invalid Tag Values
```hcl
resource "aws_lambda_function" "processor" {
  filename      = "lambda_function.zip"
  function_name = "data-processor"
  role          = aws_iam_role.lambda.arn
  handler       = "index.handler"
  runtime       = "python3.11"
  
  tags = {
    Environment = "prod-env"  # ✗ Invalid value (should be "production")
    Owner       = "data team"  # ✗ Invalid format (should be email)
    Application = ""  # ✗ Empty value
    CostCenter  = "unknown"  # ✗ Invalid cost center code
  }
}
```

### ❌ Non-Compliant - DynamoDB with Partial Tags
```hcl
resource "aws_dynamodb_table" "users" {
  name           = "users-table"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "user_id"

  attribute {
    name = "user_id"
    type = "S"
  }

  tags = {
    Environment = "production"
    Application = "user-service"
    # ✗ Missing Owner
    # ✗ Missing CostCenter
  }
}
```

### ❌ Non-Compliant - Security Group with No Tags
```hcl
resource "aws_security_group" "app" {
  name        = "app-security-group"
  description = "Security group for application"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"]
  }
  
  # ✗ No tags block defined
}
```

### ❌ Non-Compliant - EBS Volume with Minimal Tags
```hcl
resource "aws_ebs_volume" "data" {
  availability_zone = "us-east-1a"
  size              = 100
  type              = "gp3"
  
  tags = {
    Name = "data-volume"
    # ✗ Missing all required tags
  }
}
```

## Remediation

### Add Required Tags to Resources
```hcl
tags = {
  Environment = "production"  # or "staging", "development", "testing"
  Owner       = "team-email@company.com"
  Application = "application-name"
  CostCenter  = "CC-XXXX"
  ManagedBy   = "terraform"
}
```

### Use Terraform Variables for Consistency
```hcl
variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default = {
    ManagedBy  = "terraform"
    Project    = "customer-portal"
    CostCenter = "CC-1234"
  }
}

resource "aws_db_instance" "production" {
  identifier = "prod-database"
  # ... other configuration ...
  
  tags = merge(
    var.common_tags,
    {
      Environment = "production"
      Owner       = "data-team@company.com"
      Application = "core-api"
    }
  )
}
```

### Use Terraform Modules with Default Tags
```hcl
# In terraform.tf or provider.tf
provider "aws" {
  region = "us-east-1"
  
  default_tags {
    tags = {
      ManagedBy  = "terraform"
      Project    = var.project_name
      CostCenter = var.cost_center
    }
  }
}

# Resources automatically inherit default tags
resource "aws_db_instance" "production" {
  identifier = "prod-database"
  # ... configuration ...
  
  # Only need to add resource-specific tags
  tags = {
    Environment = "production"
    Owner       = "data-team@company.com"
    Application = "core-api"
  }
}
```

## Tag Value Standards

### Environment Tag Values
- **Allowed:** `production`, `staging`, `development`, `testing`, `sandbox`
- **Not Allowed:** `prod`, `dev`, `test`, `stg` (use full names)

### Owner Tag Format
- **Format:** Valid email address or team identifier
- **Examples:** 
  - ✓ `data-team@company.com`
  - ✓ `platform-engineering@company.com`
  - ✗ `john` (not specific enough)
  - ✗ `data team` (use email)

### Application Tag Format
- **Format:** Lowercase, hyphen-separated
- **Examples:**
  - ✓ `core-api`
  - ✓ `user-service`
  - ✓ `data-warehouse`
  - ✗ `Core API` (no spaces or capitals)

### CostCenter Tag Format
- **Format:** `CC-` followed by 4 digits
- **Examples:**
  - ✓ `CC-1234`
  - ✓ `CC-0001`
  - ✗ `1234` (missing prefix)
  - ✗ `CC-12` (insufficient digits)

## Automation and Enforcement

### AWS Config Rule for Tag Compliance
```hcl
resource "aws_config_config_rule" "required_tags" {
  name = "required-tags-check"

  source {
    owner             = "AWS"
    source_identifier = "REQUIRED_TAGS"
  }

  input_parameters = jsonencode({
    tag1Key = "Environment"
    tag2Key = "Owner"
    tag3Key = "Application"
    tag4Key = "CostCenter"
  })

  depends_on = [aws_config_configuration_recorder.main]
}
```

### Tag Policy (AWS Organizations)
```json
{
  "tags": {
    "Environment": {
      "tag_key": {
        "@@assign": "Environment"
      },
      "tag_value": {
        "@@assign": [
          "production",
          "staging",
          "development",
          "testing"
        ]
      },
      "enforced_for": {
        "@@assign": [
          "ec2:instance",
          "rds:db",
          "s3:bucket"
        ]
      }
    }
  }
}
```

### Terraform Validation
```hcl
# In a custom validation module
variable "tags" {
  type = map(string)
  
  validation {
    condition = (
      contains(keys(var.tags), "Environment") &&
      contains(keys(var.tags), "Owner") &&
      contains(keys(var.tags), "Application") &&
      contains(keys(var.tags), "CostCenter")
    )
    error_message = "Tags must include Environment, Owner, Application, and CostCenter."
  }
  
  validation {
    condition = contains(
      ["production", "staging", "development", "testing"],
      lookup(var.tags, "Environment", "")
    )
    error_message = "Environment must be one of: production, staging, development, testing."
  }
}
```

## Cost Allocation Benefits

### Monthly Cost Report by Tag
```sql
-- AWS Cost Explorer Query
SELECT 
  user:Environment,
  user:Application,
  user:CostCenter,
  SUM(line_item_unblended_cost) as total_cost
FROM 
  cost_and_usage_report
WHERE 
  line_item_usage_start_date >= '2024-01-01'
GROUP BY 
  user:Environment,
  user:Application,
  user:CostCenter
ORDER BY 
  total_cost DESC;
```

### Cost Savings from Tagging
- **Identify Orphaned Resources:** Find resources without owners
- **Environment Optimization:** Right-size dev/test environments
- **Chargeback Accuracy:** Allocate costs to correct teams
- **Budget Alerts:** Set budgets by application or cost center

## Operational Benefits

### Automated Operations by Tag
```bash
# Stop all development EC2 instances at night
aws ec2 stop-instances \
  --instance-ids $(aws ec2 describe-instances \
    --filters "Name=tag:Environment,Values=development" \
              "Name=instance-state-name,Values=running" \
    --query 'Reservations[].Instances[].InstanceId' \
    --output text)

# Backup all production databases
aws rds describe-db-instances \
  --query 'DBInstances[?Tags[?Key==`Environment` && Value==`production`]].DBInstanceIdentifier' \
  --output text | xargs -I {} aws rds create-db-snapshot \
  --db-instance-identifier {} \
  --db-snapshot-identifier {}-$(date +%Y%m%d)
```

### Resource Inventory by Tags
```bash
# List all resources by application
aws resourcegroupstaggingapi get-resources \
  --tag-filters Key=Application,Values=core-api \
  --query 'ResourceTagMappingList[].ResourceARN'
```

## Exceptions

### Resources That May Not Need All Tags
1. **Terraform State Buckets:** Infrastructure-only resources
2. **CloudWatch Log Groups:** Auto-created by services
3. **Default VPC Resources:** AWS-managed defaults
4. **Temporary Test Resources:** Short-lived (< 24 hours)

### Exception Documentation
```hcl
resource "aws_s3_bucket" "terraform_state" {
  bucket = "company-terraform-state"
  
  tags = {
    Purpose     = "terraform-state"
    ManagedBy   = "terraform"
    Environment = "infrastructure"
    # Minimal tags acceptable for infrastructure resources
  }
}
```

## Compliance Mapping

### Regulatory Requirements
| Framework | Tagging Requirement |
|-----------|---------------------|
| **SOC 2** | Asset inventory and ownership |
| **ISO 27001** | Asset management and classification |
| **PCI-DSS** | System component inventory |
| **NIST** | Asset identification and tracking |

## Monitoring and Reporting

### CloudWatch Dashboard for Untagged Resources
```hcl
resource "aws_cloudwatch_dashboard" "tagging_compliance" {
  dashboard_name = "tagging-compliance"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/Config", "ComplianceScore", { stat = "Average" }]
          ]
          period = 300
          stat   = "Average"
          region = "us-east-1"
          title  = "Tag Compliance Score"
        }
      }
    ]
  })
}
```

### Weekly Compliance Report
```bash
#!/bin/bash
# Generate weekly tagging compliance report

echo "Tagging Compliance Report - $(date)"
echo "======================================"

# Count untagged resources
UNTAGGED=$(aws resourcegroupstaggingapi get-resources \
  --query 'length(ResourceTagMappingList[?Tags==`[]`])' \
  --output text)

echo "Untagged Resources: $UNTAGGED"

# List resources missing required tags
aws resourcegroupstaggingapi get-resources \
  --query 'ResourceTagMappingList[?!Tags[?Key==`Environment`]]' \
  --output table
```

## References
- [AWS Tagging Best Practices](https://docs.aws.amazon.com/general/latest/gr/aws_tagging.html)
- [AWS Tag Policies](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_tag-policies.html)
- [AWS Config Required Tags Rule](https://docs.aws.amazon.com/config/latest/developerguide/required-tags.html)
- [AWS Cost Allocation Tags](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/cost-alloc-tags.html)
- [Terraform Default Tags](https://www.terraform.io/language/providers/configuration#default_tags)
- [AWS Well-Architected Framework - Cost Optimization](https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/tagging.html)
