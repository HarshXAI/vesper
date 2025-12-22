# Security Documentation

This document covers the security architecture and best practices for Vesper.

## Overview

Vesper implements defense-in-depth security across all layers:

```
┌─────────────────────────────────────────────────────────────┐
│                        CloudFront                           │
│                    (DDoS Protection)                        │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                    AWS WAF v2                               │
│        (OWASP Rules, Rate Limiting, Bot Protection)        │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│              Application Load Balancer                       │
│                   (TLS Termination)                         │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                   API Gateway                               │
│           (JWT Validation, Rate Limiting)                   │
└─────────────────────────────────────────────────────────────┘
```

## Authentication

### AWS Cognito

Vesper uses AWS Cognito for identity management:

| Component     | Purpose                           |
| ------------- | --------------------------------- |
| User Pool     | User directory and authentication |
| App Clients   | OAuth2/OIDC for web apps          |
| Custom Claims | Tenant ID for multi-tenancy       |

### User Pool Configuration

```hcl
# infrastructure/terraform/modules/auth/cognito.tf

resource "aws_cognito_user_pool" "vesper" {
  name = "vesper-${var.environment}"

  password_policy {
    minimum_length    = 12
    require_lowercase = true
    require_numbers   = true
    require_symbols   = true
    require_uppercase = true
  }

  mfa_configuration = "ON"

  software_token_mfa_configuration {
    enabled = true
  }
}
```

### JWT Validation

The API Gateway validates JWTs on every request:

```python
# apps/api-gateway/app/middleware/auth.py

class JWTValidator:
    """Validates JWTs using JWKS from Cognito."""

    async def validate_token(self, token: str) -> dict:
        # Fetch and cache JWKS
        jwks = await self._get_jwks()

        # Decode and verify token
        header = jwt.get_unverified_header(token)
        key = self._find_key(jwks, header["kid"])

        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=self.issuer,
            audience=self.client_id,
        )

        # Verify expiration
        if payload["exp"] < time.time():
            raise TokenExpiredError()

        return payload
```

### Token Claims

Expected JWT claims:

```json
{
  "sub": "user-uuid",
  "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_xxx",
  "aud": "client-id",
  "exp": 1700000000,
  "iat": 1699996400,
  "email": "user@example.com",
  "cognito:groups": ["analysts", "admins"],
  "custom:tenant_id": "tenant-123"
}
```

## Authorization

### Role-Based Access Control (RBAC)

| Role        | Permissions                                |
| ----------- | ------------------------------------------ |
| `analysts`  | Chat, view citations, view traces          |
| `operators` | All analyst + trigger DAGs, view evals     |
| `admins`    | All operator + manage users, modify config |

### Tenant Isolation

Every request includes tenant context:

```python
# Tenant ID extraction from JWT
tenant_id = claims.get("custom:tenant_id", "default")

# All queries are scoped to tenant
results = await vector_store.query(
    query=query,
    filter={"tenant_id": tenant_id},
    top_k=10,
)
```

## Web Application Firewall (WAF)

### Managed Rules

| Rule Set                             | Description              |
| ------------------------------------ | ------------------------ |
| AWSManagedRulesCommonRuleSet         | OWASP Top 10 protections |
| AWSManagedRulesKnownBadInputsRuleSet | Known attack patterns    |
| AWSManagedRulesSQLiRuleSet           | SQL injection protection |
| AWSManagedRulesLinuxRuleSet          | Linux-specific attacks   |
| AWSManagedRulesBotControlRuleSet     | Bot detection            |

### Rate Limiting

```hcl
# infrastructure/terraform/modules/edge/waf.tf

rule {
  name     = "RateLimitRule"
  priority = 1

  action {
    block {}
  }

  statement {
    rate_based_statement {
      limit              = 2000  # requests per 5 minutes
      aggregate_key_type = "IP"
    }
  }
}
```

### Geo-Blocking (Optional)

```hcl
variable "allowed_countries" {
  default = ["US", "CA", "GB", "DE"]  # Restrict to specific countries
}
```

## TLS/HTTPS

### Certificate Configuration

```hcl
# infrastructure/terraform/modules/edge/main.tf

resource "aws_acm_certificate" "main" {
  domain_name       = var.domain_name
  validation_method = "DNS"

  subject_alternative_names = [
    "*.${var.domain_name}",
    "api.${var.domain_name}",
    "ops.${var.domain_name}"
  ]
}
```

### SSL Policy

Using TLS 1.3 with strong ciphers:

```hcl
resource "aws_lb_listener" "https" {
  ssl_policy = "ELBSecurityPolicy-TLS13-1-2-2021-06"
}
```

### HTTP to HTTPS Redirect

All HTTP traffic is redirected to HTTPS:

```hcl
resource "aws_lb_listener" "http_redirect" {
  port     = 80
  protocol = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}
```

## Secrets Management

### AWS SSM Parameter Store

All secrets are stored encrypted in SSM:

```hcl
# infrastructure/terraform/modules/ssm/main.tf

resource "aws_ssm_parameter" "openai_api_key" {
  name   = "/vesper/${var.environment}/openai-api-key"
  type   = "SecureString"
  value  = var.openai_api_key
  key_id = aws_kms_key.ssm.arn
}
```

### KMS Encryption

Dedicated KMS key for secrets:

