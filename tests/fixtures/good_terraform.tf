# Terraform configuration with PROPER deletion protection
# This should PASS the audit

resource "aws_db_instance" "main" {
  identifier           = "mydb-instance"
  engine               = "postgres"
  engine_version       = "14.7"
  instance_class       = "db.t3.micro"
  allocated_storage    = 20
  storage_encrypted    = true
  
  username = "admin"
  password = "changeme123"
  
  # COMPLIANT: deletion_protection is enabled
  deletion_protection = true
  
  backup_retention_period = 7
  skip_final_snapshot    = false
  final_snapshot_identifier = "mydb-final-snapshot"
  
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
  
  # COMPLIANT: deletion_protection is enabled
  deletion_protection = true
  
  backup_retention_period = 7
  skip_final_snapshot    = false
  final_snapshot_identifier = "aurora-final-snapshot"
  
  tags = {
    Environment = "production"
  }
}

resource "aws_db_instance" "replica" {
  identifier           = "mydb-replica"
  replicate_source_db  = aws_db_instance.main.identifier
  instance_class       = "db.t3.micro"
  
  # COMPLIANT: deletion_protection is enabled
  deletion_protection = true
  
  tags = {
    Environment = "production"
    Role        = "read-replica"
  }
}
