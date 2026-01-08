# Public Access Block Policy

## Policy ID
`public_access_block`

## Severity
**HIGH**

## Description
All data storage and network resources MUST have public access blocked unless explicitly required and documented. Public access creates security vulnerabilities and is the leading cause of data breaches in cloud environments.

## Scope
This policy applies to the following AWS resources:
- `aws_s3_bucket` (S3 Buckets)
- `aws_s3_bucket_public_access_block` (S3 Public Access Block)
- `aws_db_instance` (RDS Database Instances)
- `aws_rds_cluster` (Aurora Clusters)
- `aws_security_group` (Security Groups)
- `aws_elasticsearch_domain` (Elasticsearch/OpenSearch)
- `aws_redshift_cluster` (Redshift Clusters)

## Requirements
1. **S3 Buckets:** Must have `aws_s3_bucket_public_access_block` with all protections enabled
2. **RDS/Aurora:** `publicly_accessible = false` must be set
3. **Security Groups:** No ingress rules with `cidr_blocks = ["0.0.0.0/0"]` on sensitive ports
4. **Elasticsearch:** `endpoint_options.enforce_https = true` and no public access
5. **Redshift:** `publicly_accessible = false` must be set

## Rationale
Public access restrictions are critical for:
1. **Data Breach Prevention:** 90% of cloud breaches involve publicly exposed resources
2. **Compliance:** Required by most security frameworks (CIS, NIST, PCI-DSS)
3. **Attack Surface Reduction:** Limits exposure to internet-based attacks
4. **Regulatory Requirements:** GDPR, HIPAA require access controls
5. **Cost of Breach:** Average data breach costs $4.35M (IBM 2022)

## Examples

### ✅ Compliant - S3 with Public Access Block
```hcl
resource "aws_s3_bucket" "private_data" {
  bucket = "company-private-data"
}

resource "aws_s3_bucket_public_access_block" "private_data" {
  bucket = aws_s3_bucket.private_data.id

  block_public_acls       = true  # ✓ Block public ACLs
  block_public_policy     = true  # ✓ Block public bucket policies
  ignore_public_acls      = true  # ✓ Ignore public ACLs
  restrict_public_buckets = true  # ✓ Restrict public bucket policies
}
```

### ✅ Compliant - RDS in Private Subnet
```hcl
resource "aws_db_instance" "private_db" {
  identifier           = "private-database"
  engine               = "postgres"
  instance_class       = "db.t3.medium"
  allocated_storage    = 100
  
  publicly_accessible = false  # ✓ Not publicly accessible
  
  db_subnet_group_name   = aws_db_subnet_group.private.name
  vpc_security_group_ids = [aws_security_group.database.id]
  
  username = "admin"
  password = var.db_password
}
```

### ✅ Compliant - Security Group with Restricted Access
```hcl
resource "aws_security_group" "app" {
  name        = "app-security-group"
  description = "Security group for application servers"
  vpc_id      = aws_vpc.main.id

  # ✓ Only allow specific CIDR blocks
  ingress {
    description = "HTTPS from corporate network"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"]  # ✓ Private network only
  }

  ingress {
    description     = "HTTP from load balancer"
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]  # ✓ Security group reference
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]  # ✓ Egress is acceptable
  }
}
```

### ✅ Compliant - Aurora Cluster Private
```hcl
resource "aws_rds_cluster" "private_aurora" {
  cluster_identifier = "private-aurora-cluster"
  engine             = "aurora-postgresql"
  engine_version     = "14.6"
  database_name      = "mydb"
  master_username    = "admin"
  master_password    = var.db_password
  
  publicly_accessible = false  # ✓ Not publicly accessible
  
  db_subnet_group_name   = aws_db_subnet_group.private.name
  vpc_security_group_ids = [aws_security_group.aurora.id]
}
```

### ✅ Compliant - Redshift in Private Subnet
```hcl
resource "aws_redshift_cluster" "analytics" {
  cluster_identifier = "analytics-cluster"
  database_name      = "analytics"
  master_username    = "admin"
  master_password    = var.redshift_password
  node_type          = "dc2.large"
  cluster_type       = "single-node"
  
  publicly_accessible = false  # ✓ Not publicly accessible
  
  cluster_subnet_group_name = aws_redshift_subnet_group.private.name
  vpc_security_group_ids    = [aws_security_group.redshift.id]
}
```

### ❌ Non-Compliant - S3 without Public Access Block
```hcl
resource "aws_s3_bucket" "data" {
  bucket = "company-data-bucket"
  
  # ✗ No aws_s3_bucket_public_access_block defined
  # This allows public access to be configured later
}
```

### ❌ Non-Compliant - S3 with Public ACL
```hcl
resource "aws_s3_bucket" "public_data" {
  bucket = "company-public-data"
}

resource "aws_s3_bucket_acl" "public_data" {
  bucket = aws_s3_bucket.public_data.id
  acl    = "public-read"  # ✗ Public read access
}
```

### ❌ Non-Compliant - S3 with Partial Protection
```hcl
resource "aws_s3_bucket" "data" {
  bucket = "company-data"
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket = aws_s3_bucket.data.id

  block_public_acls       = true
  block_public_policy     = false  # ✗ Public policies allowed
  ignore_public_acls      = true
  restrict_public_buckets = false  # ✗ Public buckets allowed
}
```

