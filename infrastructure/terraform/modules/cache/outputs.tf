output "redis_cluster_id" {
  description = "ID of the Redis replication group"
  value       = aws_elasticache_replication_group.main.id
}

output "redis_primary_endpoint" {
  description = "Primary endpoint address for Redis"
  value       = aws_elasticache_replication_group.main.primary_endpoint_address
}

output "redis_reader_endpoint" {
  description = "Reader endpoint address for Redis (read replicas)"
  value       = aws_elasticache_replication_group.main.reader_endpoint_address
}

output "redis_configuration_endpoint" {
  description = "Configuration endpoint for Redis cluster"
  value       = aws_elasticache_replication_group.main.configuration_endpoint_address
}

output "redis_port" {
  description = "Port for Redis connections"
  value       = 6379
}

output "security_group_id" {
  description = "ID of the Redis security group"
  value       = aws_security_group.redis.id
}

output "auth_token_secret_arn" {
  description = "ARN of Secrets Manager secret with Redis auth token"
  value       = var.transit_encryption_enabled ? aws_secretsmanager_secret.redis_auth[0].arn : null
}

output "redis_connection_string" {
  description = "Redis connection string (without auth token if encryption enabled)"
  value       = "redis://${aws_elasticache_replication_group.main.primary_endpoint_address}:6379"
}
