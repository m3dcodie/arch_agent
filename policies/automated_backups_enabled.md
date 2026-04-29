# Automated Backups Enabled Policy

## Policy ID
`automated_backups_enabled`

## Severity
**MEDIUM**

## Description
All production database resources MUST have automated backups enabled with properly configured backup windows. Automated backups ensure consistent, reliable backup operations without manual intervention and enable point-in-time recovery.

## Scope
This policy applies to the following AWS resources:
- `aws_db_instance` (RDS Database Instances)
- `aws_rds_cluster` (Aurora Clusters)
- `aws_redshift_cluster` (Redshift Clusters)
- `aws_docdb_cluster` (DocumentDB Clusters)
- `aws_neptune_cluster` (Neptune Clusters)

## Requirements
1. **RDS Instances:** `backup_retention_period > 0` (enables automated backups)
2. **Aurora Clusters:** `backup_retention_period > 0`
3. **Redshift:** `automated_snapshot_retention_period > 0`
4. **DocumentDB:** `backup_retention_period > 0`
5. **Neptune:** `backup_retention_period > 0`
6. **Backup Window:** Should be defined during off-peak hours

## Rationale
Automated backups are critical for:
1. **Consistency:** Regular, predictable backup schedule
2. **Human Error Elimination:** No dependency on manual processes
3. **Point-in-Time Recovery:** Restore to any second within retention period
4. **Compliance:** Automated processes meet audit requirements
5. **Operational Excellence:** Reduces operational burden
6. **Disaster Recovery:** Automated protection without intervention

## Examples

### ✅ Compliant - RDS with Automated Backups
```hcl
resource "aws_db_instance" "production" {
  identifier           = "prod-database"
  engine               = "postgres"
  engine_version       = "14.7"
  instance_class       = "db.r5.large"
  allocated_storage    = 100
  
  backup_retention_period = 7  # ✓ Automated backups enabled (> 0)
  backup_window          = "03:00-04:00"  # ✓ Backup window defined
  maintenance_window     = "mon:04:00-mon:05:00"
  
  username = "admin"
  password = var.db_password
  
  tags = {
    Environment = "production"
  }
}
```

### ✅ Compliant - Aurora with Automated Backups
```hcl
resource "aws_rds_cluster" "production" {
  cluster_identifier = "prod-aurora-cluster"
  engine             = "aurora-postgresql"
  engine_version     = "14.6"
  database_name      = "mydb"
  master_username    = "admin"
  master_password    = var.db_password
  
  backup_retention_period = 14  # ✓ Automated backups enabled
  preferred_backup_window = "02:00-03:00"  # ✓ Off-peak hours
  preferred_maintenance_window = "sun:04:00-sun:05:00"
  
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
  cluster_type       = "single-node"
  
  automated_snapshot_retention_period = 7  # ✓ Automated snapshots enabled
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
  
  backup_retention_period = 7  # ✓ Automated backups enabled
  preferred_backup_window = "02:00-03:00"  # ✓ Defined backup window
  
  tags = {
    Environment = "production"
  }
}
```

### ✅ Compliant - Neptune with Backups
```hcl
resource "aws_neptune_cluster" "graph" {
  cluster_identifier = "prod-neptune"
  engine             = "neptune"
  
  backup_retention_period = 7  # ✓ Automated backups enabled
  preferred_backup_window = "03:00-04:00"
  
  tags = {
    Environment = "production"
  }
}
```

### ✅ Compliant - RDS with Extended Retention
```hcl
resource "aws_db_instance" "critical" {
  identifier           = "critical-database"
  engine               = "postgres"
  instance_class       = "db.r5.xlarge"
  allocated_storage    = 500
  
  backup_retention_period = 35  # ✓ Maximum retention (35 days)
  backup_window          = "02:00-03:00"
  
  # Enable enhanced monitoring
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  
  username = "admin"
  password = var.db_password
  
  tags = {
    Environment = "production"
    Criticality = "high"
  }
}
```

### ❌ Non-Compliant - RDS with Backups Disabled
```hcl
resource "aws_db_instance" "production" {
  identifier           = "prod-database"
  engine               = "mysql"
  instance_class       = "db.t3.large"
  allocated_storage    = 100
  
  backup_retention_period = 0  # ✗ Automated backups disabled
  
  username = "admin"
  password = var.db_password
  
  tags = {
    Environment = "production"
  }
}
```

### ❌ Non-Compliant - RDS Missing Backup Configuration
```hcl
resource "aws_db_instance" "production" {
  identifier           = "prod-database"
  engine               = "postgres"
  instance_class       = "db.r5.large"
  allocated_storage    = 200
  
  # ✗ Missing backup_retention_period (may default to 1 or 0)
  # ✗ Missing backup_window
  
  username = "admin"
  password = var.db_password
  
  tags = {
    Environment = "production"
  }
}
```

