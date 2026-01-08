# KMS Key Rotation Policy

## Policy ID
`kms_key_rotation`

## Severity
**MEDIUM**

## Description
All customer-managed KMS keys MUST have automatic key rotation enabled to enhance cryptographic security. Regular key rotation limits the amount of data encrypted under a single key version and reduces the impact of potential key compromise.

## Scope
This policy applies to the following AWS resources:
- `aws_kms_key` (Customer-Managed KMS Keys)

**Note:** This policy does NOT apply to:
- AWS-managed keys (automatically rotated annually)
- Keys with imported key material (cannot be auto-rotated)
- Asymmetric keys (cannot be auto-rotated)

## Requirements
1. **Symmetric Keys:** `enable_key_rotation = true` must be set
2. **Rotation Frequency:** Automatic rotation every 365 days (AWS default)
3. **Key Usage:** Must be enabled for encryption/decryption operations
4. **Key State:** Must be in ENABLED state

## Rationale
KMS key rotation is critical for:
1. **Cryptographic Hygiene:** Limits data encrypted under single key version
2. **Compliance:** Required by many security frameworks (PCI-DSS, HIPAA)
3. **Breach Mitigation:** Reduces impact of potential key compromise
4. **Best Practice:** Industry standard for cryptographic key management
5. **Regulatory Requirements:** NIST, FIPS standards recommend regular rotation
6. **Defense in Depth:** Additional security layer for encrypted data

## Examples

### ✅ Compliant - KMS Key with Rotation Enabled
```hcl
resource "aws_kms_key" "database" {
  description             = "KMS key for database encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true  # ✓ Automatic rotation enabled
  
  tags = {
    Name        = "prod-database-encryption-key"
    Environment = "production"
    Purpose     = "database-encryption"
  }
}

resource "aws_kms_alias" "database" {
  name          = "alias/prod-database-key"
  target_key_id = aws_kms_key.database.key_id
}
```

### ✅ Compliant - S3 Encryption Key with Rotation
```hcl
resource "aws_kms_key" "s3" {
  description             = "KMS key for S3 bucket encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true  # ✓ Rotation enabled
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow S3 to use the key"
        Effect = "Allow"
        Principal = {
          Service = "s3.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = "*"
      }
    ]
  })
  
  tags = {
    Name        = "prod-s3-encryption-key"
    Environment = "production"
  }
}
```

### ✅ Compliant - EBS Volume Encryption Key
```hcl
resource "aws_kms_key" "ebs" {
  description             = "KMS key for EBS volume encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true  # ✓ Rotation enabled
  
  tags = {
    Name        = "prod-ebs-encryption-key"
    Environment = "production"
    Purpose     = "ebs-encryption"
  }
}

resource "aws_kms_alias" "ebs" {
  name          = "alias/prod-ebs-key"
  target_key_id = aws_kms_key.ebs.key_id
}
```

### ✅ Compliant - Secrets Manager Encryption Key
```hcl
resource "aws_kms_key" "secrets" {
  description             = "KMS key for Secrets Manager"
  deletion_window_in_days = 30
  enable_key_rotation     = true  # ✓ Rotation enabled
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow Secrets Manager to use the key"
        Effect = "Allow"
        Principal = {
          Service = "secretsmanager.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = "*"
      }
    ]
  })
  
  tags = {
    Name        = "prod-secrets-encryption-key"
    Environment = "production"
  }
}
```

### ✅ Compliant - Multi-Region Key with Rotation
```hcl
resource "aws_kms_key" "multi_region" {
  description             = "Multi-region KMS key"
  deletion_window_in_days = 30
  enable_key_rotation     = true  # ✓ Rotation enabled
  multi_region            = true
  
  tags = {
    Name        = "prod-multi-region-key"
    Environment = "production"
  }
}
```

### ❌ Non-Compliant - KMS Key without Rotation
```hcl
resource "aws_kms_key" "database" {
  description             = "KMS key for database encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = false  # ✗ Rotation disabled
  
  tags = {
    Name        = "prod-database-encryption-key"
    Environment = "production"
  }
}
```

### ❌ Non-Compliant - KMS Key Missing Rotation Setting
```hcl
resource "aws_kms_key" "s3" {
  description             = "KMS key for S3 encryption"
  deletion_window_in_days = 30
  # ✗ Missing enable_key_rotation (defaults to false)
  
  tags = {
    Name        = "prod-s3-encryption-key"
    Environment = "production"
  }
}
```

### ❌ Non-Compliant - Production Key without Rotation
```hcl
resource "aws_kms_key" "ebs" {
  description             = "KMS key for EBS volumes"
  deletion_window_in_days = 30
  enable_key_rotation     = false  # ✗ Explicitly disabled
  
  tags = {
    Name        = "prod-ebs-encryption-key"
    Environment = "production"
    Purpose     = "ebs-encryption"
  }
}
```

### ❌ Non-Compliant - Secrets Key without Rotation
```hcl
resource "aws_kms_key" "secrets" {
  description             = "KMS key for secrets"
  deletion_window_in_days = 30
  # ✗ Missing enable_key_rotation attribute
  
  tags = {
    Name        = "prod-secrets-key"
    Environment = "production"
  }
}
```

