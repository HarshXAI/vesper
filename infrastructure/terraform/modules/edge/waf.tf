# =============================================================================
# WAF (Web Application Firewall) Configuration
# =============================================================================
# AWS WAFv2 rules for protecting the API Gateway and web applications
# Implements OWASP Top 10 protections and rate limiting
# =============================================================================

# -----------------------------------------------------------------------------
# WAF Variables
# -----------------------------------------------------------------------------

variable "enable_waf" {
  description = "Enable WAF protection"
  type        = bool
  default     = true
}

variable "waf_rate_limit" {
  description = "Rate limit per 5 minutes per IP"
  type        = number
  default     = 100  # Stricter limit: 100 requests per 5 minutes per IP
}

variable "waf_block_mode" {
  description = "Whether to block (true) or count (false) for managed rules"
  type        = bool
  default     = true
}

variable "allowed_countries" {
  description = "List of allowed country codes (empty = allow all)"
  type        = list(string)
  default     = []
}

variable "ip_rate_limit_per_tenant" {
  description = "Rate limit per tenant per 5 minutes"
  type        = number
  default     = 5000
}

# -----------------------------------------------------------------------------
# WAF Web ACL
# -----------------------------------------------------------------------------

resource "aws_wafv2_web_acl" "main" {
  count = var.enable_waf ? 1 : 0
  
  name        = "${local.name_prefix}-waf"
  description = "WAF rules for Vesper API"
  scope       = "REGIONAL"
  
  default_action {
    allow {}
  }
  
  # -------------------------------------------------------------------------
  # Rate Limiting Rule
  # -------------------------------------------------------------------------
  rule {
    name     = "RateLimitRule"
    priority = 1
    
    action {
      block {}
    }
    
    statement {
      rate_based_statement {
        limit              = var.waf_rate_limit
        aggregate_key_type = "IP"
      }
    }
    
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name_prefix}-rate-limit"
      sampled_requests_enabled   = true
    }
  }
  
  # -------------------------------------------------------------------------
  # AWS Managed Rules - Common Rule Set
  # -------------------------------------------------------------------------
  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 10
    
    override_action {
      dynamic "none" {
        for_each = var.waf_block_mode ? [1] : []
        content {}
      }
      dynamic "count" {
        for_each = var.waf_block_mode ? [] : [1]
        content {}
      }
    }
    
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
        
        # Exclude rules that may conflict with API behavior
        rule_action_override {
          name = "SizeRestrictions_BODY"
          action_to_use {
            count {}
          }
        }
        
        rule_action_override {
          name = "NoUserAgent_HEADER"
          action_to_use {
            count {}
          }
        }
      }
    }
    
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name_prefix}-common-rules"
      sampled_requests_enabled   = true
    }
  }
  
  # -------------------------------------------------------------------------
  # AWS Managed Rules - Known Bad Inputs
  # -------------------------------------------------------------------------
  rule {
    name     = "AWSManagedRulesKnownBadInputsRuleSet"
    priority = 20
    
    override_action {
      dynamic "none" {
        for_each = var.waf_block_mode ? [1] : []
        content {}
      }
      dynamic "count" {
        for_each = var.waf_block_mode ? [] : [1]
        content {}
      }
    }
    
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
        vendor_name = "AWS"
      }
    }
    
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name_prefix}-bad-inputs"
      sampled_requests_enabled   = true
    }
  }
  
  # -------------------------------------------------------------------------
  # AWS Managed Rules - SQL Injection
  # -------------------------------------------------------------------------
  rule {
    name     = "AWSManagedRulesSQLiRuleSet"
    priority = 30
    
    override_action {
      dynamic "none" {
        for_each = var.waf_block_mode ? [1] : []
        content {}
      }
      dynamic "count" {
        for_each = var.waf_block_mode ? [] : [1]
        content {}
      }
    }
    
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesSQLiRuleSet"
        vendor_name = "AWS"
      }
    }
    
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name_prefix}-sqli"
      sampled_requests_enabled   = true
    }
  }
  
  # -------------------------------------------------------------------------
  # AWS Managed Rules - Linux OS
  # -------------------------------------------------------------------------
  rule {
    name     = "AWSManagedRulesLinuxRuleSet"
    priority = 40
    
    override_action {
      dynamic "none" {
        for_each = var.waf_block_mode ? [1] : []
        content {}
      }
      dynamic "count" {
        for_each = var.waf_block_mode ? [] : [1]
        content {}
      }
    }
    
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesLinuxRuleSet"
        vendor_name = "AWS"
      }
    }
    
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name_prefix}-linux"
      sampled_requests_enabled   = true
    }
  }
  
  # -------------------------------------------------------------------------
  # AWS Managed Rules - Bot Control (Optional)
  # -------------------------------------------------------------------------
  rule {
    name     = "AWSManagedRulesBotControlRuleSet"
    priority = 50
    
    override_action {
      count {}
    }
    
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesBotControlRuleSet"
        vendor_name = "AWS"
        
        managed_rule_group_configs {
          aws_managed_rules_bot_control_rule_set {
            inspection_level = "COMMON"
          }
        }
      }
    }
    
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name_prefix}-bot-control"
      sampled_requests_enabled   = true
    }
  }
  
  # -------------------------------------------------------------------------
  # Geo-Restriction (if configured)
  # -------------------------------------------------------------------------
  dynamic "rule" {
    for_each = length(var.allowed_countries) > 0 ? [1] : []
    
    content {
      name     = "GeoRestriction"
      priority = 5
      
      action {
        block {}
      }
      
      statement {
        not_statement {
          statement {
            geo_match_statement {
              country_codes = var.allowed_countries
            }
          }
        }
      }
      
      visibility_config {
        cloudwatch_metrics_enabled = true
        metric_name                = "${local.name_prefix}-geo-block"
        sampled_requests_enabled   = true
      }
    }
  }
  
  # -------------------------------------------------------------------------
  # Custom Rule - Block Suspicious User Agents
  # -------------------------------------------------------------------------
  rule {
    name     = "BlockSuspiciousUserAgents"
    priority = 60
    
    action {
      block {}
    }
    
    statement {
      regex_pattern_set_reference_statement {
        arn = aws_wafv2_regex_pattern_set.suspicious_user_agents[0].arn
        
        field_to_match {
          single_header {
            name = "user-agent"
          }
        }
        
        text_transformation {
          priority = 0
          type     = "LOWERCASE"
        }
      }
    }
    
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name_prefix}-suspicious-ua"
      sampled_requests_enabled   = true
    }
  }
  
  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${local.name_prefix}-waf"
    sampled_requests_enabled   = true
  }
  
  tags = merge(local.all_tags, {
    Name = "${local.name_prefix}-waf"
  })
}

