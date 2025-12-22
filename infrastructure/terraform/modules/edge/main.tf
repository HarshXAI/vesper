# =============================================================================
# Edge Module - TLS/HTTPS Configuration for ALB
# =============================================================================
# This module configures HTTPS termination with ACM certificates and 
# secure listeners for the Application Load Balancer
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

variable "domain_name" {
  description = "Primary domain name for the certificate"
  type        = string
}

variable "hosted_zone_id" {
  description = "Route53 hosted zone ID for DNS validation"
  type        = string
}

variable "alb_arn" {
  description = "ARN of the Application Load Balancer"
  type        = string
}

variable "alb_security_group_id" {
  description = "Security group ID of the ALB"
  type        = string
}

variable "target_group_arn" {
  description = "ARN of the target group for HTTPS listener"
  type        = string
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
  name_prefix = "vesper-${var.environment}"
  
  default_tags = {
    Environment = var.environment
    Project     = "vesper"
    ManagedBy   = "terraform"
    Module      = "edge"
  }
  
  all_tags = merge(local.default_tags, var.tags)
}

# -----------------------------------------------------------------------------
# ACM Certificate
# -----------------------------------------------------------------------------

resource "aws_acm_certificate" "main" {
  domain_name       = var.domain_name
  validation_method = "DNS"
  
  subject_alternative_names = [
    "*.${var.domain_name}",
    "api.${var.domain_name}",
    "ops.${var.domain_name}"
  ]
  
  lifecycle {
    create_before_destroy = true
  }
  
  tags = merge(local.all_tags, {
    Name = "${local.name_prefix}-certificate"
  })
}

# -----------------------------------------------------------------------------
# DNS Validation Records
# -----------------------------------------------------------------------------

resource "aws_route53_record" "cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.main.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }
  
  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = var.hosted_zone_id
}

resource "aws_acm_certificate_validation" "main" {
  certificate_arn         = aws_acm_certificate.main.arn
  validation_record_fqdns = [for record in aws_route53_record.cert_validation : record.fqdn]
  
  timeouts {
    create = "30m"
  }
}

# -----------------------------------------------------------------------------
# HTTPS Listener
# -----------------------------------------------------------------------------

resource "aws_lb_listener" "https" {
  load_balancer_arn = var.alb_arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate_validation.main.certificate_arn
  
  default_action {
    type             = "forward"
    target_group_arn = var.target_group_arn
  }
  
  tags = merge(local.all_tags, {
    Name = "${local.name_prefix}-https-listener"
  })
}

# -----------------------------------------------------------------------------
# HTTP to HTTPS Redirect
# -----------------------------------------------------------------------------

resource "aws_lb_listener" "http_redirect" {
  load_balancer_arn = var.alb_arn
  port              = 80
  protocol          = "HTTP"
  
  default_action {
    type = "redirect"
    
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
  
  tags = merge(local.all_tags, {
    Name = "${local.name_prefix}-http-redirect"
  })
}

# -----------------------------------------------------------------------------
# Security Group Rule - Allow HTTPS
# -----------------------------------------------------------------------------

resource "aws_security_group_rule" "alb_https_ingress" {
  type              = "ingress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = var.alb_security_group_id
  description       = "Allow HTTPS traffic"
}

# -----------------------------------------------------------------------------
# Route53 Records for Services
# -----------------------------------------------------------------------------

data "aws_lb" "main" {
  arn = var.alb_arn
}

resource "aws_route53_record" "api" {
  zone_id = var.hosted_zone_id
  name    = "api.${var.domain_name}"
  type    = "A"
  
  alias {
    name                   = data.aws_lb.main.dns_name
    zone_id                = data.aws_lb.main.zone_id
    evaluate_target_health = true
  }
}

resource "aws_route53_record" "ops" {
  zone_id = var.hosted_zone_id
  name    = "ops.${var.domain_name}"
  type    = "A"
  
  alias {
    name                   = data.aws_lb.main.dns_name
    zone_id                = data.aws_lb.main.zone_id
    evaluate_target_health = true
  }
}

# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------

output "certificate_arn" {
  description = "ARN of the ACM certificate"
  value       = aws_acm_certificate.main.arn
}

output "https_listener_arn" {
  description = "ARN of the HTTPS listener"
  value       = aws_lb_listener.https.arn
}

output "domain_name" {
  description = "Primary domain name"
  value       = var.domain_name
}

output "api_endpoint" {
  description = "API endpoint URL"
  value       = "https://api.${var.domain_name}"
}

output "ops_endpoint" {
  description = "Ops dashboard endpoint URL"
  value       = "https://ops.${var.domain_name}"
}
