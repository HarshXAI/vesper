# VESPER Infrastructure as Code

Terraform configuration for deploying VESPER (Vector-Enhanced Search & Processing Engine for Reports) on AWS.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Internet                             │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
              ┌────────────────┐
              │      ALB       │  Application Load Balancer
              └────────┬───────┘
                       │
        ┌──────────────┴──────────────┐
        │                             │
        ▼                             ▼
┌───────────────┐            ┌───────────────┐
│  Public AZ-A  │            │  Public AZ-B  │
│               │            │               │
│ NAT Gateway   │            │ NAT Gateway   │
└───────┬───────┘            └───────┬───────┘
        │                            │
        ▼                            ▼
┌───────────────┐            ┌───────────────┐
│ Private AZ-A  │            │ Private AZ-B  │
│               │            │               │
│ ECS Tasks     │            │ ECS Tasks     │
│ RDS Primary   │            │ RDS Standby   │
│ Redis Node    │            │               │
└───────────────┘            └───────────────┘
        │                            │
        └────────────┬───────────────┘
                     │
                     ▼
            ┌────────────────┐
            │   S3 Buckets   │
            │                │
            │ • Data Lake    │
            │ • Models       │
            │ • Logs         │
            └────────────────┘
```

## 📦 Components

### Networking

- **VPC**: Multi-AZ with public and private subnets
- **NAT Gateway**: Per-AZ for private subnet internet access
- **Security Groups**: Isolated network segments

### Database

- **RDS PostgreSQL 15**: With pgvector extension
- **Multi-AZ**: High availability (prod only)
- **Automated Backups**: 7-day retention

### Cache

- **ElastiCache Redis 7**: Session and cache storage
- **Replication**: Multi-node with auto-failover (prod only)

### Compute

- **ECS Fargate**: Serverless container orchestration
- **Application Load Balancer**: HTTP/HTTPS routing
- **Auto-scaling**: CPU and memory-based

### Storage

- **S3 Data Lake**: Raw and processed financial data
- **S3 Model Artifacts**: ML models and embeddings
- **S3 Logs**: Application and access logs

## 🚀 Quick Start

### Prerequisites

```bash
# Install Terraform
brew install terraform  # macOS
# or
wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip

# Install AWS CLI
brew install awscli  # macOS
# or
pip install awscli

# Configure AWS credentials
aws configure
```

### Deploy Development Environment

```bash
# Navigate to dev environment
cd infrastructure/terraform/environments/dev

# Copy example variables
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars with your values
vim terraform.tfvars

# Initialize Terraform
terraform init

# Review planned changes
terraform plan

# Deploy infrastructure
terraform apply

# Get outputs
terraform output alb_dns_name
```

### Access Application

```bash
# Get ALB DNS name
ALB_DNS=$(terraform output -raw alb_dns_name)

# Test health endpoint
curl http://$ALB_DNS/health

# Access application
open http://$ALB_DNS
```

## 📁 Project Structure

```
infrastructure/terraform/
├── modules/
│   ├── networking/       # VPC, subnets, NAT, IGW
│   ├── database/         # RDS PostgreSQL with pgvector
│   ├── cache/            # ElastiCache Redis
│   ├── compute/          # ECS cluster, ALB, services
│   └── storage/          # S3 buckets
└── environments/
    ├── dev/              # Development environment
    ├── staging/          # Staging environment (TODO)
    └── prod/             # Production environment (TODO)
```

## 💰 Cost Estimates

### Development Environment (~$150/month)

- RDS db.t3.medium (single-AZ): $61/month
- ElastiCache cache.t3.micro: $12/month
- NAT Gateway (2 AZs): $64/month
- ECS Fargate (1 task): $58/month
- ALB: $21/month
- S3 + Data Transfer: ~$10/month
- **Total: ~$226/month**

### Production Environment (~$700/month)

- RDS db.r6g.xlarge (multi-AZ): $584/month
- ElastiCache cache.r6g.large (2 nodes): $260/month
- NAT Gateway (2 AZs): $64/month
- ECS Fargate (4 tasks): $232/month
- ALB: $21/month
- S3 + Data Transfer: ~$50/month
- **Total: ~$1,211/month**

## 🔧 Configuration

### Environment Variables

Edit `terraform.tfvars` to customize:

```hcl
# Basic settings
project_name = "vesper"
environment  = "dev"
aws_region   = "us-east-1"

