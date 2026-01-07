# Terraform configuration with MISSING deletion protection
# This should FAIL the audit

resource "aws_db_instance" "main" {
  identifier           = "mydb-instance"
  engine               = "postgres"
  engine_version       = "14.7"
  instance_class       = "db.t3.micro"
  allocated_storage    = 20
  storage_encrypted    = true
  
  username = "admin"
  password = "changeme123"
  
  # VIOLATION: deletion_protection is missing!
  # This database can be accidentally deleted
  
  skip_final_snapshot = true
  
  tags = {
    Environment = "production"
    ManagedBy   = "terraform"
  }
}

resource "aws_rds_cluster" "aurora" {
  cluster_identifier      = "aurora-cluster"
  engine                  = "aurora-postgresql"
  engine_version          = "14.6"
  database_name           = "mydb"
  master_username         = "admin"
  master_password         = "changeme456"
  
  # VIOLATION: deletion_protection = false (explicitly disabled)
  deletion_protection = false
  
  skip_final_snapshot = true
  
  tags = {
    Environment = "production"
  }
}
