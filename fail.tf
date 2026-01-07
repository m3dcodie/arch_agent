# Terraform configuration for database WITHOUT delete protection
# WARNING: This configuration is vulnerable to accidental deletion

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

# RDS Database Instance WITHOUT Delete Protection
resource "aws_db_instance" "unprotected_database" {
  identifier           = "unprotected-db-instance"
  engine               = "postgres"
  engine_version       = "15.3"
  instance_class       = "db.t3.micro"
  allocated_storage    = 20
  storage_type         = "gp3"
  storage_encrypted    = true
  
  db_name  = "unprotecteddb"
  username = "admin"
  password = "ChangeMe123!" # In production, use AWS Secrets Manager
  
  # Delete Protection - DISABLED (SECURITY RISK!)
  deletion_protection = false
  
  # Backup configuration
  backup_retention_period = 7
  backup_window          = "03:00-04:00"
  maintenance_window     = "mon:04:00-mon:05:00"
  
  # Skip final snapshot - RISKY!
  skip_final_snapshot = true
  
  # Network configuration
  publicly_accessible = false
  
  tags = {
    Name        = "Unprotected Database"
    Environment = "development"
    Protection  = "disabled"
    Warning     = "No deletion protection enabled"
  }
}

# Output the database endpoint
output "database_endpoint" {
  description = "The connection endpoint for the unprotected database"
  value       = aws_db_instance.unprotected_database.endpoint
  sensitive   = true
}

output "database_name" {
  description = "The name of the unprotected database"
  value       = aws_db_instance.unprotected_database.db_name
}

output "deletion_protection_status" {
  description = "Status of deletion protection"
  value       = aws_db_instance.unprotected_database.deletion_protection
}
