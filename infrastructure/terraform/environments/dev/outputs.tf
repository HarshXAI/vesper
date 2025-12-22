# Networking Outputs
output "vpc_id" {
  description = "ID of the VPC"
  value       = module.networking.vpc_id
}

output "public_subnet_ids" {
  description = "IDs of public subnets"
  value       = module.networking.public_subnet_ids
}

output "private_subnet_ids" {
  description = "IDs of private subnets"
  value       = module.networking.private_subnet_ids
}

# Database Outputs
output "database_endpoint" {
  description = "RDS endpoint"
  value       = module.database.db_endpoint
}

output "database_secret_arn" {
  description = "Secrets Manager ARN with DB credentials"
  value       = module.database.secret_arn
}

# Cache Outputs
output "redis_primary_endpoint" {
  description = "Redis primary endpoint"
  value       = module.cache.redis_primary_endpoint
}

output "redis_port" {
  description = "Redis port"
  value       = module.cache.redis_port
}

# Storage Outputs
output "data_lake_bucket" {
  description = "Data lake S3 bucket name"
  value       = module.storage.data_lake_bucket_name
}

output "model_artifacts_bucket" {
  description = "Model artifacts S3 bucket name"
  value       = module.storage.model_artifacts_bucket_name
}

# Compute Outputs
output "alb_dns_name" {
  description = "ALB DNS name - use this to access the application"
  value       = module.compute.alb_dns_name
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = module.compute.ecs_cluster_name
}

output "api_gateway_service_name" {
  description = "API Gateway ECS service name"
  value       = module.compute.api_gateway_service_name
}

# Connection Strings
output "application_url" {
  description = "Application URL"
  value       = "http://${module.compute.alb_dns_name}"
}

output "database_connection_string" {
  description = "Database connection string (password in Secrets Manager)"
  value       = module.database.connection_string
  sensitive   = true
}

output "redis_connection_string" {
  description = "Redis connection string"
  value       = module.cache.redis_connection_string
}
