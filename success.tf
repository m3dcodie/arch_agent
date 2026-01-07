# Terraform configuration for database with delete protection enabled
# This configuration creates a secure database instance with deletion protection

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

# RDS Database Instance with Delete Protection
resource "aws_db_instance" "protected_database" {
  identifier           = "protected-db-instance"
  engine               = "postgres"
  engine_version       = "15.3"
  instance_class       = "db.t3.micro"
  allocated_storage    = 20
  storage_type         = "gp3"
  storage_encrypted    = true
  
  db_name  = "protecteddb"
  username = "admin"
  password = "ChangeMe123!" # In production, use AWS Secrets Manager
  
  # Delete Protection - ENABLED
  deletion_protection = true
  
  # Backup configuration
  backup_retention_period = 7
  backup_window          = "03:00-04:00"
  maintenance_window     = "mon:04:00-mon:05:00"
  
  # Skip final snapshot for demo purposes
  # In production, set this to false and provide final_snapshot_identifier
  skip_final_snapshot = false
  final_snapshot_identifier = "protected-db-final-snapshot"
  
  # Network configuration
  publicly_accessible = false
  
  tags = {
    Name        = "Protected Database"
    Environment = "production"
    Protection  = "enabled"
  }
}

# Output the database endpoint
output "database_endpoint" {
  description = "The connection endpoint for the protected database"
  value       = aws_db_instance.protected_database.endpoint
  sensitive   = true
}

output "database_name" {
  description = "The name of the protected database"
  value       = aws_db_instance.protected_database.db_name
}

output "deletion_protection_status" {
  description = "Status of deletion protection"
  value       = aws_db_instance.protected_database.deletion_protection
}