```hcl
resource "aws_kms_key" "ssm" {
  description             = "KMS key for Vesper SSM parameters"
  deletion_window_in_days = 7
  enable_key_rotation     = true
}
```

### Environment Variable Injection

ECS tasks retrieve secrets at runtime:

```hcl
secrets = [
  {
    name      = "OPENAI_API_KEY"
    valueFrom = aws_ssm_parameter.openai_api_key.arn
  },
  {
    name      = "DATABASE_URL"
    valueFrom = aws_ssm_parameter.database_url.arn
  }
]
```

## Network Security

### VPC Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                          VPC                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │               Public Subnets                         │   │
│  │   ┌─────────┐                    ┌─────────┐        │   │
│  │   │   ALB   │                    │   NAT   │        │   │
│  │   └────┬────┘                    └────┬────┘        │   │
│  └────────┼─────────────────────────────┼──────────────┘   │
│           │                              │                  │
│  ┌────────▼─────────────────────────────▼──────────────┐   │
│  │               Private Subnets                        │   │
│  │   ┌─────────┐    ┌─────────┐    ┌─────────┐        │   │
│  │   │   ECS   │    │   RDS   │    │  Redis  │        │   │
│  │   └─────────┘    └─────────┘    └─────────┘        │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Security Groups

| Component | Inbound            | Outbound         |
| --------- | ------------------ | ---------------- |
| ALB       | 443 from 0.0.0.0/0 | All to VPC       |
| ECS Tasks | 8000 from ALB SG   | 443 to 0.0.0.0/0 |
| RDS       | 5432 from ECS SG   | None             |
| Redis     | 6379 from ECS SG   | None             |

### Private Endpoints

VPC endpoints for AWS services:

```hcl
resource "aws_vpc_endpoint" "ssm" {
  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.${var.region}.ssm"
  vpc_endpoint_type = "Interface"
}
```

## Input Validation

### Request Validation

All inputs are validated with Pydantic:

```python
class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4096)
    tenant_id: str = Field(..., pattern=r"^[a-zA-Z0-9-]+$")
    stream: bool = True

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        # Sanitize input
        v = v.strip()
        if not v:
            raise ValueError("Query cannot be empty")
        return v
```

### Guardrails

Content moderation for inputs and outputs:

```python
class GuardrailsMiddleware:
    async def check_input(self, query: str) -> bool:
        # Check for PII
        if self._contains_pii(query):
            raise ContentBlockedError("PII detected in input")

        # Check for prompt injection
        if self._is_prompt_injection(query):
            raise ContentBlockedError("Potential prompt injection")

        return True
```

## Audit Logging

### Request Logging

All requests are logged with security context:

```python
logger.info(
    "Request processed",
    extra={
        "request_id": request_id,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "path": request.url.path,
        "method": request.method,
        "status_code": response.status_code,
        "latency_ms": latency_ms,
        "client_ip": client_ip,
    }
)
```

### Security Events

Security events are logged separately:

```python
security_logger.warning(
    "Authentication failure",
    extra={
        "event_type": "auth_failure",
        "reason": "invalid_token",
        "client_ip": client_ip,
        "user_agent": user_agent,
    }
)
```

### CloudWatch Logs

Logs are shipped to CloudWatch with retention:

```hcl
resource "aws_cloudwatch_log_group" "api" {
  name              = "/vesper/api-gateway"
  retention_in_days = 90
}
```

## Vulnerability Management

### Dependency Scanning

```yaml
# .github/workflows/ci.yml
- name: Run Snyk security scan
  uses: snyk/actions/python@master
  with:
    args: --severity-threshold=high
```

### Container Scanning

```yaml
- name: Scan Docker image
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: ${{ env.IMAGE }}
    severity: "CRITICAL,HIGH"
    exit-code: "1"
```

### SAST (Static Analysis)

```yaml
- name: Run Bandit security linter
  run: |
    pip install bandit
    bandit -r apps/ -ll -ii
```

## Security Checklist

### Pre-Production

- [ ] All secrets in SSM Parameter Store
- [ ] MFA enabled for Cognito users
- [ ] WAF rules in blocking mode
- [ ] TLS 1.3 enforced
- [ ] Security groups least-privilege
- [ ] VPC flow logs enabled
- [ ] CloudTrail enabled
- [ ] Dependency vulnerabilities addressed

### Ongoing

- [ ] Regular secret rotation
- [ ] Security patches applied
- [ ] Penetration testing (annual)
- [ ] Access reviews (quarterly)
- [ ] Incident response drills
- [ ] Log review automation

## Incident Response

### Security Contacts

| Role          | Contact                     |
| ------------- | --------------------------- |
| Security Lead | security@vesper.example.com |
| On-Call       | PagerDuty                   |
| AWS TAM       | Account team                |

### Response Procedures

1. **Detection**: Monitor for security events
2. **Containment**: Isolate affected resources
3. **Analysis**: Determine scope and impact
4. **Remediation**: Fix vulnerability
5. **Recovery**: Restore services
6. **Lessons Learned**: Update procedures

### Emergency Actions

```bash
# Block an IP immediately
aws wafv2 update-ip-set \
  --name vesper-blocked-ips \
  --scope REGIONAL \
  --addresses "1.2.3.4/32"

# Rotate compromised secret
aws ssm put-parameter \
  --name "/vesper/prod/openai-api-key" \
  --value "new-key" \
  --overwrite
```
