# Encryption at Rest Policy

## Policy ID
`encryption_at_rest`

## Severity
**HIGH**

## Description
All data storage resources MUST have encryption at rest enabled using AWS-managed or customer-managed KMS keys. This ensures data confidentiality and meets compliance requirements for data protection.

## Scope
This policy applies to the following AWS resources:
- `aws_db_instance` (RDS Database Instances)
- `aws_rds_cluster` (Aurora Clusters)
- `aws_s3_bucket` (S3 Buckets)
- `aws_ebs_volume` (EBS Volumes)
- `aws_efs_file_system` (EFS File Systems)
- `aws_dynamodb_table` (DynamoDB Tables)
- `aws_redshift_cluster` (Redshift Clusters)

## Requirements
1. **RDS/Aurora:** `storage_encrypted = true` must be set
2. **S3:** Server-side encryption must be enabled via `server_side_encryption_configuration`
3. **EBS:** `encrypted = true` must be set
4. **EFS:** `encrypted = true` must be set
5. **DynamoDB:** `server_side_encryption` block must be present with `enabled = true`
6. **Redshift:** `encrypted = true` must be set

## Rationale
Encryption at rest is critical for:
1. **Compliance:** Required by GDPR, HIPAA, PCI-DSS, SOC 2
2. **Data Protection:** Prevents unauthorized access to data on physical storage
3. **Breach Mitigation:** Encrypted data is useless to attackers without keys
4. **Industry Standard:** Expected security baseline for all production systems
5. **Regulatory Fines:** Non-compliance can result in millions in penalties

## Examples

### ✅ Compliant - RDS with Encryption
```hcl
resource "aws_db_instance" "production" {
  identifier           = "prod-database"
  engine               = "postgres"
  engine_version       = "14.7"
  instance_class       = "db.t3.large"
  allocated_storage    = 100
  
  storage_encrypted = true  # ✓ Encryption enabled
  kms_key_id        = aws_kms_key.rds.arn  # Optional: customer-managed key
  
  username = "admin"
  password = var.db_password
}
```

### ✅ Compliant - S3 with Default Encryption
```hcl
resource "aws_s3_bucket" "data" {
  bucket = "company-data-bucket"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "AES256"  # ✓ AWS-managed encryption
    }
  }
}
```

### ✅ Compliant - S3 with KMS Encryption
```hcl
resource "aws_s3_bucket" "sensitive" {
  bucket = "company-sensitive-data"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "sensitive" {
  bucket = aws_s3_bucket.sensitive.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"  # ✓ KMS encryption
      kms_master_key_id = aws_kms_key.s3.arn
    }
    bucket_key_enabled = true  # Cost optimization
  }
}
```

### ✅ Compliant - EBS Volume with Encryption
```hcl
resource "aws_ebs_volume" "data" {
  availability_zone = "us-east-1a"
  size              = 100
  type              = "gp3"
  
  encrypted  = true  # ✓ Encryption enabled
  kms_key_id = aws_kms_key.ebs.arn
  
  tags = {
    Name = "encrypted-data-volume"
  }
}
```

### ✅ Compliant - DynamoDB with Encryption
```hcl
resource "aws_dynamodb_table" "users" {
  name           = "users-table"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "user_id"

  attribute {
    name = "user_id"
    type = "S"
  }

  server_side_encryption {
    enabled     = true  # ✓ Encryption enabled
    kms_key_arn = aws_kms_key.dynamodb.arn
  }
}
```

### ❌ Non-Compliant - RDS without Encryption
```hcl
resource "aws_db_instance" "production" {
  identifier           = "prod-database"
  engine               = "postgres"
  instance_class       = "db.t3.large"
  allocated_storage    = 100
  
  # ✗ Missing storage_encrypted attribute (defaults to false)
  
  username = "admin"
  password = var.db_password
}
```

