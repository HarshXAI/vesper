# =============================================================================
# SSM Parameter Store Module
# =============================================================================
# Manages secrets and configuration in AWS Systems Manager Parameter Store
# Provides secure storage for API keys, database credentials, and app config
# =============================================================================

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

# -----------------------------------------------------------------------------
# Variables
# -----------------------------------------------------------------------------

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "kms_key_arn" {
  description = "ARN of the KMS key for encrypting SecureString parameters"
  type        = string
  default     = null
}

variable "openai_api_key" {
  description = "OpenAI API key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "database_url" {
  description = "PostgreSQL database connection URL"
  type        = string
  sensitive   = true
  default     = ""
}

variable "redis_url" {
  description = "Redis connection URL"
  type        = string
  sensitive   = true
  default     = ""
}

variable "cognito_user_pool_id" {
  description = "Cognito User Pool ID"
  type        = string
  default     = ""
}

variable "cognito_client_id" {
  description = "Cognito App Client ID"
  type        = string
  default     = ""
}

variable "grafana_api_key" {
  description = "Grafana API key for dashboard access"
  type        = string
  sensitive   = true
  default     = ""
}

variable "sentry_dsn" {
  description = "Sentry DSN for error tracking"
  type        = string
  sensitive   = true
  default     = ""
}

variable "slack_webhook_url" {
  description = "Slack webhook URL for alerts"
  type        = string
  sensitive   = true
  default     = ""
}

variable "jwks_url" {
  description = "JWKS URL for JWT validation (optional, computed from Cognito if not set)"
  type        = string
  default     = ""
}

variable "cognito_analyst_client_id" {
  description = "Cognito Analyst UI App Client ID"
  type        = string
  default     = ""
}

variable "cognito_ops_client_id" {
  description = "Cognito Ops UI App Client ID"
  type        = string
  default     = ""
}

variable "cognito_api_client_id" {
  description = "Cognito API App Client ID"
  type        = string
  default     = ""
}

