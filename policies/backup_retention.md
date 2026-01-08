# Backup Retention Policy

## Policy ID
`backup_retention`

## Severity
**MEDIUM**

## Description
All production database resources MUST have automated backups enabled with a minimum retention period of 7 days. This ensures point-in-time recovery capability and protects against data loss, corruption, or accidental deletion.

## Scope
This policy applies to the following AWS resources:
- `aws_db_instance` (RDS Database Instances)
- `aws_rds_cluster` (Aurora Clusters)
- `aws_dynamodb_table` (DynamoDB Tables with PITR)
- `aws_redshift_cluster` (Redshift Clusters)
- `aws_docdb_cluster` (DocumentDB Clusters)

## Requirements
1. **RDS Instances:** `backup_retention_period >= 7` days (production: 30 days recommended)
2. **Aurora Clusters:** `backup_retention_period >= 7` days
3. **DynamoDB:** `point_in_time_recovery.enabled = true`
4. **Redshift:** `automated_snapshot_retention_period >= 7` days
5. **DocumentDB:** `backup_retention_period >= 7` days

**Context-Aware:** Minimum 7 days for production, 1 day acceptable for non-production

## Rationale
Backup retention is critical for:
1. **Disaster Recovery:** Recover from hardware failures, corruption, or disasters
2. **Point-in-Time Recovery:** Restore to any point within retention window
3. **Compliance:** Many regulations require 7-30 day retention
4. **Human Error Protection:** Recover from accidental deletions or bad updates
5. **Ransomware Protection:** Restore clean data before attack
6. **Cost of Data Loss:** Average $3.86M per data breach (IBM 2023)

## Examples

### ✅ Compliant - RDS with 30-Day Retention
```hcl
resource "aws_db_instance" "production" {
  identifier           = "prod-database"
  engine               = "postgres"
  engine_version       = "14.7"
  instance_class       = "db.r5.large"
  allocated_storage    = 100
  
  backup_retention_period = 30  # ✓ 30 days for production
  backup_window          = "03:00-04:00"  # ✓ Backup window defined
  
  username = "admin"
  password = var.db_password
  
  tags = {
    Environment = "production"
  }
}
```

### ✅ Compliant - Aurora with 14-Day Retention
```hcl
resource "aws_rds_cluster" "production" {
  cluster_identifier = "prod-aurora-cluster"
  engine             = "aurora-postgresql"
  engine_version     = "14.6"
  database_name      = "mydb"
  master_username    = "admin"
  master_password    = var.db_password
  
  backup_retention_period = 14  # ✓ 14 days retention
  preferred_backup_window = "03:00-04:00"
  
  tags = {
    Environment = "production"
  }
}
```

### ✅ Compliant - DynamoDB with PITR
```hcl
resource "aws_dynamodb_table" "users" {
  name           = "users-table"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "user_id"

  attribute {
    name = "user_id"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true  # ✓ PITR enabled (35 days retention)
  }
  
  tags = {
    Environment = "production"
  }
}
```

### ✅ Compliant - Redshift with Automated Snapshots
```hcl
resource "aws_redshift_cluster" "analytics" {
  cluster_identifier = "prod-analytics"
  database_name      = "analytics"
  master_username    = "admin"
  master_password    = var.redshift_password
  node_type          = "dc2.large"
  cluster_type       = "multi-node"
  number_of_nodes    = 2
  
  automated_snapshot_retention_period = 35  # ✓ 35 days retention
  preferred_maintenance_window        = "sun:05:00-sun:06:00"
  
  tags = {
    Environment = "production"
  }
}
```

### ✅ Compliant - DocumentDB with Backups
```hcl
resource "aws_docdb_cluster" "documents" {
  cluster_identifier     = "prod-docdb"
  engine                 = "docdb"
  master_username        = "admin"
  master_password        = var.docdb_password
  
  backup_retention_period = 7  # ✓ 7 days minimum
  preferred_backup_window = "02:00-03:00"
  
  tags = {
    Environment = "production"
  }
}
```

### ✅ Compliant - Development Database (Lower Retention)
```hcl
resource "aws_db_instance" "development" {
  identifier           = "dev-database"
  engine               = "postgres"
  instance_class       = "db.t3.medium"
  allocated_storage    = 20
  
  backup_retention_period = 1  # ✓ Acceptable for development
  
  username = "admin"
  password = var.db_password
  
  tags = {
    Environment = "development"
  }
}
```

