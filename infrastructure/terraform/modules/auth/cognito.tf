# VESPER Authentication Module - Cognito User Pool

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "vesper"
}

variable "analyst_ui_callback_urls" {
  description = "Callback URLs for Analyst UI"
  type        = list(string)
  default     = ["http://localhost:3000/api/auth/callback/cognito"]
}

variable "ops_ui_callback_urls" {
  description = "Callback URLs for Ops UI"
  type        = list(string)
  default     = ["http://localhost:3001/api/auth/callback/cognito"]
}

variable "analyst_ui_logout_urls" {
  description = "Logout URLs for Analyst UI"
  type        = list(string)
  default     = ["http://localhost:3000"]
}

variable "ops_ui_logout_urls" {
  description = "Logout URLs for Ops UI"
  type        = list(string)
  default     = ["http://localhost:3001"]
}

variable "admin_email" {
  description = "Email for admin user to create"
  type        = string
  default     = ""
}

# ============================================================================
# Cognito User Pool
# ============================================================================

resource "aws_cognito_user_pool" "main" {
  name = "${var.project_name}-${var.environment}"
  
  # Username configuration
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  
  # Password policy
  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = true
    require_uppercase                = true
    temporary_password_validity_days = 7
  }
  
  # MFA configuration
  mfa_configuration = var.environment == "prod" ? "ON" : "OPTIONAL"
  
  software_token_mfa_configuration {
    enabled = true
  }
  
  # Account recovery
  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }
  
  # User attributes
  schema {
    name                     = "tenant_id"
    attribute_data_type      = "String"
    developer_only_attribute = false
    mutable                  = true
    required                 = false
    
    string_attribute_constraints {
      min_length = 1
      max_length = 100
    }
  }
  
  schema {
    name                     = "organization"
    attribute_data_type      = "String"
    developer_only_attribute = false
    mutable                  = true
    required                 = false
    
    string_attribute_constraints {
      min_length = 0
      max_length = 200
    }
  }
  
  # Email configuration
  email_configuration {
    email_sending_account = "COGNITO_DEFAULT"
  }
  
  # Verification message
  verification_message_template {
    default_email_option = "CONFIRM_WITH_CODE"
    email_subject        = "VESPER - Verify your email"
    email_message        = "Your VESPER verification code is {####}"
  }
  
  # Admin creation settings
  admin_create_user_config {
    allow_admin_create_user_only = var.environment == "prod"
    
    invite_message_template {
      email_subject = "VESPER - Your account has been created"
      email_message = "Your VESPER account has been created. Username: {username}, Temporary Password: {####}"
      sms_message   = "VESPER: Username {username}, Password {####}"
    }
  }
  
  # Lambda triggers (optional)
  # lambda_config {
  #   pre_sign_up = aws_lambda_function.pre_signup.arn
  # }
  
  # Device tracking
  device_configuration {
    challenge_required_on_new_device      = true
    device_only_remembered_on_user_prompt = true
  }
  
  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

# ============================================================================
# User Pool Domain
# ============================================================================

resource "aws_cognito_user_pool_domain" "main" {
  domain       = "${var.project_name}-${var.environment}"
  user_pool_id = aws_cognito_user_pool.main.id
}

# ============================================================================
# User Pool Groups
# ============================================================================

resource "aws_cognito_user_group" "admin" {
  name         = "admin"
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "Administrators with full access"
  precedence   = 1
}

resource "aws_cognito_user_group" "ops" {
  name         = "ops"
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "Operations team with access to Ops UI"
  precedence   = 2
}

resource "aws_cognito_user_group" "analyst" {
  name         = "analyst"
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "Analysts with access to Analyst UI"
  precedence   = 3
}

resource "aws_cognito_user_group" "viewer" {
  name         = "viewer"
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "Read-only access"
  precedence   = 4
}

# ============================================================================
# App Client - Analyst UI
# ============================================================================

resource "aws_cognito_user_pool_client" "analyst_ui" {
  name         = "${var.project_name}-analyst-ui-${var.environment}"
  user_pool_id = aws_cognito_user_pool.main.id
  
  # Token configuration
  access_token_validity  = 1  # hours
  id_token_validity      = 1  # hours
  refresh_token_validity = 30 # days
  
  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }
  
  # OAuth configuration
  generate_secret                      = true
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["email", "openid", "profile"]
  
  callback_urls = var.analyst_ui_callback_urls
  logout_urls   = var.analyst_ui_logout_urls
  
  supported_identity_providers = ["COGNITO"]
  
  # Security
  prevent_user_existence_errors = "ENABLED"
  enable_token_revocation       = true
  
  # Attribute read/write permissions
  read_attributes = [
    "email",
    "email_verified",
    "name",
    "custom:tenant_id",
    "custom:organization",
  ]
  
  write_attributes = [
    "email",
    "name",
    "custom:tenant_id",
    "custom:organization",
  ]
}

