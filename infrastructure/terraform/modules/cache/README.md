# Cache Module

Creates a production-ready ElastiCache Redis cluster for caching and session storage.

## Features

- **Redis 7.0** with latest performance improvements
- **Multi-AZ Replication** for high availability
- **Automatic Failover** for primary node failures
- **Encryption at Rest** using AWS KMS
- **Optional Encryption in Transit** with auth tokens
- **Automated Snapshots** with configurable retention
- **CloudWatch Logging** for slow queries and engine logs
- **CloudWatch Alarms** for CPU, memory, and evictions

## Usage

```hcl
module "cache" {
  source = "../../modules/cache"

  project_name = "vesper"
  vpc_id       = module.networking.vpc_id
  subnet_ids   = module.networking.private_subnet_ids
  
  allowed_security_groups = [module.compute.ecs_security_group_id]
  
  node_type              = "cache.t3.micro"
  num_cache_nodes        = 2
  maxmemory_policy       = "allkeys-lru"
  
  snapshot_retention_limit    = 5
  transit_encryption_enabled  = false
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
| subnet_ids | Subnet IDs | list(string) | - | yes |
| allowed_security_groups | SGs allowed | list(string) | - | yes |
| node_type | Node instance type | string | "cache.t3.micro" | no |
| engine_version | Redis version | string | "7.0" | no |
| num_cache_nodes | Number of nodes | number | 2 | no |
| maxmemory_policy | Eviction policy | string | "allkeys-lru" | no |

## Outputs

| Name | Description |
|------|-------------|
| redis_primary_endpoint | Primary write endpoint |
| redis_reader_endpoint | Read replica endpoint |
| redis_port | Redis port (6379) |
| auth_token_secret_arn | Secrets Manager auth token ARN |
| security_group_id | Redis security group ID |

## Connection Examples

**Python (redis-py):**
```python
import redis

client = redis.Redis(
    host='vesper-redis.abc123.ng.0001.use1.cache.amazonaws.com',
    port=6379,
    decode_responses=True
)

# Set value with expiration
client.setex('session:user123', 3600, 'session_data')

# Get value
value = client.get('session:user123')
```

**With Auth Token:**
```python
client = redis.Redis(
    host='endpoint',
    port=6379,
    password='auth_token_from_secrets_manager',
    ssl=True,
    decode_responses=True
)
```

## Eviction Policies

- **allkeys-lru**: Evict least recently used keys (recommended for cache)
- **volatile-lru**: Evict LRU keys with TTL set
- **allkeys-lfu**: Evict least frequently used keys
- **noeviction**: Return errors when memory full

## Cost Considerations

**cache.t3.micro (2 nodes)**:
- Nodes: ~$24/month
- Backups: Included
- **Total**: ~$24/month

**cache.r6g.large (2 nodes)**:
- Nodes: ~$260/month
- Backups: Included
- **Total**: ~$260/month

## Monitoring

CloudWatch Alarms:
- **CPU Utilization**: Alert if > 75% for 10 minutes
- **Memory Usage**: Alert if > 90%
- **Evictions**: Alert if > 100 evictions in 5 minutes

## High Availability

- Primary node in AZ-A, replica in AZ-B
- Automatic failover in ~30-60 seconds
- Read traffic can use reader endpoint (load balanced)
- Write traffic uses primary endpoint only

## Security

- Encrypted at rest with AWS KMS
- Optional encryption in transit with TLS
- Auth token stored in AWS Secrets Manager
- Network isolation in private subnets
- Security group limits access to application tier

## Maintenance

- Automated snapshots: 03:00-05:00 UTC
- Maintenance window: Sunday 05:00-07:00 UTC
- Snapshot retention: 5 days
- Slow log and engine log retention: 7 days