### ❌ Non-Compliant - Production RDS with No Backups
```hcl
resource "aws_db_instance" "production" {
  identifier           = "prod-database"
  engine               = "mysql"
  instance_class       = "db.t3.large"
  allocated_storage    = 100
  
  backup_retention_period = 0  # ✗ Backups disabled
  
  username = "admin"
  password = var.db_password
  
  tags = {
    Environment = "production"
  }
}
```

### ❌ Non-Compliant - Production RDS with Insufficient Retention
```hcl
resource "aws_db_instance" "production" {
  identifier           = "prod-database"
  engine               = "postgres"
  instance_class       = "db.r5.xlarge"
  allocated_storage    = 500
  
  backup_retention_period = 3  # ✗ Less than 7 days for production
  
  username = "admin"
  password = var.db_password
  
  tags = {
    Environment = "prod"
  }
}
```

### ❌ Non-Compliant - RDS Missing backup_retention_period
```hcl
resource "aws_db_instance" "production" {
  identifier           = "prod-database"
  engine               = "postgres"
  instance_class       = "db.r5.large"
  allocated_storage    = 200
  
  # ✗ Missing backup_retention_period (defaults to 1 day)
  
  username = "admin"
  password = var.db_password
  
  tags = {
    Environment = "production"
  }
}
```

### ❌ Non-Compliant - Aurora with Minimal Retention
```hcl
resource "aws_rds_cluster" "production" {
  cluster_identifier = "prod-aurora"
  engine             = "aurora-mysql"
  master_username    = "admin"
  master_password    = var.db_password
  
  backup_retention_period = 1  # ✗ Only 1 day for production
  
  tags = {
    Environment = "production"
  }
}
```

### ❌ Non-Compliant - DynamoDB without PITR
```hcl
resource "aws_dynamodb_table" "users" {
  name           = "users-table"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "user_id"

  attribute {
    name = "user_id"
    type = "S"
  }

  # ✗ No point_in_time_recovery block
  
  tags = {
    Environment = "production"
  }
}
```

### ❌ Non-Compliant - DynamoDB with PITR Disabled
```hcl
resource "aws_dynamodb_table" "orders" {
  name           = "orders-table"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "order_id"

  attribute {
    name = "order_id"
    type = "S"
  }

  point_in_time_recovery {
    enabled = false  # ✗ PITR explicitly disabled
  }
  
  tags = {
    Environment = "production"
  }
}
```

### ❌ Non-Compliant - Redshift with No Automated Snapshots
```hcl
resource "aws_redshift_cluster" "analytics" {
  cluster_identifier = "prod-analytics"
  database_name      = "analytics"
  master_username    = "admin"
  master_password    = var.redshift_password
  node_type          = "dc2.large"
  
  automated_snapshot_retention_period = 0  # ✗ Automated snapshots disabled
  
  tags = {
    Environment = "production"
  }
}
```

## Remediation

### For RDS Instances
Set appropriate backup retention:
```hcl
backup_retention_period = 30  # 30 days for production
backup_window          = "03:00-04:00"  # Off-peak hours
```

**Note:** Changing retention period does not cause downtime

### For Aurora Clusters
Enable backup retention:
```hcl
backup_retention_period = 14  # 14 days minimum
preferred_backup_window = "03:00-04:00"
```

### For DynamoDB
Enable point-in-time recovery:
```hcl
point_in_time_recovery {
  enabled = true  # Provides 35 days of continuous backups
}
```

**Note:** PITR can be enabled on existing tables without downtime

### For Redshift
Enable automated snapshots:
```hcl
automated_snapshot_retention_period = 35  # 35 days recommended
preferred_maintenance_window        = "sun:05:00-sun:06:00"
```

### For DocumentDB
Set backup retention:
```hcl
backup_retention_period = 7  # 7 days minimum
preferred_backup_window = "02:00-03:00"
```

## Retention Period Recommendations

### By Environment
| Environment | Minimum | Recommended | Maximum |
|-------------|---------|-------------|---------|
| Production | 7 days | 30 days | 35 days |
| Staging | 3 days | 7 days | 14 days |
| Development | 1 day | 1 day | 7 days |
| Testing | 0-1 day | 1 day | 3 days |

### By Data Sensitivity
| Data Classification | Retention Period |
|---------------------|------------------|
| Critical (PII, Financial) | 30-35 days |
| Sensitive (Business Data) | 14-30 days |
| Internal (Logs, Metrics) | 7-14 days |
| Public (Non-sensitive) | 1-7 days |