### ❌ Non-Compliant - RDS Publicly Accessible
```hcl
resource "aws_db_instance" "public_db" {
  identifier           = "public-database"
  engine               = "postgres"
  instance_class       = "db.t3.medium"
  allocated_storage    = 100
  
  publicly_accessible = true  # ✗ Publicly accessible
  
  username = "admin"
  password = var.db_password
}
```

### ❌ Non-Compliant - RDS Missing publicly_accessible
```hcl
resource "aws_db_instance" "database" {
  identifier           = "my-database"
  engine               = "mysql"
  instance_class       = "db.t3.small"
  allocated_storage    = 20
  
  # ✗ Missing publicly_accessible (may default to true in some configurations)
  
  username = "admin"
  password = var.db_password
}
```

### ❌ Non-Compliant - Security Group Open to Internet
```hcl
resource "aws_security_group" "database" {
  name        = "database-sg"
  description = "Database security group"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "PostgreSQL from anywhere"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]  # ✗ Open to entire internet
  }
}
```

### ❌ Non-Compliant - Security Group with Multiple Open Ports
```hcl
resource "aws_security_group" "app" {
  name   = "app-sg"
  vpc_id = aws_vpc.main.id

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]  # ✗ SSH open to internet
  }

  ingress {
    from_port   = 3306
    to_port     = 3306
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]  # ✗ MySQL open to internet
  }
}
```

### ❌ Non-Compliant - Aurora Publicly Accessible
```hcl
resource "aws_rds_cluster" "public_aurora" {
  cluster_identifier = "public-aurora"
  engine             = "aurora-mysql"
  master_username    = "admin"
  master_password    = var.db_password
  
  publicly_accessible = true  # ✗ Publicly accessible
}
```

## Remediation

### For S3 Buckets
Add public access block configuration:
```hcl
resource "aws_s3_bucket_public_access_block" "example" {
  bucket = aws_s3_bucket.example.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```

Remove any public ACLs:
```hcl
# Remove or change this:
# acl = "public-read"
```

### For RDS/Aurora
Set publicly_accessible to false:
```hcl
publicly_accessible = false
```

Ensure database is in private subnet:
```hcl
db_subnet_group_name = aws_db_subnet_group.private.name
```

### For Security Groups
Replace `0.0.0.0/0` with specific CIDR blocks:
```hcl
ingress {
  from_port   = 443
  to_port     = 443
  protocol    = "tcp"
  cidr_blocks = ["10.0.0.0/8"]  # Corporate network only
}
```

Or use security group references:
```hcl
ingress {
  from_port       = 3306
  to_port         = 3306
  protocol        = "tcp"
  security_groups = [aws_security_group.app.id]  # Only from app servers
}
```

### For Redshift
Set publicly_accessible to false:
```hcl
publicly_accessible = false
cluster_subnet_group_name = aws_redshift_subnet_group.private.name
```

## Exceptions

### Legitimate Public Access Scenarios
Public access may be acceptable for:
1. **Static Website Hosting:** S3 buckets serving public websites
2. **Public APIs:** API Gateway endpoints (with authentication)
3. **CDN Origins:** CloudFront distributions (with OAI/OAC)
4. **Public Documentation:** Read-only public content

### Exception Process
If public access is required:
1. Document business justification in resource tags
2. Implement additional security controls (WAF, authentication)
3. Get security team approval
4. Add exception tag: `PublicAccessApproved = "true"`
5. Regular security reviews (quarterly)

### Exception Example
```hcl
resource "aws_s3_bucket" "public_website" {
  bucket = "company-public-website"
  
  tags = {
    PublicAccessApproved = "true"
    Justification        = "Public marketing website"
    ApprovedBy           = "security-team@company.com"
    ApprovalDate         = "2024-01-15"
    ReviewDate           = "2024-04-15"
  }
}

# Still implement security controls
resource "aws_s3_bucket_public_access_block" "public_website" {
  bucket = aws_s3_bucket.public_website.id

  block_public_acls       = true  # Still block ACLs
  block_public_policy     = false # Allow bucket policy for website
  ignore_public_acls      = true
  restrict_public_buckets = false
}
```

## Detection and Response

### Monitoring
Set up CloudWatch alarms for:
- S3 bucket policy changes
- Security group rule modifications
- RDS instance modifications

### Automated Response
Consider AWS Config rules:
- `s3-bucket-public-read-prohibited`
- `s3-bucket-public-write-prohibited`
- `restricted-ssh`
- `restricted-common-ports`

## References
- [AWS S3 Block Public Access](https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-control-block-public-access.html)
- [AWS RDS Security](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.html)
- [AWS Security Group Best Practices](https://docs.aws.amazon.com/vpc/latest/userguide/VPC_SecurityGroups.html)
- [CIS AWS Foundations Benchmark](https://www.cisecurity.org/benchmark/amazon_web_services)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [Terraform aws_s3_bucket_public_access_block](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_public_access_block)
- [Terraform aws_db_instance](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/db_instance)
- [Capital One Breach Case Study](https://www.capitalone.com/digital/facts2019/) - Example of misconfigured security group