variable "additional_parameters" {
  description = "Additional custom parameters to create"
  type = map(object({
    value       = string
    type        = string  # String or SecureString
    description = string
  }))
  default = {}
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

# -----------------------------------------------------------------------------
# Local Values
# -----------------------------------------------------------------------------

locals {
  name_prefix = "/vesper/${var.environment}"
  
  default_tags = {
    Environment = var.environment
    Project     = "vesper"
    ManagedBy   = "terraform"
    Module      = "ssm"
  }
  
  all_tags = merge(local.default_tags, var.tags)
  
  # Define core parameters with their configurations
  core_parameters = {
    # API Keys
    openai_api_key = {
      value       = var.openai_api_key
      type        = "SecureString"
      description = "OpenAI API key for embeddings and completions"
      tier        = "Standard"
    }
    
    # Database
    database_url = {
      value       = var.database_url
      type        = "SecureString"
      description = "PostgreSQL connection string with pgvector"
      tier        = "Standard"
    }
    
    # Cache
    redis_url = {
      value       = var.redis_url
      type        = "SecureString"
      description = "Redis connection URL for caching"
      tier        = "Standard"
    }
    
    # Auth
    cognito_user_pool_id = {
      value       = var.cognito_user_pool_id
      type        = "String"
      description = "AWS Cognito User Pool ID"
      tier        = "Standard"
    }
    
    cognito_client_id = {
      value       = var.cognito_client_id
      type        = "String"
      description = "AWS Cognito App Client ID"
      tier        = "Standard"
    }
    
    # Observability
    grafana_api_key = {
      value       = var.grafana_api_key
      type        = "SecureString"
      description = "Grafana API key for dashboard access"
      tier        = "Standard"
    }
    
    sentry_dsn = {
      value       = var.sentry_dsn
      type        = "SecureString"
      description = "Sentry DSN for error tracking"
      tier        = "Standard"
    }
    
    slack_webhook_url = {
      value       = var.slack_webhook_url
      type        = "SecureString"
      description = "Slack webhook URL for alerts"
      tier        = "Standard"
    }
    
    # JWKS
    jwks_url = {
      value       = var.jwks_url != "" ? var.jwks_url : "https://cognito-idp.${data.aws_region.current.name}.amazonaws.com/${var.cognito_user_pool_id}/.well-known/jwks.json"
      type        = "String"
      description = "JWKS URL for JWT validation"
      tier        = "Standard"
    }
    
    # Additional Cognito clients
    cognito_analyst_client_id = {
      value       = var.cognito_analyst_client_id
      type        = "String"
      description = "Cognito Analyst UI App Client ID"
      tier        = "Standard"
    }
    
    cognito_ops_client_id = {
      value       = var.cognito_ops_client_id
      type        = "String"
      description = "Cognito Ops UI App Client ID"
      tier        = "Standard"
    }
    
    cognito_api_client_id = {
      value       = var.cognito_api_client_id
      type        = "String"
      description = "Cognito API App Client ID"
      tier        = "Standard"
    }
  }
  
  # Filter out empty parameters
  active_parameters = {
    for k, v in local.core_parameters : k => v if v.value != ""
  }
}

# -----------------------------------------------------------------------------
# KMS Key for Parameter Encryption (if not provided)
# -----------------------------------------------------------------------------

resource "aws_kms_key" "ssm" {
  count = var.kms_key_arn == null ? 1 : 0
  
  description             = "KMS key for Vesper SSM parameters"
  deletion_window_in_days = 7
  enable_key_rotation     = true
  
  tags = merge(local.all_tags, {
    Name = "vesper-${var.environment}-ssm-key"
  })
}

resource "aws_kms_alias" "ssm" {
  count = var.kms_key_arn == null ? 1 : 0
  
  name          = "alias/vesper-${var.environment}-ssm"
  target_key_id = aws_kms_key.ssm[0].key_id
}

locals {
  kms_key_id = var.kms_key_arn != null ? var.kms_key_arn : aws_kms_key.ssm[0].arn
}

# -----------------------------------------------------------------------------
# Core SSM Parameters
# -----------------------------------------------------------------------------

resource "aws_ssm_parameter" "core" {
  for_each = local.active_parameters
  
  name        = "${local.name_prefix}/${replace(each.key, "_", "-")}"
  description = each.value.description
  type        = each.value.type
  value       = each.value.value
  tier        = each.value.tier
  key_id      = each.value.type == "SecureString" ? local.kms_key_id : null
  
  tags = merge(local.all_tags, {
    Name      = each.key
    Sensitive = each.value.type == "SecureString" ? "true" : "false"
  })
  
  lifecycle {
    ignore_changes = [value]
  }
}

# -----------------------------------------------------------------------------
# Additional Custom Parameters
# -----------------------------------------------------------------------------

resource "aws_ssm_parameter" "additional" {
  for_each = var.additional_parameters
  
  name        = "${local.name_prefix}/${each.key}"
  description = each.value.description
  type        = each.value.type
  value       = each.value.value
  tier        = "Standard"
  key_id      = each.value.type == "SecureString" ? local.kms_key_id : null
  
  tags = merge(local.all_tags, {
    Name      = each.key
    Sensitive = each.value.type == "SecureString" ? "true" : "false"
  })
}

# -----------------------------------------------------------------------------
# Application Configuration Parameters
# -----------------------------------------------------------------------------

resource "aws_ssm_parameter" "app_config" {
  name        = "${local.name_prefix}/config/app"
  description = "Application configuration JSON"
  type        = "String"
  tier        = "Standard"
  
  value = jsonencode({
    environment          = var.environment
    log_level           = var.environment == "prod" ? "INFO" : "DEBUG"
    enable_tracing      = true
    enable_metrics      = true
    max_tokens          = 4096
    temperature         = 0.7
    embedding_model     = "text-embedding-3-small"
    completion_model    = "gpt-4o"
    chunk_size          = 512
    chunk_overlap       = 50
    similarity_threshold = 0.7
    top_k_results       = 10
  })
  
  tags = merge(local.all_tags, {
    Name = "app-config"
  })
}

resource "aws_ssm_parameter" "feature_flags" {
  name        = "${local.name_prefix}/config/features"
  description = "Feature flags configuration"
  type        = "String"
  tier        = "Standard"
  
  value = jsonencode({
    enable_streaming           = true
    enable_citations           = true
    enable_guardrails          = true
    enable_budget_enforcement  = true
    enable_cache_warmers       = var.environment == "prod"
    enable_eval_runs           = true
    enable_dag_triggers        = true
    maintenance_mode           = false
  })
  
  tags = merge(local.all_tags, {
    Name = "feature-flags"
  })
}

resource "aws_ssm_parameter" "rate_limits" {
  name        = "${local.name_prefix}/config/rate-limits"
  description = "Rate limiting configuration"
  type        = "String"
  tier        = "Standard"
  
  value = jsonencode({
    default_rpm           = 60
    default_tpm           = 100000
    burst_multiplier      = 2
    tenant_budget_daily   = 100.0
    global_budget_daily   = 10000.0
    cache_ttl_seconds     = 3600
    embedding_batch_size  = 100
  })
  
  tags = merge(local.all_tags, {
    Name = "rate-limits"
  })
}

# -----------------------------------------------------------------------------
# IAM Policy for Parameter Access
# -----------------------------------------------------------------------------

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

resource "aws_iam_policy" "ssm_read" {
  name        = "vesper-${var.environment}-ssm-read"
  description = "Read access to Vesper SSM parameters"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "GetParameters"
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:GetParametersByPath"
        ]
        Resource = [
          "arn:aws:ssm:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:parameter${local.name_prefix}/*"
        ]
      },
      {
        Sid    = "DecryptParameters"
        Effect = "Allow"
        Action = [
          "kms:Decrypt"
        ]
        Resource = [local.kms_key_id]
      }
    ]
  })
  
  tags = local.all_tags
}

