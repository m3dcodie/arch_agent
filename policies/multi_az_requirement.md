# Multi-AZ Requirement Policy

## Policy ID
`multi_az_requirement`

## Severity
**MEDIUM**

## Description
All production database and cache resources MUST be deployed in Multi-AZ (Availability Zone) configuration to ensure high availability and automatic failover capabilities. This protects against datacenter-level failures.

## Scope
This policy applies to the following AWS resources:
- `aws_db_instance` (RDS Database Instances)
- `aws_rds_cluster` (Aurora Clusters - via instance count)
- `aws_elasticache_replication_group` (ElastiCache Redis)
- `aws_mq_broker` (Amazon MQ)
- `aws_elasticsearch_domain` (Elasticsearch/OpenSearch)

## Requirements
1. **RDS Instances:** `multi_az = true` for production databases
2. **Aurora Clusters:** At least 2 instances in different AZs
3. **ElastiCache:** `automatic_failover_enabled = true` and `num_cache_clusters >= 2`
4. **Amazon MQ:** `deployment_mode = "ACTIVE_STANDBY_MULTI_AZ"`
5. **Elasticsearch:** `zone_awareness_enabled = true` with `availability_zone_count >= 2`

**Context-Aware:** This policy applies only to resources tagged with `Environment = "production"` or `Environment = "prod"`

## Rationale
Multi-AZ deployment is critical for:
1. **High Availability:** 99.95% SLA vs 99.5% for single-AZ
2. **Automatic Failover:** Typically 1-2 minutes for RDS
3. **Disaster Recovery:** Protection against AZ-level outages
4. **Maintenance Windows:** Zero-downtime patching
5. **Business Continuity:** Prevents revenue loss during outages
6. **Cost of Downtime:** Average $5,600 per minute for enterprises

## Examples

### ✅ Compliant - Production RDS with Multi-AZ
```hcl
resource "aws_db_instance" "production" {
  identifier           = "prod-database"
  engine               = "postgres"
  engine_version       = "14.7"
  instance_class       = "db.r5.large"
  allocated_storage    = 100
  
  multi_az = true  # ✓ Multi-AZ enabled for production
  
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.database.id]
  
  username = "admin"
  password = var.db_password
  
  tags = {
    Environment = "production"  # Production environment
    Application = "core-api"
  }
}
```

### ✅ Compliant - Aurora Cluster with Multiple Instances
```hcl
resource "aws_rds_cluster" "production" {
  cluster_identifier = "prod-aurora-cluster"
  engine             = "aurora-postgresql"
  engine_version     = "14.6"
  database_name      = "mydb"
  master_username    = "admin"
  master_password    = var.db_password
  
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.aurora.id]
  
  tags = {
    Environment = "production"
  }
}

# ✓ Multiple instances in different AZs
resource "aws_rds_cluster_instance" "production_1" {
  identifier         = "prod-aurora-instance-1"
  cluster_identifier = aws_rds_cluster.production.id
  instance_class     = "db.r5.large"
  engine             = aws_rds_cluster.production.engine
  
  availability_zone = "us-east-1a"  # First AZ
}

resource "aws_rds_cluster_instance" "production_2" {
  identifier         = "prod-aurora-instance-2"
  cluster_identifier = aws_rds_cluster.production.id
  instance_class     = "db.r5.large"
  engine             = aws_rds_cluster.production.engine
  
  availability_zone = "us-east-1b"  # Second AZ - ✓ Multi-AZ
}
```

### ✅ Compliant - ElastiCache with Automatic Failover
```hcl
resource "aws_elasticache_replication_group" "production" {
  replication_group_id       = "prod-redis-cluster"
  replication_group_description = "Production Redis cluster"
  engine                     = "redis"
  engine_version             = "7.0"
  node_type                  = "cache.r5.large"
  
  num_cache_clusters         = 3  # ✓ Multiple nodes
  automatic_failover_enabled = true  # ✓ Automatic failover
  multi_az_enabled           = true  # ✓ Multi-AZ enabled
  
  subnet_group_name = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.redis.id]
  
  tags = {
    Environment = "production"
  }
}
```

### ✅ Compliant - Amazon MQ with Multi-AZ
```hcl
resource "aws_mq_broker" "production" {
  broker_name = "prod-message-broker"
  engine_type = "ActiveMQ"
  engine_version = "5.16.4"
  host_instance_type = "mq.m5.large"
  
  deployment_mode = "ACTIVE_STANDBY_MULTI_AZ"  # ✓ Multi-AZ deployment
  
  subnet_ids = [
    aws_subnet.private_a.id,
    aws_subnet.private_b.id
  ]
  
  user {
    username = "admin"
    password = var.mq_password
  }
  
  tags = {
    Environment = "production"
  }
}
```