# ============================================================================
# App Client - Ops UI
# ============================================================================

resource "aws_cognito_user_pool_client" "ops_ui" {
  name         = "${var.project_name}-ops-ui-${var.environment}"
  user_pool_id = aws_cognito_user_pool.main.id
  
  # Token configuration
  access_token_validity  = 1   # hours
  id_token_validity      = 1   # hours
  refresh_token_validity = 7   # days (shorter for ops access)
  
  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }
  
  # OAuth configuration
  generate_secret                      = true
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["email", "openid", "profile"]
  
  callback_urls = var.ops_ui_callback_urls
  logout_urls   = var.ops_ui_logout_urls
  
  supported_identity_providers = ["COGNITO"]
  
  # Security
  prevent_user_existence_errors = "ENABLED"
  enable_token_revocation       = true
  
  # Attribute read/write permissions
  read_attributes = [
    "email",
    "email_verified",
    "name",
    "custom:tenant_id",
    "custom:organization",
  ]
  
  write_attributes = [
    "email",
    "name",
  ]
}

# ============================================================================
# App Client - API Gateway (Machine-to-Machine)
# ============================================================================

resource "aws_cognito_user_pool_client" "api_gateway" {
  name         = "${var.project_name}-api-gateway-${var.environment}"
  user_pool_id = aws_cognito_user_pool.main.id
  
  # No secret for API token validation
  generate_secret = false
  
  # Token configuration
  access_token_validity  = 1  # hours
  id_token_validity      = 1  # hours
  refresh_token_validity = 30 # days
  
  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }
  
  # Explicit auth flows for API
  explicit_auth_flows = [
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_SRP_AUTH",
  ]
  
  # Security
  prevent_user_existence_errors = "ENABLED"
  enable_token_revocation       = true
  
  # Read all attributes for API
  read_attributes = [
    "email",
    "email_verified",
    "name",
    "custom:tenant_id",
    "custom:organization",
  ]
}

# ============================================================================
# Resource Server (for API scopes)
# ============================================================================

resource "aws_cognito_resource_server" "api" {
  identifier   = "${var.project_name}-api"
  name         = "VESPER API"
  user_pool_id = aws_cognito_user_pool.main.id
  
  scope {
    scope_name        = "read"
    scope_description = "Read access to API"
  }
  
  scope {
    scope_name        = "write"
    scope_description = "Write access to API"
  }
  
  scope {
    scope_name        = "admin"
    scope_description = "Admin access to API"
  }
}

# ============================================================================
# Outputs
# ============================================================================

output "user_pool_id" {
  description = "Cognito User Pool ID"
  value       = aws_cognito_user_pool.main.id
}

output "user_pool_arn" {
  description = "Cognito User Pool ARN"
  value       = aws_cognito_user_pool.main.arn
}

output "user_pool_endpoint" {
  description = "Cognito User Pool endpoint"
  value       = aws_cognito_user_pool.main.endpoint
}

output "user_pool_domain" {
  description = "Cognito User Pool domain"
  value       = aws_cognito_user_pool_domain.main.domain
}

output "analyst_ui_client_id" {
  description = "Analyst UI App Client ID"
  value       = aws_cognito_user_pool_client.analyst_ui.id
}

output "analyst_ui_client_secret" {
  description = "Analyst UI App Client Secret"
  value       = aws_cognito_user_pool_client.analyst_ui.client_secret
  sensitive   = true
}

output "ops_ui_client_id" {
  description = "Ops UI App Client ID"
  value       = aws_cognito_user_pool_client.ops_ui.id
}

output "ops_ui_client_secret" {
  description = "Ops UI App Client Secret"
  value       = aws_cognito_user_pool_client.ops_ui.client_secret
  sensitive   = true
}

output "api_gateway_client_id" {
  description = "API Gateway App Client ID"
  value       = aws_cognito_user_pool_client.api_gateway.id
}

output "issuer_url" {
  description = "OIDC Issuer URL for JWT validation"
  value       = "https://cognito-idp.${data.aws_region.current.name}.amazonaws.com/${aws_cognito_user_pool.main.id}"
}

output "jwks_uri" {
  description = "JWKS URI for JWT validation"
  value       = "https://cognito-idp.${data.aws_region.current.name}.amazonaws.com/${aws_cognito_user_pool.main.id}/.well-known/jwks.json"
}

data "aws_region" "current" {}
