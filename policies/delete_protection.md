# Deletion Protection Policy

## Policy ID
`delete_protection`

## Severity
**HIGH**

## Description
All production database instances MUST have deletion protection enabled to prevent accidental deletion of critical data infrastructure.

## Scope
This policy applies to the following AWS resources:
- `aws_db_instance` (RDS Database Instances)
- `aws_rds_cluster` (Aurora Clusters)
- `aws_db_cluster_instance` (Aurora Cluster Instances)

## Requirements
The `deletion_protection` attribute must be explicitly set to `true` for all database resources.

## Rationale
Deletion protection is a critical safety mechanism that:
1. Prevents accidental deletion of production databases
2. Requires explicit action to disable before deletion
3. Protects against human error and automation mistakes
4. Ensures compliance with data retention policies

## Examples

### ✅ Compliant
```hcl
resource "aws_db_instance" "main" {
  identifier           = "production-db"
  engine               = "postgres"
  instance_class       = "db.t3.micro"
  
  deletion_protection = true  # ✓ Compliant
}
```

### ❌ Non-Compliant
```hcl
resource "aws_db_instance" "main" {
  identifier           = "production-db"
  engine               = "postgres"
  instance_class       = "db.t3.micro"
  
  # ✗ Missing deletion_protection
}
```

```hcl
resource "aws_db_instance" "main" {
  identifier           = "production-db"
  engine               = "postgres"
  instance_class       = "db.t3.micro"
  
  deletion_protection = false  # ✗ Explicitly disabled
}
```

## Remediation
Add the following attribute to your database resource:
```hcl
deletion_protection = true
```

## Exceptions
None. This policy applies to all database resources without exception.

## References
- [AWS RDS Deletion Protection Documentation](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_DeleteInstance.html)
- [Terraform aws_db_instance Documentation](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/db_instance)