### ❌ Non-Compliant - Aurora without Backup Window
```hcl
resource "aws_rds_cluster" "production" {
  cluster_identifier = "prod-aurora"
  engine             = "aurora-mysql"
  master_username    = "admin"
  master_password    = var.db_password
  
  backup_retention_period = 7  # Backups enabled
  # ✗ Missing preferred_backup_window (AWS chooses random time)
  
  tags = {
    Environment = "production"
  }
}
```

### ❌ Non-Compliant - Redshift without Automated Snapshots
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

### ❌ Non-Compliant - DocumentDB Missing Backups
```hcl
resource "aws_docdb_cluster" "documents" {
  cluster_identifier = "prod-docdb"
  engine             = "docdb"
  master_username    = "admin"
  master_password    = var.docdb_password
  
  # ✗ Missing backup_retention_period (defaults to 1 day)
  # ✗ Missing preferred_backup_window
  
  tags = {
    Environment = "production"
  }
}
```

### ❌ Non-Compliant - RDS with Peak-Hour Backup Window
```hcl
resource "aws_db_instance" "production" {
  identifier           = "prod-database"
  engine               = "postgres"
  instance_class       = "db.r5.large"
  allocated_storage    = 100
  
  backup_retention_period = 7
  backup_window          = "14:00-15:00"  # ✗ 2 PM - peak business hours
  
  username = "admin"
  password = var.db_password
  
  tags = {
    Environment = "production"
  }
}
```

## Remediation

### Enable Automated Backups
For RDS/Aurora:
```hcl
backup_retention_period = 7  # Minimum 7 days for production
backup_window          = "03:00-04:00"  # 3-4 AM local time
```

For Redshift:
```hcl
automated_snapshot_retention_period = 7
preferred_maintenance_window        = "sun:05:00-sun:06:00"
```

For DocumentDB/Neptune:
```hcl
backup_retention_period = 7
preferred_backup_window = "02:00-03:00"
```

### Choose Appropriate Backup Windows

**Best Practices:**
1. **Off-Peak Hours:** 2 AM - 5 AM local time
2. **Avoid Maintenance Windows:** Separate by at least 1 hour
3. **Consider Time Zones:** Use UTC in Terraform, document local time
4. **Duration:** Allow 30-60 minutes for backup completion

**Example with Time Zone Documentation:**
```hcl
resource "aws_db_instance" "production" {
  identifier = "prod-database"
  # ... other configuration ...
  
  backup_window      = "07:00-08:00"  # UTC (2-3 AM EST)
  maintenance_window = "mon:08:00-mon:09:00"  # UTC (3-4 AM EST Monday)
  
  tags = {
    Environment       = "production"
    BackupWindowLocal = "2-3 AM EST"
    MaintenanceLocal  = "3-4 AM EST Monday"
  }
}
```

## Backup Window Recommendations

### By Region and Business Hours

#### US East Coast (EST/EDT)
```hcl
backup_window = "07:00-08:00"  # 2-3 AM EST
```

#### US West Coast (PST/PDT)
```hcl
backup_window = "10:00-11:00"  # 2-3 AM PST
```

#### Europe (CET/CEST)
```hcl
backup_window = "02:00-03:00"  # 3-4 AM CET
```

#### Asia Pacific (JST)
```hcl
backup_window = "18:00-19:00"  # 3-4 AM JST
```

### By Workload Type

| Workload | Recommended Window | Rationale |
|----------|-------------------|-----------|
| E-commerce | 2-4 AM local | Lowest transaction volume |
| B2B SaaS | 3-5 AM local | Business hours only |
| Global 24/7 | Stagger by region | Minimize impact |
| Analytics | After ETL completion | Ensure data consistency |
| Development | Any time | Non-critical |

## Performance Impact

### RDS/Aurora Backup Impact
- **I/O Suspension:** Brief pause during snapshot (single-AZ)
- **Multi-AZ:** No I/O suspension (backup from standby)
- **Storage Performance:** Minimal impact on gp3/io1
- **Duration:** 5-30 minutes depending on size and change rate

### Redshift Backup Impact
- **Cluster Performance:** Minimal impact
- **Snapshot Speed:** Incremental after first full snapshot
- **Duration:** 10-60 minutes depending on cluster size

### Monitoring Backup Performance
```hcl
resource "aws_cloudwatch_metric_alarm" "backup_duration" {
  alarm_name          = "rds-backup-duration-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "BackupDuration"
  namespace           = "AWS/RDS"
  period              = "3600"
  statistic           = "Maximum"
  threshold           = "3600"  # 1 hour
  alarm_description   = "Alert when backup takes longer than 1 hour"
  
  dimensions = {
    DBInstanceIdentifier = aws_db_instance.production.id
  }
}
```

