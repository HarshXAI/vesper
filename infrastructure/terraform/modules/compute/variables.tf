variable "project_name" {
  description = "Name of the project, used for resource naming"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "vpc_id" {
  description = "ID of the VPC"
  type        = string
}

variable "public_subnet_ids" {
  description = "List of public subnet IDs for ALB"
  type        = list(string)
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for ECS tasks"
  type        = list(string)
}

variable "logs_bucket_name" {
  description = "Name of S3 bucket for ALB access logs"
  type        = string
}

variable "database_secret_arn" {
  description = "ARN of Secrets Manager secret with database credentials"
  type        = string
}

variable "redis_secret_arn" {
  description = "ARN of Secrets Manager secret with Redis credentials"
  type        = string
}

variable "service_names" {
  description = "List of service names for CloudWatch log groups"
  type        = list(string)
  default     = ["api-gateway", "ingestion", "processing"]
}

variable "api_gateway_image" {
  description = "Docker image for API Gateway service"
  type        = string
}

variable "api_gateway_cpu" {
  description = "CPU units for API Gateway task (1024 = 1 vCPU)"
  type        = string
  default     = "1024"
}

variable "api_gateway_memory" {
  description = "Memory for API Gateway task in MB"
  type        = string
  default     = "2048"
}

variable "api_gateway_desired_count" {
  description = "Desired number of API Gateway tasks"
  type        = number
  default     = 2
}

variable "api_gateway_min_count" {
  description = "Minimum number of API Gateway tasks"
  type        = number
  default     = 1
}

variable "api_gateway_max_count" {
  description = "Maximum number of API Gateway tasks"
  type        = number
  default     = 4
}

variable "enable_deletion_protection" {
  description = "Enable deletion protection for ALB"
  type        = bool
  default     = false
}

variable "enable_container_insights" {
  description = "Enable ECS Container Insights"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# Blue/Green Deployment Variables
variable "blue_weight" {
  description = "Traffic weight for blue (primary) target group (0-100)"
  type        = number
  default     = 100

  validation {
    condition     = var.blue_weight >= 0 && var.blue_weight <= 100
    error_message = "Blue weight must be between 0 and 100."
  }
}

variable "green_weight" {
  description = "Traffic weight for green (canary) target group (0-100)"
  type        = number
  default     = 0

  validation {
    condition     = var.green_weight >= 0 && var.green_weight <= 100
    error_message = "Green weight must be between 0 and 100."
  }
}