resource "aws_iam_policy" "ssm_write" {
  name        = "vesper-${var.environment}-ssm-write"
  description = "Write access to Vesper SSM parameters"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ManageParameters"
        Effect = "Allow"
        Action = [
          "ssm:PutParameter",
          "ssm:DeleteParameter",
          "ssm:AddTagsToResource",
          "ssm:RemoveTagsFromResource"
        ]
        Resource = [
          "arn:aws:ssm:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:parameter${local.name_prefix}/*"
        ]
      },
      {
        Sid    = "EncryptParameters"
        Effect = "Allow"
        Action = [
          "kms:Encrypt",
          "kms:GenerateDataKey"
        ]
        Resource = [local.kms_key_id]
      }
    ]
  })
  
  tags = local.all_tags
}

# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------

output "parameter_prefix" {
  description = "SSM parameter path prefix"
  value       = local.name_prefix
}

output "kms_key_arn" {
  description = "ARN of the KMS key used for encryption"
  value       = local.kms_key_id
}

output "ssm_read_policy_arn" {
  description = "ARN of the IAM policy for reading SSM parameters"
  value       = aws_iam_policy.ssm_read.arn
}

output "ssm_write_policy_arn" {
  description = "ARN of the IAM policy for writing SSM parameters"
  value       = aws_iam_policy.ssm_write.arn
}

output "parameter_arns" {
  description = "Map of parameter names to their ARNs"
  value       = { for k, v in aws_ssm_parameter.core : k => v.arn }
}

output "app_config_arn" {
  description = "ARN of the app configuration parameter"
  value       = aws_ssm_parameter.app_config.arn
}

output "feature_flags_arn" {
  description = "ARN of the feature flags parameter"
  value       = aws_ssm_parameter.feature_flags.arn
}
