# Compute Module

Creates ECS Fargate cluster with Application Load Balancer and auto-scaling.

## Features

- **ECS Fargate Cluster** with Container Insights
- **Application Load Balancer** for HTTP/HTTPS traffic
- **Auto-scaling** based on CPU and memory utilization
- **Security Groups** for ALB and ECS tasks
- **IAM Roles** with least-privilege access
- **CloudWatch Logs** with 7-day retention
- **Health Checks** for container and load balancer

## Usage

```hcl
module "compute" {
  source = "../../modules/compute"

  project_name = "vesper"
  environment  = "dev"
  aws_region   = "us-east-1"
  
  vpc_id             = module.networking.vpc_id
  public_subnet_ids  = module.networking.public_subnet_ids
  private_subnet_ids = module.networking.private_subnet_ids
  
  logs_bucket_name     = module.storage.logs_bucket_name
  database_secret_arn  = module.database.secret_arn
  redis_secret_arn     = module.cache.auth_token_secret_arn
  
  api_gateway_image         = "ghcr.io/HarshXAI/vesper-api-gateway:main"
  api_gateway_cpu           = "1024"
  api_gateway_memory        = "2048"
  api_gateway_desired_count = 2
  api_gateway_min_count     = 1
  api_gateway_max_count     = 4
  
  enable_container_insights  = true
  enable_deletion_protection = false
  
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
| environment | Environment name | string | - | yes |
| vpc_id | VPC ID | string | - | yes |
| public_subnet_ids | Public subnet IDs | list(string) | - | yes |
| private_subnet_ids | Private subnet IDs | list(string) | - | yes |
| api_gateway_image | Docker image URI | string | - | yes |
| api_gateway_cpu | CPU units (1024 = 1 vCPU) | string | "1024" | no |
| api_gateway_memory | Memory in MB | string | "2048" | no |
| api_gateway_desired_count | Desired task count | number | 2 | no |

## Outputs

| Name | Description |
|------|-------------|
| alb_dns_name | ALB DNS name for access |
| ecs_cluster_name | ECS cluster name |
| ecs_security_group_id | ECS security group ID |
| ecs_task_role_arn | Task role ARN |

## Architecture

```
Internet
    |
    v
[Application Load Balancer]
    |
    +-- Target Group (api-gateway)
            |
            v
[ECS Fargate Tasks]
    |
    +-- API Gateway (2-4 tasks)
    +-- Ingestion (on-demand)
    +-- Processing (on-demand)
```

## Auto-scaling

**Scale Out:** Triggered when:
- CPU > 70% for 1 minute
- Memory > 80% for 1 minute

**Scale In:** Triggered when:
- CPU < 70% for 5 minutes
- Memory < 80% for 5 minutes

**Limits:**
- Min: 1 task
- Max: 4 tasks
- Cooldown: 60s out, 300s in

## Cost Considerations

**Fargate Pricing (per task/hour):**
- 1 vCPU, 2GB RAM: $0.08/hour = ~$58/month
- 2 tasks 24/7: ~$116/month

**ALB Pricing:**
- Fixed: $16.20/month
- LCU usage: ~$5-10/month
- **Total ALB**: ~$21-26/month

**Total (2 tasks)**: ~$137-142/month

## Security

- ALB accepts traffic from internet (0.0.0.0/0)
- ECS tasks only accept traffic from ALB
- ECS tasks in private subnets (no direct internet access)
- IAM roles with least-privilege policies
- Secrets injected from AWS Secrets Manager
- Container logs sent to CloudWatch

## Monitoring

Container Insights provides:
- CPU and memory utilization
- Network traffic
- Task count and health
- Container instance metrics

CloudWatch Logs capture:
- Application logs
- Error traces
- Request/response logs

## Deployment

ECS deployment configuration:
- **Maximum**: 200% (allows 4 tasks during deploy)
- **Minimum**: 100% (keeps 2 tasks running)
- **Deregistration delay**: 30 seconds

Rolling update process:
1. Start 2 new tasks with new image
2. Wait for health checks to pass
3. Drain connections from old tasks (30s)
4. Stop old tasks

Zero-downtime deployments guaranteed.

## ECS Exec

ECS Exec enabled for debugging:
```bash
aws ecs execute-command \
  --cluster vesper-cluster \
  --task <task-id> \
  --container api-gateway \
  --interactive \
  --command "/bin/bash"
```