## Backup Verification

### Automated Backup Checks
```hcl
# CloudWatch alarm for backup failures
resource "aws_cloudwatch_metric_alarm" "backup_failure" {
  alarm_name          = "rds-backup-failure"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "BackupRetentionPeriodStorageUsed"
  namespace           = "AWS/RDS"
  period              = "43200"  # 12 hours
  statistic           = "Average"
  threshold           = "1"
  alarm_description   = "Alert when backups are not being created"
  treat_missing_data  = "breaching"
  
  dimensions = {
    DBInstanceIdentifier = aws_db_instance.production.id
  }
}
```

### Manual Verification Script
```bash
#!/bin/bash
# Check latest RDS backup age

INSTANCE_ID="prod-database"
LATEST_SNAPSHOT=$(aws rds describe-db-snapshots \
  --db-instance-identifier $INSTANCE_ID \
  --snapshot-type automated \
  --query 'DBSnapshots[0].SnapshotCreateTime' \
  --output text)

echo "Latest automated snapshot: $LATEST_SNAPSHOT"

# Alert if older than 25 hours
AGE_HOURS=$(( ($(date +%s) - $(date -d "$LATEST_SNAPSHOT" +%s)) / 3600 ))
if [ $AGE_HOURS -gt 25 ]; then
  echo "WARNING: Latest backup is $AGE_HOURS hours old!"
  exit 1
fi
```

## Cost Optimization

### Backup Storage Costs
- **Free Tier:** Backup storage up to 100% of allocated storage
- **Additional:** $0.095/GB-month (us-east-1)
- **Optimization:** Use appropriate retention periods

### Cost Example
```
Database: 500 GB allocated storage
Retention: 7 days
Change Rate: 10% daily

Backup Storage: 500 GB (initial) + 350 GB (7 days × 50 GB changes) = 850 GB
Free: 500 GB
Billable: 350 GB × $0.095 = $33.25/month
```

### Cost Optimization Strategies
1. **Right-size Retention:** Don't over-retain for non-critical data
2. **Manual Snapshots:** For long-term retention beyond 35 days
3. **Cross-Region Copies:** Only for DR requirements
4. **Lifecycle Policies:** Archive old snapshots to S3 Glacier

## Exceptions

### Acceptable Scenarios Without Automated Backups
1. **Read Replicas:** Primary has backups enabled
2. **Temporary Databases:** Short-lived testing/development
3. **Derived Data:** Can be regenerated from source
4. **Cache Layers:** ElastiCache, Redis (data is transient)

### Exception Documentation
```hcl
resource "aws_db_instance" "read_replica" {
  identifier     = "prod-database-replica"
  replicate_source_db = aws_db_instance.production.identifier
  instance_class = "db.r5.large"
  
  backup_retention_period = 0  # Acceptable for read replica
  
  tags = {
    Environment = "production"
    Role        = "read-replica"
    BackupNote  = "Primary has backups enabled"
  }
}
```

## Compliance Mapping

### Regulatory Requirements
| Framework | Backup Requirement |
|-----------|-------------------|
| **PCI-DSS** | Daily automated backups, tested quarterly |
| **HIPAA** | Regular backups, tested restoration procedures |
| **SOC 2** | Documented backup procedures, retention policy |
| **ISO 27001** | Backup and restoration procedures |
| **GDPR** | Data recovery capabilities |

## Disaster Recovery Integration

### Backup Strategy Tiers

**Tier 1: Critical (RTO < 1 hour)**
```hcl
backup_retention_period = 35  # Maximum automated retention
# Plus manual snapshots for longer retention
# Plus cross-region replication
```

**Tier 2: Important (RTO < 4 hours)**
```hcl
backup_retention_period = 14
# Plus manual snapshots weekly
```

**Tier 3: Standard (RTO < 24 hours)**
```hcl
backup_retention_period = 7
# Automated backups only
```

## References
- [AWS RDS Automated Backups](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithAutomatedBackups.html)
- [Aurora Backup and Restore](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/Aurora.Managing.Backups.html)
- [Redshift Automated Snapshots](https://docs.aws.amazon.com/redshift/latest/mgmt/working-with-snapshots.html)
- [DocumentDB Backup and Restore](https://docs.aws.amazon.com/documentdb/latest/developerguide/backup_restore.html)
- [AWS Backup Service](https://docs.aws.amazon.com/aws-backup/latest/devguide/whatisbackup.html)
- [Terraform aws_db_instance](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/db_instance)
- [AWS Well-Architected Framework - Reliability](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/back-up-data.html)