### ❌ Non-Compliant - RDS with Encryption Disabled
```hcl
resource "aws_db_instance" "production" {
  identifier           = "prod-database"
  engine               = "mysql"
  instance_class       = "db.t3.medium"
  allocated_storage    = 50
  
  storage_encrypted = false  # ✗ Explicitly disabled
  
  username = "admin"
  password = var.db_password
}
```

### ❌ Non-Compliant - S3 without Encryption
```hcl
resource "aws_s3_bucket" "data" {
  bucket = "company-data-bucket"
  
  # ✗ No server_side_encryption_configuration defined
}
```

### ❌ Non-Compliant - EBS Volume Unencrypted
```hcl
resource "aws_ebs_volume" "data" {
  availability_zone = "us-east-1a"
  size              = 100
  type              = "gp3"
  
  # ✗ Missing encrypted attribute (defaults to false)
  
  tags = {
    Name = "unencrypted-volume"
  }
}
```

### ❌ Non-Compliant - DynamoDB without Encryption
```hcl
resource "aws_dynamodb_table" "users" {
  name           = "users-table"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "user_id"

  attribute {
    name = "user_id"
    type = "S"
  }
  
  # ✗ No server_side_encryption block defined
}
```

### ❌ Non-Compliant - Aurora Cluster Unencrypted
```hcl
resource "aws_rds_cluster" "aurora" {
  cluster_identifier = "aurora-cluster"
  engine             = "aurora-postgresql"
  engine_version     = "14.6"
  database_name      = "mydb"
  master_username    = "admin"
  master_password    = var.db_password
  
  # ✗ Missing storage_encrypted attribute
}
```

## Remediation

### For RDS/Aurora
Add encryption to your database resource:
```hcl
storage_encrypted = true
kms_key_id        = aws_kms_key.rds.arn  # Optional: use customer-managed key
```

**Note:** Encryption cannot be enabled on existing unencrypted RDS instances. You must:
1. Create a snapshot of the unencrypted instance
2. Copy the snapshot with encryption enabled
3. Restore from the encrypted snapshot
4. Update application connection strings

### For S3
Add server-side encryption configuration:
```hcl
resource "aws_s3_bucket_server_side_encryption_configuration" "example" {
  bucket = aws_s3_bucket.example.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"  # or "aws:kms" for KMS
    }
  }
}
```

### For EBS
Add encryption to your volume:
```hcl
encrypted  = true
kms_key_id = aws_kms_key.ebs.arn  # Optional
```

**Note:** Existing unencrypted volumes must be:
1. Snapshotted
2. Copied with encryption enabled
3. New volume created from encrypted snapshot

### For DynamoDB
Add server-side encryption block:
```hcl
server_side_encryption {
  enabled     = true
  kms_key_arn = aws_kms_key.dynamodb.arn  # Optional
}
```

## Exceptions
**None.** This policy applies to all data storage resources without exception. Even development and testing environments should use encryption to maintain security hygiene and prevent accidental data exposure.

## Cost Considerations
- **AWS-Managed Keys (AES256):** No additional cost
- **KMS Customer-Managed Keys:** $1/month per key + $0.03 per 10,000 requests
- **S3 Bucket Keys:** Reduce KMS request costs by up to 99%

## References
- [AWS RDS Encryption Documentation](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Overview.Encryption.html)
- [AWS S3 Encryption Documentation](https://docs.aws.amazon.com/AmazonS3/latest/userguide/serv-side-encryption.html)
- [AWS EBS Encryption Documentation](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/EBSEncryption.html)
- [AWS DynamoDB Encryption Documentation](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/EncryptionAtRest.html)
- [Terraform aws_db_instance](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/db_instance)
- [Terraform aws_s3_bucket_server_side_encryption_configuration](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_server_side_encryption_configuration)
- [GDPR Article 32 - Security of Processing](https://gdpr-info.eu/art-32-gdpr/)
- [HIPAA Security Rule - Encryption](https://www.hhs.gov/hipaa/for-professionals/security/guidance/index.html)