### ✅ Compliant - Elasticsearch with Zone Awareness
```hcl
resource "aws_elasticsearch_domain" "production" {
  domain_name           = "prod-search"
  elasticsearch_version = "7.10"

  cluster_config {
    instance_type            = "r5.large.elasticsearch"
    instance_count           = 4
    zone_awareness_enabled   = true  # ✓ Zone awareness enabled
    
    zone_awareness_config {
      availability_zone_count = 2  # ✓ Two AZs
    }
  }

  ebs_options {
    ebs_enabled = true
    volume_size = 100
  }

  tags = {
    Environment = "production"
  }
}
```

### ✅ Compliant - Development Database (Single-AZ Acceptable)
```hcl
resource "aws_db_instance" "development" {
  identifier           = "dev-database"
  engine               = "postgres"
  instance_class       = "db.t3.medium"
  allocated_storage    = 20
  
  multi_az = false  # ✓ Acceptable for non-production
  
  username = "admin"
  password = var.db_password
  
  tags = {
    Environment = "development"  # Not production - policy doesn't apply
  }
}
```

### ❌ Non-Compliant - Production RDS Single-AZ
```hcl
resource "aws_db_instance" "production" {
  identifier           = "prod-database"
  engine               = "mysql"
  instance_class       = "db.t3.large"
  allocated_storage    = 100
  
  multi_az = false  # ✗ Single-AZ for production
  
  username = "admin"
  password = var.db_password
  
  tags = {
    Environment = "production"  # Production but no Multi-AZ
  }
}
```

### ❌ Non-Compliant - Production RDS Missing multi_az
```hcl
resource "aws_db_instance" "production" {
  identifier           = "prod-database"
  engine               = "postgres"
  instance_class       = "db.r5.xlarge"
  allocated_storage    = 500
  
  # ✗ Missing multi_az attribute (defaults to false)
  
  username = "admin"
  password = var.db_password
  
  tags = {
    Environment = "prod"  # Production environment
  }
}
```

### ❌ Non-Compliant - Aurora with Single Instance
```hcl
resource "aws_rds_cluster" "production" {
  cluster_identifier = "prod-aurora"
  engine             = "aurora-mysql"
  master_username    = "admin"
  master_password    = var.db_password
  
  tags = {
    Environment = "production"
  }
}

# ✗ Only one instance - no failover capability
resource "aws_rds_cluster_instance" "production_only" {
  identifier         = "prod-aurora-instance-1"
  cluster_identifier = aws_rds_cluster.production.id
  instance_class     = "db.r5.large"
  engine             = aws_rds_cluster.production.engine
}
```

### ❌ Non-Compliant - ElastiCache without Failover
```hcl
resource "aws_elasticache_replication_group" "production" {
  replication_group_id       = "prod-redis"
  replication_group_description = "Production Redis"
  engine                     = "redis"
  node_type                  = "cache.t3.medium"
  
  num_cache_clusters         = 1  # ✗ Single node
  automatic_failover_enabled = false  # ✗ No automatic failover
  
  tags = {
    Environment = "production"
  }
}
```

### ❌ Non-Compliant - ElastiCache with Failover but Single Node
```hcl
resource "aws_elasticache_replication_group" "production" {
  replication_group_id       = "prod-redis"
  replication_group_description = "Production Redis"
  engine                     = "redis"
  node_type                  = "cache.r5.large"
  
  num_cache_clusters         = 1  # ✗ Only one node
  automatic_failover_enabled = true  # Failover enabled but needs 2+ nodes
  
  tags = {
    Environment = "production"
  }
}
```

### ❌ Non-Compliant - Amazon MQ Single Instance
```hcl
resource "aws_mq_broker" "production" {
  broker_name = "prod-mq"
  engine_type = "ActiveMQ"
  engine_version = "5.16.4"
  host_instance_type = "mq.m5.large"
  
  deployment_mode = "SINGLE_INSTANCE"  # ✗ Single instance for production
  
  subnet_ids = [aws_subnet.private_a.id]
  
  user {
    username = "admin"
    password = var.mq_password
  }
  
  tags = {
    Environment = "production"
  }
}
```