### ✅ Acceptable - Asymmetric Key (Cannot Rotate)
```hcl
resource "aws_kms_key" "signing" {
  description             = "KMS key for digital signatures"
  deletion_window_in_days = 30
  key_usage               = "SIGN_VERIFY"
  customer_master_key_spec = "RSA_2048"
  
  # ✓ Asymmetric keys cannot have automatic rotation
  # This is acceptable and documented
  
  tags = {
    Name           = "prod-signing-key"
    Environment    = "production"
    KeyType        = "asymmetric"
    RotationPolicy = "manual-annual-review"
  }
}
```

### ✅ Acceptable - Imported Key Material (Cannot Rotate)
```hcl
resource "aws_kms_key" "imported" {
  description             = "KMS key with imported material"
  deletion_window_in_days = 30
  
  # Keys with imported material cannot have automatic rotation
  # Must implement manual rotation process
  
  tags = {
    Name           = "prod-imported-key"
    Environment    = "production"
    KeyMaterial    = "imported"
    RotationPolicy = "manual-quarterly"
  }
}
```

## Remediation

### Enable Key Rotation on Existing Keys
```hcl
resource "aws_kms_key" "database" {
  description             = "KMS key for database encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true  # Add this line
  
  tags = {
    Name        = "prod-database-encryption-key"
    Environment = "production"
  }
}
```

**Note:** Enabling rotation on existing key:
- Does NOT cause downtime
- Does NOT re-encrypt existing data
- Takes effect immediately
- First rotation occurs 365 days after enabling

### AWS CLI Command
```bash
# Enable rotation on existing key
aws kms enable-key-rotation --key-id <key-id>

# Verify rotation is enabled
aws kms get-key-rotation-status --key-id <key-id>
```

### Terraform Import and Update
```bash
# Import existing key
terraform import aws_kms_key.database <key-id>

# Update configuration to enable rotation
# Then apply
terraform apply
```

## Key Rotation Mechanics

### How Automatic Rotation Works
1. **Annual Schedule:** AWS rotates key automatically every 365 days
2. **New Key Version:** Creates new cryptographic material
3. **Backward Compatibility:** Old versions retained for decryption
4. **Transparent:** Applications don't need changes
5. **Encryption:** New encryptions use latest version
6. **Decryption:** AWS automatically uses correct version

### Key Version Management
```
Key ID: arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012

Versions:
├── Version 1 (2023-01-01) - Can decrypt only
├── Version 2 (2024-01-01) - Can decrypt only
└── Version 3 (2025-01-01) - Current (encrypt & decrypt)
```

### Data Re-encryption
**Important:** Automatic rotation does NOT re-encrypt existing data

To re-encrypt data with new key version:
```bash
# For S3 objects
aws s3 cp s3://bucket/object s3://bucket/object \
  --sse aws:kms \
  --sse-kms-key-id <key-id> \
  --metadata-directive REPLACE

# For EBS volumes
# Create snapshot, copy with new key, create volume from snapshot
```

## Monitoring and Compliance

### CloudWatch Metrics
```hcl
resource "aws_cloudwatch_metric_alarm" "key_rotation_disabled" {
  alarm_name          = "kms-key-rotation-disabled"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "KeyRotationEnabled"
  namespace           = "AWS/KMS"
  period              = "86400"
  statistic           = "Average"
  threshold           = "1"
  alarm_description   = "Alert when KMS key rotation is disabled"
  
  dimensions = {
    KeyId = aws_kms_key.database.key_id
  }
}
```

### AWS Config Rule
```hcl
resource "aws_config_config_rule" "kms_rotation" {
  name = "kms-cmk-rotation-enabled"

  source {
    owner             = "AWS"
    source_identifier = "CMK_BACKING_KEY_ROTATION_ENABLED"
  }

  depends_on = [aws_config_configuration_recorder.main]
}
```

### Compliance Check Script
```bash
#!/bin/bash
# Check all KMS keys for rotation status

echo "KMS Key Rotation Compliance Report"
echo "===================================="

aws kms list-keys --query 'Keys[].KeyId' --output text | while read key_id; do
  # Get key metadata
  key_metadata=$(aws kms describe-key --key-id "$key_id")
  key_state=$(echo "$key_metadata" | jq -r '.KeyMetadata.KeyState')
  key_spec=$(echo "$key_metadata" | jq -r '.KeyMetadata.CustomerMasterKeySpec')
  
  # Skip if not enabled or not symmetric
  if [ "$key_state" != "Enabled" ] || [ "$key_spec" != "SYMMETRIC_DEFAULT" ]; then
    continue
  fi
  
  # Check rotation status
  rotation_status=$(aws kms get-key-rotation-status --key-id "$key_id" | jq -r '.KeyRotationEnabled')
  
  if [ "$rotation_status" = "false" ]; then
    echo "❌ Key $key_id: Rotation DISABLED"
  else
    echo "✅ Key $key_id: Rotation ENABLED"
  fi
done
```

