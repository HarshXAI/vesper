# General Variables
variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "vesper"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

# Networking Variables
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of availability zones"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets"
  type        = list(string)
  default     = ["10.0.11.0/24", "10.0.12.0/24"]
}

variable "enable_nat_gateway" {
  description = "Enable NAT Gateway"
  type        = bool
  default     = true
}

variable "enable_flow_logs" {
  description = "Enable VPC Flow Logs"
  type        = bool
  default     = false
}

# Database Variables
variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.medium"
}

variable "db_engine_version" {
  description = "PostgreSQL version"
  type        = string
  default     = "15.4"
}

variable "db_allocated_storage" {
  description = "Initial storage in GB"
  type        = number
  default     = 100
}

variable "db_max_allocated_storage" {
  description = "Max storage for autoscaling in GB"
  type        = number
  default     = 500
}

variable "db_name" {
  description = "Database name"
  type        = string
  default     = "vesper"
}

variable "db_master_username" {
  description = "Master username"
  type        = string
  default     = "vesper_admin"
}

variable "db_multi_az" {
  description = "Enable Multi-AZ"
  type        = bool
  default     = false # Single AZ for dev to save costs
}

variable "db_backup_retention_period" {
  description = "Backup retention in days"
  type        = number
  default     = 7
}

variable "db_deletion_protection" {
  description = "Enable deletion protection"
  type        = bool
  default     = false # Disabled for dev
}

variable "db_skip_final_snapshot" {
  description = "Skip final snapshot on deletion"
  type        = bool
  default     = true # Enabled for dev
}

variable "db_enable_alarms" {
  description = "Enable CloudWatch alarms"
  type        = bool
  default     = true
}

# Cache Variables
variable "redis_node_type" {
  description = "Redis node type"
  type        = string
  default     = "cache.t3.micro"
}

variable "redis_engine_version" {
  description = "Redis version"
  type        = string
  default     = "7.0"
}

variable "redis_num_nodes" {
  description = "Number of cache nodes"
  type        = number
  default     = 1 # Single node for dev
}

variable "redis_maxmemory_policy" {
  description = "Eviction policy"
  type        = string
  default     = "allkeys-lru"
}

variable "redis_snapshot_retention" {
  description = "Snapshot retention in days"
  type        = number
  default     = 5
}

variable "redis_transit_encryption" {
  description = "Enable encryption in transit"
  type        = bool
  default     = false # Disabled for dev simplicity
}

variable "redis_enable_alarms" {
  description = "Enable CloudWatch alarms"
  type        = bool
  default     = true
}

# Storage Variables
variable "s3_enable_versioning" {
  description = "Enable S3 versioning"
  type        = bool
  default     = true
}

# Compute Variables
variable "api_gateway_image" {
  description = "Docker image for API Gateway"
  type        = string
  default     = "ghcr.io/harshxai/vesper-api-gateway:main"
}

variable "api_gateway_cpu" {
  description = "CPU units (1024 = 1 vCPU)"
  type        = string
  default     = "1024"
}

variable "api_gateway_memory" {
  description = "Memory in MB"
  type        = string
  default     = "2048"
}

variable "api_gateway_desired_count" {
  description = "Desired task count"
  type        = number
  default     = 1 # Single task for dev
}

variable "api_gateway_min_count" {
  description = "Minimum task count"
  type        = number
  default     = 1
}

variable "api_gateway_max_count" {
  description = "Maximum task count"
  type        = number
  default     = 2 # Limited scaling for dev
}

variable "ecs_enable_container_insights" {
  description = "Enable Container Insights"
  type        = bool
  default     = true
}

variable "alb_deletion_protection" {
  description = "Enable ALB deletion protection"
  type        = bool
  default     = false
}