# Cost optimization for dev
db_multi_az = false           # Save ~$60/month
redis_num_nodes = 1           # Save ~$12/month
api_gateway_desired_count = 1 # Save ~$58/month
enable_nat_gateway = true     # Required for private subnets
```

### Scaling Settings

```hcl
# API Gateway auto-scaling
api_gateway_min_count = 1
api_gateway_max_count = 4

# Scale out when:
# - CPU > 70% for 1 minute
# - Memory > 80% for 1 minute

# Scale in when:
# - CPU < 70% for 5 minutes
# - Memory < 80% for 5 minutes
```

## 🔒 Security

### Network Isolation

- Public subnets: ALB only
- Private subnets: ECS tasks, RDS, Redis
- No direct internet access to compute/data layers

### Encryption

- **At Rest**: All RDS and S3 encrypted with AES256/KMS
- **In Transit**: Optional TLS for Redis, HTTPS for ALB

### Secrets Management

- Database credentials: AWS Secrets Manager
- Redis auth tokens: AWS Secrets Manager
- IAM roles: Least-privilege policies

### Access Control

- Security groups: Port-level restrictions
- IAM policies: Resource-level permissions
- Bucket policies: Service-level access only

## 📊 Monitoring

### CloudWatch Metrics

- ECS: CPU, memory, task count
- RDS: CPU, storage, connections
- Redis: CPU, memory, evictions
- ALB: Request count, latency, errors

### Alarms Configured

- RDS CPU > 80%
- RDS free storage < 10GB
- Redis memory > 90%
- Redis evictions > 100/5min

### Logs

- ECS container logs: 7-day retention
- VPC flow logs: Optional
- ALB access logs: S3, 90-day expiration

## 🔄 CI/CD Integration

### GitHub Actions Deployment

```yaml
- name: Deploy to AWS
  run: |
    cd infrastructure/terraform/environments/dev
    terraform init
    terraform apply -auto-approve
  env:
    AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
    AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

### Docker Image Updates

```bash
# Update ECS task with new image
aws ecs update-service \
  --cluster vesper-cluster \
  --service vesper-api-gateway \
  --force-new-deployment
```

## 🛠️ Operations

### View Logs

```bash
# ECS container logs
aws logs tail /ecs/vesper/api-gateway --follow

# ALB access logs (in S3)
aws s3 ls s3://vesper-logs-dev/alb/
```

### Scale Service

```bash
# Manual scaling
aws ecs update-service \
  --cluster vesper-cluster \
  --service vesper-api-gateway \
  --desired-count 3
```

### Database Access

```bash
# Get database credentials
aws secretsmanager get-secret-value \
  --secret-id vesper-db-master-password \
  --query SecretString --output text | jq -r '.password'

# Connect via bastion or ECS Exec
aws ecs execute-command \
  --cluster vesper-cluster \
  --task <task-id> \
  --container api-gateway \
  --interactive \
  --command "psql $DATABASE_URL"
```

### Destroy Infrastructure

```bash
# DANGER: This will delete all resources
cd infrastructure/terraform/environments/dev
terraform destroy
```

## 📚 Module Documentation

Each module has detailed documentation:

- [Networking Module](modules/networking/README.md)
- [Database Module](modules/database/README.md)
- [Cache Module](modules/cache/README.md)
- [Compute Module](modules/compute/README.md)
- [Storage Module](modules/storage/README.md)

## 🤝 Contributing

1. Create feature branch: `git checkout -b feature/new-module`
2. Make changes and test: `terraform plan`
3. Commit with conventional commits: `git commit -m "feat(compute): add spot instances"`
4. Push and create PR: `git push origin feature/new-module`

## 📄 License

This infrastructure code is part of the VESPER project and follows the same license.

## 🆘 Troubleshooting

### Terraform Init Fails

```bash
# Clear cache and re-initialize
rm -rf .terraform .terraform.lock.hcl
terraform init
```

### Apply Fails on NAT Gateway

```bash
# NAT Gateways take time to provision
# Wait and retry after 2-3 minutes
terraform apply
```

### ECS Tasks Not Starting

```bash
# Check logs for errors
aws logs tail /ecs/vesper/api-gateway --follow

# Verify secrets exist
aws secretsmanager list-secrets
```

### Cannot Connect to Database

```bash
# Verify security group rules
aws ec2 describe-security-groups --group-ids <sg-id>

# Check RDS endpoint
aws rds describe-db-instances --db-instance-identifier vesper-db
```

## 🔗 Additional Resources

- [Terraform AWS Provider Docs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [AWS ECS Best Practices](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/)
- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)
- [VESPER Project Documentation](../../README.md)
