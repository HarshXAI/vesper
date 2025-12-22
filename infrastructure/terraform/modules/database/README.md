# Database Module

Creates a production-ready RDS PostgreSQL instance with pgvector extension support.

## Features

- **PostgreSQL 15** with pgvector extension for vector similarity search
- **Multi-AZ Deployment** for high availability
- **Automated Backups** with configurable retention
- **Encryption at Rest** using AWS KMS
- **Enhanced Monitoring** with CloudWatch integration
- **Secrets Management** using AWS Secrets Manager
- **CloudWatch Alarms** for CPU, storage, and connections
- **Auto-scaling Storage** to prevent out-of-space issues

## Usage

```hcl
module "database" {
  source = "../../modules/database"

  project_name = "vesper"
  vpc_id       = module.networking.vpc_id
  subnet_ids   = module.networking.private_subnet_ids
  
  allowed_security_groups = [module.compute.ecs_security_group_id]
  
  instance_class        = "db.t3.medium"
  allocated_storage     = 100
  max_allocated_storage = 500
  
  multi_az                    = true
  backup_retention_period     = 7
  enable_deletion_protection  = true
  enable_cloudwatch_alarms    = true
  
  tags = {
    Environment = "dev"
    ManagedBy   = "Terraform"
  }
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| project_name | Project name | string | - | yes |
| vpc_id | VPC ID | string | - | yes |
| subnet_ids | Subnet IDs for DB | list(string) | - | yes |
| allowed_security_groups | SGs allowed to connect | list(string) | - | yes |
| instance_class | RDS instance class | string | "db.t3.medium" | no |
| engine_version | PostgreSQL version | string | "15.4" | no |
| allocated_storage | Initial storage (GB) | number | 100 | no |
| max_allocated_storage | Max storage (GB) | number | 500 | no |
| multi_az | Enable Multi-AZ | bool | true | no |
| backup_retention_period | Backup retention days | number | 7 | no |

## Outputs

| Name | Description |
|------|-------------|
| db_endpoint | Database connection endpoint |
| db_address | Database hostname |
| db_port | Database port (5432) |
| secret_arn | Secrets Manager secret ARN with credentials |
| security_group_id | RDS security group ID |

## pgvector Extension

The module configures PostgreSQL with the pgvector extension for vector operations:

```sql
-- Enable extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create table with vector column
CREATE TABLE embeddings (
  id SERIAL PRIMARY KEY,
  content TEXT,
  embedding vector(1536)
);

-- Create index for fast similarity search
CREATE INDEX ON embeddings USING ivfflat (embedding vector_cosine_ops);
```

## Cost Considerations

**db.t3.medium (Multi-AZ)**:
- Instance: ~$122/month
- Storage (100GB gp3): ~$25/month
- Backups: Included (same size as DB)
- **Total**: ~$147/month

**db.r6g.xlarge (Production)**:
- Instance: ~$584/month
- Storage (500GB gp3): ~$125/month
- **Total**: ~$709/month

## Monitoring

CloudWatch Alarms created:
- **CPU Utilization**: Alert if > 80% for 10 minutes
- **Free Storage**: Alert if < 10GB
- **Database Connections**: Alert if > 80% of max

## Security

- Storage encrypted at rest with AWS KMS
- Master password stored in AWS Secrets Manager
- Network isolation in private subnets
- Security group restricts access to application layer only
- Automated backups with 7-day retention
- Deletion protection enabled by default

## Maintenance

- Automated backups: 03:00-04:00 UTC
- Maintenance window: Monday 04:00-05:00 UTC
- Auto-minor-version-upgrade: Disabled (manual control)
- Enhanced monitoring: 60-second intervals
