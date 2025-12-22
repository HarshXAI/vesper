# VESPER Infrastructure Deployment Guide

Complete guide for deploying VESPER infrastructure on AWS using Terraform.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Initial Setup](#initial-setup)
3. [Configuration](#configuration)
4. [Deployment](#deployment)
5. [Validation](#validation)
6. [Post-Deployment](#post-deployment)
7. [Cost Management](#cost-management)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Tools

```bash
# Terraform (>= 1.0)
brew install terraform

# AWS CLI (>= 2.0)
brew install awscli

# jq (for parsing JSON outputs)
brew install jq
```

### AWS Account Setup

```bash
# Configure AWS credentials
aws configure

# Verify access
aws sts get-caller-identity

# Check quota limits
aws service-quotas get-service-quota \
  --service-code vpc \
  --quota-code L-F678F1CE
```

### Required AWS Permissions

Your IAM user/role needs:

- VPC creation and management
- EC2 (for ECS, ALB, NAT Gateway)
- RDS and ElastiCache management
- S3 bucket management
- IAM role creation
- CloudWatch access
- Secrets Manager access

## Initial Setup

### 1. Clone Repository

```bash
git clone https://github.com/HarshXAI/vesper.git
cd vesper/infrastructure/terraform/environments/dev
```

### 2. Configure Backend (Optional but Recommended)

Create S3 bucket for remote state:

```bash
# Create bucket
aws s3 mb s3://vesper-terraform-state --region us-east-1

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket vesper-terraform-state \
  --versioning-configuration Status=Enabled

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket vesper-terraform-state \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'

# Create DynamoDB table for state locking
aws dynamodb create-table \
  --table-name vesper-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

Uncomment backend block in `main.tf`:

```hcl
terraform {
  backend "s3" {
    bucket         = "vesper-terraform-state"
    key            = "dev/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "vesper-terraform-locks"
  }
}
```

### 3. Configure Variables

```bash
# Copy example variables
cp terraform.tfvars.example terraform.tfvars

# Edit with your values
vim terraform.tfvars
```

## Configuration

### Basic Settings

```hcl
# terraform.tfvars

project_name = "vesper"
environment  = "dev"
aws_region   = "us-east-1"

# Use your GitHub username
api_gateway_image = "ghcr.io/YOUR_USERNAME/vesper-api-gateway:main"
```

### Cost Optimization for Dev

```hcl
# Single-AZ RDS (saves ~$60/month)
db_multi_az = false
db_instance_class = "db.t3.medium"

# Single Redis node (saves ~$12/month)
redis_num_nodes = 1
redis_node_type = "cache.t3.micro"

# Single ECS task (saves ~$58/month)
api_gateway_desired_count = 1
api_gateway_min_count = 1
api_gateway_max_count = 2

# Enable NAT Gateway (required)
enable_nat_gateway = true

# Disable unnecessary features
enable_flow_logs = false
db_deletion_protection = false
```

### Production Settings

```hcl
# Multi-AZ for high availability
db_multi_az = true
db_instance_class = "db.r6g.xlarge"

# Redis replication
redis_num_nodes = 2
redis_node_type = "cache.r6g.large"
redis_transit_encryption = true

# ECS auto-scaling
api_gateway_desired_count = 2
api_gateway_min_count = 2
api_gateway_max_count = 10

# Enable protections
db_deletion_protection = true
alb_deletion_protection = true
db_skip_final_snapshot = false
```

## Deployment

### 1. Initialize Terraform

```bash
cd infrastructure/terraform/environments/dev

terraform init
```

Expected output:

```
Initializing modules...
Initializing the backend...
Initializing provider plugins...
Terraform has been successfully initialized!
```

### 2. Plan Infrastructure

```bash
terraform plan -out=tfplan
```

Review the plan output carefully. Expected resources:

- ~50-60 resources to create
- 0 to change
- 0 to destroy

### 3. Apply Configuration

```bash
# Apply with plan file
terraform apply tfplan

# Or apply directly (requires confirmation)
terraform apply
```

Deployment takes approximately:

- Networking: 3-5 minutes
- Database: 10-15 minutes
- Cache: 5-10 minutes
- Compute: 5-10 minutes
- **Total: 20-30 minutes**

### 4. Save Outputs

```bash
# Save all outputs to file
terraform output -json > outputs.json

# Get specific outputs
terraform output alb_dns_name
terraform output database_endpoint
terraform output redis_primary_endpoint
```

## Validation

### 1. Check ECS Service

```bash
CLUSTER=$(terraform output -raw ecs_cluster_name)

# List running tasks
aws ecs list-tasks --cluster $CLUSTER

# Describe service
aws ecs describe-services \
  --cluster $CLUSTER \
  --services vesper-api-gateway
```

Expected: `runningCount: 1` (or your desired count)

### 2. Test Health Endpoint

```bash
ALB_DNS=$(terraform output -raw alb_dns_name)

# Wait for tasks to be healthy (may take 2-3 minutes)
while ! curl -sf http://$ALB_DNS/health > /dev/null; do
  echo "Waiting for health check..."
  sleep 10
done

# Test endpoint
curl http://$ALB_DNS/health
```

Expected response:

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2025-01-29T10:30:00Z"
}
```

### 3. Check Database Connection

```bash
# Get DB endpoint
DB_ENDPOINT=$(terraform output -raw database_endpoint)

# Get secret ARN
SECRET_ARN=$(terraform output -raw database_secret_arn)

# Retrieve password
DB_PASSWORD=$(aws secretsmanager get-secret-value \
  --secret-id $SECRET_ARN \
  --query SecretString --output text | jq -r '.password')

# Test connection (from ECS task)
aws ecs execute-command \
  --cluster vesper-cluster \
  --task $(aws ecs list-tasks --cluster vesper-cluster \
    --service-name vesper-api-gateway \
    --query 'taskArns[0]' --output text) \
  --container api-gateway \
  --interactive \
  --command "psql postgresql://vesper_admin:$DB_PASSWORD@$DB_ENDPOINT/vesper -c 'SELECT version();'"
```

### 4. Verify Redis

```bash
REDIS_ENDPOINT=$(terraform output -raw redis_primary_endpoint)

# Test from ECS task
aws ecs execute-command \
  --cluster vesper-cluster \
  --task <task-arn> \
  --container api-gateway \
  --interactive \
  --command "redis-cli -h $REDIS_ENDPOINT PING"
```

Expected: `PONG`

### 5. Check S3 Buckets

```bash
# List buckets
aws s3 ls | grep vesper

# Test write access
DATA_LAKE=$(terraform output -raw data_lake_bucket)
echo "test" | aws s3 cp - s3://$DATA_LAKE/test.txt

# Verify
aws s3 ls s3://$DATA_LAKE/test.txt
```

## Post-Deployment

### 1. Configure DNS (Optional)

```bash
ALB_DNS=$(terraform output -raw alb_dns_name)
ALB_ZONE_ID=$(terraform output -raw alb_zone_id)

# Create Route53 record
aws route53 change-resource-record-sets \
  --hosted-zone-id YOUR_ZONE_ID \
  --change-batch '{
    "Changes": [{
      "Action": "CREATE",
      "ResourceRecordSet": {
        "Name": "api.vesper.example.com",
        "Type": "A",
        "AliasTarget": {
          "HostedZoneId": "'$ALB_ZONE_ID'",
          "DNSName": "'$ALB_DNS'",
          "EvaluateTargetHealth": true
        }
      }
    }]
  }'
```

### 2. Enable HTTPS (Recommended for Production)

```bash
# Request ACM certificate
CERT_ARN=$(aws acm request-certificate \
  --domain-name api.vesper.example.com \
  --validation-method DNS \
  --query CertificateArn --output text)

# Add HTTPS listener to ALB
aws elbv2 create-listener \
  --load-balancer-arn $(terraform output -raw alb_arn) \
  --protocol HTTPS \
  --port 443 \
  --certificates CertificateArn=$CERT_ARN \
  --default-actions Type=forward,TargetGroupArn=$(terraform output -raw target_group_arn)
```

### 3. Set Up CloudWatch Dashboard

```bash
# Create custom dashboard
aws cloudwatch put-dashboard \
  --dashboard-name vesper-dev \
  --dashboard-body file://cloudwatch-dashboard.json
```

### 4. Configure Backup Notifications

```bash
# Create SNS topic
TOPIC_ARN=$(aws sns create-topic \
  --name vesper-dev-alerts \
  --query TopicArn --output text)

# Subscribe email
aws sns subscribe \
  --topic-arn $TOPIC_ARN \
  --protocol email \
  --notification-endpoint your-email@example.com

# Update RDS to send notifications
aws rds modify-db-instance \
  --db-instance-identifier vesper-db \
  --enable-cloudwatch-logs-exports postgresql upgrade
```

## Cost Management

### Monitor Costs

```bash
# Get current month costs
aws ce get-cost-and-usage \
  --time-period Start=$(date +%Y-%m-01),End=$(date +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics "BlendedCost" \
  --group-by Type=SERVICE

# Get yesterday's cost
aws ce get-cost-and-usage \
  --time-period Start=$(date -v-1d +%Y-%m-%d),End=$(date +%Y-%m-%d) \
  --granularity DAILY \
  --metrics "BlendedCost"
```

### Cost Optimization Tips

**Development:**

- Stop ECS tasks when not in use: `aws ecs update-service --desired-count 0`
- Delete NAT Gateway at night (manual recreation needed)
- Use RDS snapshots and delete instance
- Reduce RDS backup retention to 1 day

**Production:**

- Use Savings Plans for ECS/RDS (up to 70% savings)
- Enable S3 Intelligent-Tiering
- Use Spot instances for non-critical tasks
- Implement auto-scaling policies
- Regular review of unused resources

### Set Up Budget Alerts

```bash
# Create budget
aws budgets create-budget \
  --account-id $(aws sts get-caller-identity --query Account --output text) \
  --budget file://budget.json \
  --notifications-with-subscribers file://notifications.json
```

## Troubleshooting

### ECS Tasks Not Starting

```bash
# Check task logs
aws logs tail /ecs/vesper/api-gateway --follow

# Check task stopped reason
aws ecs describe-tasks \
  --cluster vesper-cluster \
  --tasks $(aws ecs list-tasks --cluster vesper-cluster \
    --desired-status STOPPED --max-items 1 --query 'taskArns[0]' --output text)
```

Common issues:

- Invalid Docker image URL
- Missing secrets in Secrets Manager
- Insufficient memory/CPU
- Security group misconfiguration

### Database Connection Timeout

```bash
# Verify security group rules
aws ec2 describe-security-groups \
  --filters Name=group-name,Values=vesper-rds-* \
  --query 'SecurityGroups[0].IpPermissions'

# Check RDS availability
aws rds describe-db-instances \
  --db-instance-identifier vesper-db \
  --query 'DBInstances[0].DBInstanceStatus'
```

### High Costs

```bash
# Identify top 5 services
aws ce get-cost-and-usage \
  --time-period Start=$(date -v-7d +%Y-%m-%d),End=$(date +%Y-%m-%d) \
  --granularity DAILY \
  --metrics "BlendedCost" \
  --group-by Type=SERVICE \
  | jq -r '.ResultsByTime[].Groups | sort_by(.Metrics.BlendedCost.Amount | tonumber) | reverse | .[0:5]'
```

### Terraform State Lock

```bash
# If state is locked (after crash)
LOCK_ID=$(aws dynamodb scan \
  --table-name vesper-terraform-locks \
  --query 'Items[0].LockID.S' --output text)

# Force unlock (use with caution)
terraform force-unlock $LOCK_ID
```

## Rollback Procedure

### Minor Issues (Keep Infrastructure)

```bash
# Revert to previous task definition
aws ecs update-service \
  --cluster vesper-cluster \
  --service vesper-api-gateway \
  --task-definition vesper-api-gateway:1  # Previous version
```

### Major Issues (Destroy Infrastructure)

```bash
# Export outputs first
terraform output -json > backup-outputs.json

# Destroy all resources
terraform destroy

# Redeploy from backup
terraform apply
```

## Additional Resources

- [Terraform AWS Provider Docs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [AWS ECS Best Practices](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/)
- [AWS Cost Optimization](https://aws.amazon.com/pricing/cost-optimization/)
- [VESPER Documentation](../../README.md)

## Support

For issues:

1. Check [TROUBLESHOOTING.md](../../TROUBLESHOOTING.md)
2. Review CloudWatch logs
3. Check security group rules
4. Verify IAM permissions
5. Open GitHub issue with logs

---

**Next Steps:**

- Set up monitoring dashboards
- Configure automated backups
- Implement disaster recovery
- Set up CI/CD pipeline
- Document runbook procedures