# -----------------------------------------------------------------------------
# Suspicious User Agents Pattern Set
# -----------------------------------------------------------------------------

resource "aws_wafv2_regex_pattern_set" "suspicious_user_agents" {
  count = var.enable_waf ? 1 : 0
  
  name        = "${local.name_prefix}-suspicious-ua"
  description = "Suspicious user agent patterns"
  scope       = "REGIONAL"
  
  regular_expression {
    regex_string = ".*sqlmap.*"
  }
  
  regular_expression {
    regex_string = ".*nikto.*"
  }
  
  regular_expression {
    regex_string = ".*nessus.*"
  }
  
  regular_expression {
    regex_string = ".*masscan.*"
  }
  
  regular_expression {
    regex_string = ".*zgrab.*"
  }
  
  tags = merge(local.all_tags, {
    Name = "${local.name_prefix}-suspicious-ua-patterns"
  })
}

# -----------------------------------------------------------------------------
# WAF Association with ALB
# -----------------------------------------------------------------------------

resource "aws_wafv2_web_acl_association" "main" {
  count = var.enable_waf ? 1 : 0
  
  resource_arn = var.alb_arn
  web_acl_arn  = aws_wafv2_web_acl.main[0].arn
}

# -----------------------------------------------------------------------------
# WAF Logging Configuration
# -----------------------------------------------------------------------------

resource "aws_wafv2_web_acl_logging_configuration" "main" {
  count = var.enable_waf ? 1 : 0
  
  log_destination_configs = [aws_cloudwatch_log_group.waf[0].arn]
  resource_arn            = aws_wafv2_web_acl.main[0].arn
  
  logging_filter {
    default_behavior = "DROP"
    
    filter {
      behavior = "KEEP"
      
      condition {
        action_condition {
          action = "BLOCK"
        }
      }
      
      requirement = "MEETS_ANY"
    }
    
    filter {
      behavior = "KEEP"
      
      condition {
        action_condition {
          action = "COUNT"
        }
      }
      
      requirement = "MEETS_ANY"
    }
  }
}

resource "aws_cloudwatch_log_group" "waf" {
  count = var.enable_waf ? 1 : 0
  
  # WAF log groups must start with aws-waf-logs-
  name              = "aws-waf-logs-${local.name_prefix}"
  retention_in_days = 30
  
  tags = merge(local.all_tags, {
    Name = "${local.name_prefix}-waf-logs"
  })
}

# -----------------------------------------------------------------------------
# WAF Outputs
# -----------------------------------------------------------------------------

output "waf_web_acl_arn" {
  description = "ARN of the WAF Web ACL"
  value       = var.enable_waf ? aws_wafv2_web_acl.main[0].arn : null
}

output "waf_web_acl_id" {
  description = "ID of the WAF Web ACL"
  value       = var.enable_waf ? aws_wafv2_web_acl.main[0].id : null
}

output "waf_log_group_name" {
  description = "Name of the WAF CloudWatch log group"
  value       = var.enable_waf ? aws_cloudwatch_log_group.waf[0].name : null
}