### ❌ Non-Compliant - Elasticsearch Single-AZ
```hcl
resource "aws_elasticsearch_domain" "production" {
  domain_name           = "prod-search"
  elasticsearch_version = "7.10"

  cluster_config {
    instance_type          = "r5.large.elasticsearch"
    instance_count         = 2
    zone_awareness_enabled = false  # ✗ Zone awareness disabled
  }

  tags = {
    Environment = "production"
  }
}
```

## Remediation

### For RDS Instances
Enable Multi-AZ:
```hcl
multi_az = true
```

**Note:** Enabling Multi-AZ on existing instance:
1. Causes brief I/O suspension during initial sync (typically 1-2 minutes)
2. No data loss
3. Can be done via Terraform apply
4. Plan for maintenance window

### For Aurora Clusters
Add a second instance in a different AZ:
```hcl
resource "aws_rds_cluster_instance" "replica" {
  identifier         = "${var.cluster_name}-instance-2"
  cluster_identifier = aws_rds_cluster.main.id
  instance_class     = var.instance_class
  engine             = aws_rds_cluster.main.engine
  
  # Specify different AZ or let AWS choose
  availability_zone = "us-east-1b"
}
```

### For ElastiCache
Enable automatic failover and add nodes:
```hcl
automatic_failover_enabled = true
multi_az_enabled           = true
num_cache_clusters         = 3  # Primary + 2 replicas
```

### For Amazon MQ
Change deployment mode:
```hcl
deployment_mode = "ACTIVE_STANDBY_MULTI_AZ"
```

**Note:** Requires recreation of broker - plan for migration window

### For Elasticsearch
Enable zone awareness:
```hcl
cluster_config {
  zone_awareness_enabled = true
  
  zone_awareness_config {
    availability_zone_count = 2  # or 3
  }
  
  instance_count = 4  # Must be multiple of AZ count
}
```

## Exceptions

### Acceptable Single-AZ Scenarios
1. **Non-Production Environments:** Development, testing, staging
2. **Cost Optimization:** Sandbox environments
3. **Temporary Resources:** Short-lived proof-of-concepts
4. **Read Replicas:** Can be single-AZ (primary must be Multi-AZ)

### Exception Tagging
```hcl
tags = {
  Environment        = "production"
  MultiAZException   = "true"
  ExceptionReason    = "Read replica for analytics"
  ApprovedBy         = "architecture-team@company.com"
  ReviewDate         = "2024-06-01"
}
```

## Cost Considerations

### RDS Multi-AZ Pricing
- **Cost:** ~2x single-AZ (standby instance + cross-AZ data transfer)
- **Example:** db.r5.large: $0.29/hr × 2 = $0.58/hr (~$420/month)
- **ROI:** Prevents downtime costs ($5,600/min average)

### Aurora Multi-AZ Pricing
- **Cost:** Additional instance(s) + storage replication
- **Example:** 2× db.r5.large = $0.58/hr (~$420/month)
- **Benefit:** Read scaling + high availability

### ElastiCache Multi-AZ Pricing
- **Cost:** Additional replica nodes
- **Example:** 3× cache.r5.large = $0.252/hr × 3 = $0.756/hr (~$550/month)

## Performance Considerations

### RDS Multi-AZ
- **Write Latency:** +1-2ms (synchronous replication)
- **Read Performance:** No impact (reads from primary)
- **Failover Time:** 1-2 minutes (automatic)

### Aurora Multi-AZ
- **Write Latency:** Minimal (shared storage)
- **Read Performance:** Improved (read replicas)
- **Failover Time:** 30-120 seconds (automatic)

## Monitoring

### CloudWatch Metrics to Monitor
- `DatabaseConnections` (spike during failover)
- `ReplicaLag` (Aurora)
- `FailoverCount` (track failover frequency)

### Alarms to Set
```hcl
resource "aws_cloudwatch_metric_alarm" "database_failover" {
  alarm_name          = "rds-failover-detected"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "FailoverCount"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "Alert when RDS failover occurs"
  
  dimensions = {
    DBInstanceIdentifier = aws_db_instance.production.id
  }
}
```

## References
- [AWS RDS Multi-AZ Deployments](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZ.html)
- [Aurora High Availability](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/Concepts.AuroraHighAvailability.html)
- [ElastiCache Multi-AZ](https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/AutoFailover.html)
- [Amazon MQ High Availability](https://docs.aws.amazon.com/amazon-mq/latest/developer-guide/active-standby-broker-deployment.html)
- [AWS Well-Architected Framework - Reliability Pillar](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/welcome.html)
- [Terraform aws_db_instance](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/db_instance)
- [Terraform aws_elasticache_replication_group](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/elasticache_replication_group)