## Cost Considerations

### KMS Key Costs
- **Key Storage:** $1/month per customer-managed key
- **API Requests:** $0.03 per 10,000 requests
- **Rotation Cost:** No additional cost for automatic rotation

### Cost Example
```
10 KMS keys with rotation enabled:
- Key storage: 10 × $1 = $10/month
- Rotation: $0 (included)
- API requests: ~$5/month (typical usage)
Total: ~$15/month
```

### Cost Optimization
1. **Consolidate Keys:** Use fewer keys for multiple purposes
2. **Key Aliases:** Use aliases to simplify key management
3. **Caching:** Cache data keys to reduce API calls
4. **AWS-Managed Keys:** Use when automatic rotation is sufficient

## Manual Rotation Process

### For Keys That Cannot Auto-Rotate

**Asymmetric Keys or Imported Material:**

1. **Create New Key:**
```hcl
resource "aws_kms_key" "signing_new" {
  description              = "New signing key (2024)"
  key_usage                = "SIGN_VERIFY"
  customer_master_key_spec = "RSA_2048"
  
  tags = {
    Name        = "prod-signing-key-2024"
    Environment = "production"
    ValidFrom   = "2024-01-01"
  }
}
```

2. **Update Applications:** Point to new key
3. **Deprecate Old Key:** After transition period
4. **Schedule Deletion:** After all data migrated

### Manual Rotation Schedule
```hcl
resource "aws_kms_key" "manual_rotation" {
  description = "Key requiring manual rotation"
  
  tags = {
    Name                = "prod-manual-rotation-key"
    Environment         = "production"
    LastRotated         = "2024-01-15"
    NextRotationDue     = "2025-01-15"
    RotationResponsible = "security-team@company.com"
  }
}
```

## Exceptions

### Acceptable Scenarios Without Auto-Rotation
1. **Asymmetric Keys:** Cannot auto-rotate (RSA, ECC keys)
2. **Imported Key Material:** Cannot auto-rotate
3. **External Key Store:** Keys in CloudHSM
4. **Short-Lived Keys:** Temporary keys (< 1 year lifespan)
5. **Development Keys:** Non-production environments

### Exception Documentation
```hcl
resource "aws_kms_key" "exception" {
  description             = "KMS key with rotation exception"
  deletion_window_in_days = 30
  enable_key_rotation     = false
  
  tags = {
    Name              = "dev-testing-key"
    Environment       = "development"
    RotationException = "true"
    ExceptionReason   = "Development environment, key lifecycle < 90 days"
    ApprovedBy        = "security-team@company.com"
    ApprovalDate      = "2024-01-15"
  }
}
```

## Compliance Mapping

### Regulatory Requirements
| Framework | Requirement |
|-----------|-------------|
| **PCI-DSS** | Requirement 3.6.4 - Cryptographic key rotation |
| **HIPAA** | Key management and rotation procedures |
| **NIST 800-57** | Cryptoperiod recommendations |
| **SOC 2** | Key rotation as part of encryption controls |
| **ISO 27001** | A.10.1.2 - Key management |

### Rotation Frequency Recommendations
| Data Sensitivity | Rotation Frequency |
|------------------|-------------------|
| **Critical (PII, Financial)** | Annual (AWS default) |
| **Sensitive (Business Data)** | Annual |
| **Internal** | Annual or bi-annual |
| **Development** | Not required |

## Best Practices

### Key Management Strategy
1. **Use Aliases:** Simplify key references
2. **Tag Keys:** Document purpose and ownership
3. **Monitor Usage:** Track API calls and errors
4. **Audit Access:** Review key policies regularly
5. **Test Rotation:** Verify applications handle rotation
6. **Document Keys:** Maintain key inventory

### Key Policy Template
```hcl
resource "aws_kms_key" "template" {
  description             = "Template KMS key with best practices"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow CloudWatch Logs"
        Effect = "Allow"
        Principal = {
          Service = "logs.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:CreateGrant",
          "kms:DescribeKey"
        ]
        Resource = "*"
        Condition = {
          ArnLike = {
            "kms:EncryptionContext:aws:logs:arn" = "arn:aws:logs:*:${data.aws_caller_identity.current.account_id}:*"
          }
        }
      }
    ]
  })
  
  tags = {
    Name        = "prod-template-key"
    Environment = "production"
    ManagedBy   = "terraform"
    Owner       = "security-team@company.com"
  }
}
```

## References
- [AWS KMS Key Rotation](https://docs.aws.amazon.com/kms/latest/developerguide/rotate-keys.html)
- [KMS Best Practices](https://docs.aws.amazon.com/kms/latest/developerguide/best-practices.html)
- [NIST SP 800-57 - Key Management](https://csrc.nist.gov/publications/detail/sp/800-57-part-1/rev-5/final)
- [PCI-DSS Requirement 3.6](https://www.pcisecuritystandards.org/)
- [Terraform aws_kms_key](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/kms_key)
- [AWS Config KMS Rules](https://docs.aws.amazon.com/config/latest/developerguide/managed-rules-by-aws-config.html)
