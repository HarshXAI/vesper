# VESPER Infrastructure

This directory contains Terraform configurations for provisioning VESPER's AWS infrastructure as code.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Internet Gateway                            │
└────────────────────┬───────────────────────────┬────────────────────┘
                     │                           │
          ┌──────────▼──────────┐     ┌──────────▼──────────┐
          │  Public Subnet A    │     │  Public Subnet B    │
          │  (us-east-1a)       │     │  (us-east-1b)       │
          │                     │     │                     │
          │  ┌──────────────┐   │     │                     │
          │  │ ALB          │   │     │                     │
          │  │ (Port 80)    │   │     │                     │
          │  └──────────────┘   │     │                     │
          └─────────┬────────────┘     └─────────────────────┘
                    │
          ┌─────────▼──────────────────────────────────────┐
          │              NAT Gateway                        │
          └─────────┬──────────────────────────────────────┘
                    │
          ┌─────────▼──────────┐     ┌──────────────────────┐
          │  Private Subnet A  │     │  Private Subnet B    │
          │  (us-east-1a)      │     │  (us-east-1b)        │
          │                    │     │                      │
          │  ┌──────────────┐  │     │  ┌──────────────┐   │
          │  │ ECS Tasks    │  │     │  │ ECS Tasks    │   │
          │  │ API Gateway  │  │     │  │ API Gateway  │   │
          │  └──────┬───────┘  │     │  └──────┬───────┘   │
          │         │          │     │         │           │
          │  ┌──────▼───────┐  │     │  ┌──────▼───────┐   │
          │  │ RDS Primary  │  │     │  │ RDS Standby  │   │
          │  │ (Postgres16) │  │     │  │ (Multi-AZ)   │   │
          │  └──────────────┘  │     │  └──────────────┘   │
          │                    │     │                      │
          │  ┌──────────────┐  │     │  ┌──────────────┐   │
          │  │ Redis Shard1 │  │     │  │ Redis Shard2 │   │
          │  │ (Primary)    │  │     │  │ (Primary)    │   │
          │  └──────────────┘  │     │  └──────────────┘   │
          └────────────────────┘     └──────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                        Regional Services                              │
├──────────────────────────────────────────────────────────────────────┤
│  S3 Buckets: docs, artifacts, logs                                   │
│  Cognito: User Pool, Identity Pool                                   │
│  Secrets Manager: DB password, JWT key, API keys                     │
│  CloudWatch: Logs, Metrics, Alarms                                   │
└──────────────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# Deploy infrastructure
cd infrastructure
./deploy.sh dev

# Update API keys after deployment
aws secretsmanager put-secret-value \
  --secret-id vesper-dev-api-keys \
  --secret-string '{"openai_key":"sk-...","anthropic_key":"sk-ant-..."}'

# Build and deploy API Gateway
cd ../apps/api-gateway
docker build -t vesper-api-gateway:latest .
# Push to ECR and update ECS service (see full README for details)
```

## Components

- **ECS Fargate**: Serverless containers for API Gateway (2-10 tasks, auto-scaling)
- **RDS PostgreSQL 16**: Multi-AZ database with pgvector (db.r6g.large, 100-500GB)
- **ElastiCache Redis 7**: Cluster mode with 2 shards, 2 replicas each (cache.r6g.large)
- **Application Load Balancer**: HTTP/HTTPS endpoint with health checks
- **S3**: Buckets for documents, artifacts, logs (with lifecycle policies)
- **Cognito**: User authentication with JWT tokens
- **Secrets Manager**: Secure storage for credentials and API keys
- **CloudWatch**: Comprehensive logging, metrics, and alarms

## Costs

**Development**: ~$944/month  
**Production**: ~$2,770/month

See full README for detailed breakdown and optimization tips.

## Documentation

See comprehensive documentation in this README covering:

- Complete architecture diagrams
- Step-by-step deployment guide
- Configuration options
- Operational procedures
- Monitoring and alerting
- Security considerations
- Troubleshooting guide
- Cost estimation and optimization

## Prerequisites

- Terraform >= 1.5
- AWS CLI configured with appropriate credentials
- kubectl >= 1.28
- helm >= 3.12

## Quick Start

### 1. Initialize Terraform

```bash
cd terraform/environments/dev
terraform init
```

### 2. Review Plan

```bash
terraform plan -out=tfplan
```

### 3. Apply Infrastructure

```bash
terraform apply tfplan
```

### 4. Configure kubectl

```bash
aws eks update-kubeconfig --region us-east-1 --name vesper-dev
```

### 5. Deploy Kubernetes Resources

```bash
cd ../../k8s
kubectl apply -k overlays/dev
```

## Modules

Each module is self-contained and reusable:

- **networking**: Creates VPC with public/private subnets, NAT gateways
- **storage**: S3 buckets for Bronze/Silver/Gold data with lifecycle policies
- **compute**: EKS cluster with managed node groups and Cluster Autoscaler
- **database**: RDS PostgreSQL 15 with pgvector extension
- **cache**: ElastiCache Redis cluster for caching
- **streaming**: Amazon MSK for Kafka streaming
- **monitoring**: CloudWatch log groups, X-Ray tracing
- **orchestration**: MWAA (Managed Apache Airflow)

## Cost Estimation

Development environment estimated cost: ~$500-800/month

- EKS cluster: ~$75/month
- RDS PostgreSQL: ~$150/month
- ElastiCache: ~$50/month
- MSK: ~$200/month
- Data transfer & storage: ~$50-100/month
- MWAA: ~$200/month

## Security

- All data encrypted at rest (S3, RDS, EBS)
- TLS 1.3 for all data in transit
- VPC isolation with security groups
- IAM roles with least privilege
- Secrets in AWS Secrets Manager
- Network ACLs and NACLs

## Disaster Recovery

- RDS automated backups (7 days retention)
- S3 versioning enabled
- Cross-region replication (production only)
- Point-in-time recovery for RDS

## Monitoring

All infrastructure emits metrics to CloudWatch:

- EKS cluster metrics
- RDS performance insights
- MSK broker metrics
- ElastiCache Redis metrics

Alarms configured for:

- High CPU/memory usage
- Disk space
- Network throughput
- Error rates