### By Compliance Framework
| Framework | Requirement |
|-----------|-------------|
| PCI-DSS | 90 days (use manual snapshots beyond 35) |
| HIPAA | 6 years (use manual snapshots + archival) |
| SOC 2 | 7-30 days (automated) |
| GDPR | Varies by data retention policy |

## Cost Considerations

### RDS Backup Storage Costs
- **Free Tier:** Backup storage = allocated storage (e.g., 100GB DB = 100GB free backup)
- **Additional Storage:** $0.095/GB-month (us-east-1)
- **Example:** 500GB DB with 30-day retention ≈ 500GB backups = Free

### DynamoDB PITR Costs
- **Cost:** Approximately equal to table size
- **Example:** 100GB table = ~$100/month for PITR
- **Benefit:** Continuous backups, no backup windows

### Redshift Snapshot Costs
- **Free Tier:** Backup storage = cluster size
- **Additional Storage:** $0.024/GB-month
- **Example:** 2TB cluster with 35-day retention ≈ 2TB backups = Free

## Backup Testing

### Regular Restore Testing
Test backup restoration quarterly:
```hcl
# Create test restore from backup
resource "aws_db_instance" "restore_test" {
  identifier = "restore-test-${formatdate("YYYY-MM-DD", timestamp())}"
  
  # Restore from snapshot
  snapshot_identifier = data.aws_db_snapshot.latest.id
  
  instance_class = "db.t3.small"  # Smaller instance for testing
  
  tags = {
    Purpose = "backup-restore-test"
    TestDate = formatdate("YYYY-MM-DD", timestamp())
  }
}
```

### Automated Backup Verification
```hcl
resource "aws_cloudwatch_metric_alarm" "backup_failure" {
  alarm_name          = "rds-backup-failure"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "BackupRetentionPeriodStorageUsed"
  namespace           = "AWS/RDS"
  period              = "86400"  # 24 hours
  statistic           = "Average"
  threshold           = "1"
  alarm_description   = "Alert when backups are not being created"
  
  dimensions = {
    DBInstanceIdentifier = aws_db_instance.production.id
  }
}
```

## Recovery Time Objectives (RTO)

### RDS/Aurora
- **Restore from Snapshot:** 10-30 minutes (depends on size)
- **Point-in-Time Recovery:** 15-45 minutes
- **Cross-Region Restore:** 30-60 minutes

### DynamoDB
- **PITR Restore:** 10-30 minutes (creates new table)
- **On-Demand Backup Restore:** 5-15 minutes

### Redshift
- **Snapshot Restore:** 30-120 minutes (depends on cluster size)
- **Cross-Region Restore:** 60-180 minutes

## Monitoring and Alerts

### CloudWatch Metrics to Monitor
- `BackupRetentionPeriodStorageUsed` (RDS)
- `OldestBackupAge` (verify backups are current)
- `SnapshotStorageUsed` (Redshift)

### Recommended Alarms
1. **Backup Age:** Alert if latest backup > 25 hours old
2. **Backup Failures:** Alert on backup job failures
3. **Storage Growth:** Alert on unexpected backup storage growth

## Exceptions

### Acceptable Lower Retention
1. **Ephemeral Data:** Caches, temporary processing data
2. **Reproducible Data:** Can be regenerated from source
3. **Non-Production:** Development, testing environments
4. **Cost Constraints:** With documented risk acceptance

### Exception Documentation
```hcl
tags = {
  Environment = "production"
  BackupException = "true"
  ExceptionReason = "Data is reproducible from upstream source"
  ApprovedBy = "data-team@company.com"
  ApprovalDate = "2024-01-15"
  ReviewDate = "2024-07-15"
}
```

## References
- [AWS RDS Backup and Restore](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_CommonTasks.BackupRestore.html)
- [DynamoDB Point-in-Time Recovery](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/PointInTimeRecovery.html)
- [Redshift Snapshots](https://docs.aws.amazon.com/redshift/latest/mgmt/working-with-snapshots.html)
- [AWS Backup Service](https://docs.aws.amazon.com/aws-backup/latest/devguide/whatisbackup.html)
- [Terraform aws_db_instance](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/db_instance)
- [Terraform aws_dynamodb_table](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/dynamodb_table)
- [AWS Well-Architected Framework - Reliability](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/back-up-data.html)
