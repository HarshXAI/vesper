# Deployment Pipeline Documentation

This document describes the CI/CD pipeline for the Vesper platform.

## Overview

Vesper uses GitHub Actions for continuous integration and deployment with quality gates.

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│   CI    │───▶│ Staging │───▶│  Load   │───▶│  Prod   │
│  Tests  │    │ Deploy  │    │  Test   │    │ Deploy  │
└─────────┘    └─────────┘    └─────────┘    └─────────┘
     │              │              │              │
     ▼              ▼              ▼              ▼
  Lint/Type     Eval Run      SLO Check      Canary
  Unit Test     Smoke Test    p95 < 2.5s     Rollback
```

## Workflows

### 1. Continuous Integration (`.github/workflows/ci.yml`)

Triggered on: Pull requests to `main`

**Jobs:**

| Job                  | Description             | Duration |
| -------------------- | ----------------------- | -------- |
| `lint`               | Ruff linting for Python | ~1 min   |
| `typecheck`          | Mypy type checking      | ~2 min   |
| `test`               | Pytest unit tests       | ~5 min   |
| `frontend-lint`      | ESLint for Next.js apps | ~2 min   |
| `frontend-typecheck` | TypeScript compilation  | ~2 min   |
| `frontend-test`      | Playwright E2E tests    | ~5 min   |
| `build`              | Docker image build      | ~3 min   |

**Quality Gates:**

- All linting must pass
- Type checking must pass
- Unit test coverage > 80%
- E2E tests must pass

### 2. Staging Deployment (`.github/workflows/deploy-staging.yml`)

Triggered on: Push to `main` branch

**Jobs:**

| Job              | Description                         |
| ---------------- | ----------------------------------- |
| `build`          | Build and push Docker images to ECR |
| `deploy-staging` | Deploy to ECS staging cluster       |
| `smoke-test`     | Run smoke tests against staging     |
| `eval-run`       | Trigger evaluation pipeline         |
| `load-test`      | Run load tests for SLO validation   |
| `quality-gate`   | Validate SLO metrics                |
| `notify`         | Slack notification                  |

**Quality Gates:**

```yaml
quality_gates:
  p95_latency_ms: 2500 # p95 < 2.5 seconds
  error_rate_percent: 1.0 # Errors < 1%
  faithfulness_score: 0.9 # Eval score >= 0.9
```

### 3. Production Deployment (`.github/workflows/deploy-prod.yml`)

Triggered on: Manual workflow dispatch (requires approval)

**Jobs:**

| Job                      | Description                |
| ------------------------ | -------------------------- |
| `approval`               | Environment approval gate  |
| `pre-deploy-backup`      | Database snapshot          |
| `deploy-canary`          | 10% traffic to new version |
| `canary-validation`      | Monitor canary metrics     |
| `deploy-full`            | Full production rollout    |
| `post-deploy-validation` | Smoke tests + monitoring   |
| `notify`                 | Slack notification         |

**Rollback:**

Automatic rollback if:

- Error rate > 1% in canary
- p99 latency > 5s
- Health check failures

## Pipeline Configuration

### Secrets Required

| Secret                  | Description                    |
| ----------------------- | ------------------------------ |
| `AWS_ACCESS_KEY_ID`     | AWS credentials for deployment |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials                |
| `ECR_REGISTRY`          | ECR registry URL               |
| `ECS_CLUSTER_STAGING`   | Staging ECS cluster name       |
| `ECS_CLUSTER_PROD`      | Production ECS cluster name    |
| `SLACK_WEBHOOK_URL`     | Slack notifications            |
| `GRAFANA_API_KEY`       | Grafana API for annotations    |

### Environment Variables

```yaml
# .github/workflows/deploy-staging.yml
env:
  AWS_REGION: us-east-1
  ECR_REPOSITORY: vesper/api-gateway
  ECS_SERVICE: vesper-api-gateway
  CONTAINER_NAME: api-gateway
```

## Quality Gates

### SLO Targets

| Metric           | Target  | Source        | Gate Stage           |
| ---------------- | ------- | ------------- | -------------------- |
| p95 Latency      | < 2.5s  | Prometheus    | Staging, Prod Canary |
| Error Rate (5xx) | < 1%    | Prometheus    | Staging, Prod Canary |
| Faithfulness     | >= 0.90 | MLflow        | Staging              |
| Hallucination    | <= 0.02 | MLflow        | Staging              |
| Availability     | > 99.9% | Health checks | Prod Canary          |

### PromQL Quality Gates

The staging pipeline runs these PromQL queries:

```promql
# p95 Latency Gate (must be < 2.5s)
histogram_quantile(0.95,
  sum(rate(http_request_duration_seconds_bucket{service="api-gateway"}[5m])) by (le)
)

# 5xx Error Rate Gate (must be < 1%)
sum(rate(http_requests_total{service="api-gateway",status=~"5.."}[5m]))
/ sum(rate(http_requests_total{service="api-gateway"}[5m]))
```

### MLflow Evaluation Gates

After eval pipeline runs:

```bash
# Check faithfulness >= 0.90
FAITHFULNESS=$(curl -s "$MLFLOW_TRACKING_URI/api/2.0/mlflow/runs/search" \
  --data '{"experiment_ids":["'$EXPERIMENT_ID'"],"max_results":1}' \
  | jq -r '.runs[0].data.metrics[] | select(.key=="faithfulness").value')

# Check hallucination_rate <= 0.02
HALLUCINATION=$(curl -s "$MLFLOW_TRACKING_URI/api/2.0/mlflow/runs/search" \
  --data '{"experiment_ids":["'$EXPERIMENT_ID'"],"max_results":1}' \
  | jq -r '.runs[0].data.metrics[] | select(.key=="hallucination_rate").value')
```

### Validation Script

```bash
# scripts/validate_slos.sh
#!/bin/bash

# Query Prometheus for metrics
P95=$(curl -s "$PROMETHEUS_URL/api/v1/query?query=histogram_quantile(0.95,rate(http_request_duration_seconds_bucket[5m]))")
ERROR_RATE=$(curl -s "$PROMETHEUS_URL/api/v1/query?query=rate(http_requests_total{status=~'5..'}[5m])")

# Check thresholds
if (( $(echo "$P95 > 2.5" | bc -l) )); then
  echo "❌ p95 latency exceeds 2.5s: $P95"
  exit 1
fi

if (( $(echo "$ERROR_RATE > 0.01" | bc -l) )); then
  echo "❌ Error rate exceeds 1%: $ERROR_RATE"
  exit 1
fi

echo "✅ All SLOs passing"
```

## Load Testing

### Pre-deployment Load Test

```bash
# Run load test before deployment
python scripts/load_test_concurrent.py \
  --users 50 \
  --duration 120 \
  --url https://staging.vesper.example.com
```

### Metrics Collected

- Requests per second
- Latency percentiles (p50, p90, p95, p99)
- Error rate by status code
- Success rate

### SLO Validation

The load test exits with code 1 if SLOs fail:

```python
def validate_slos(stats):
    slos = {
        "p95_latency_ms": stats.p95 < 2500,
        "error_rate_percent": stats.error_rate < 1.0,
        "success_rate_percent": stats.success_rate >= 99.0,
    }
    return all(slos.values())
```

## Deployment Strategies

### Staging: Rolling Update

```yaml
# ECS Service configuration
deployment_configuration:
  maximum_percent: 200
  minimum_healthy_percent: 100
  deployment_circuit_breaker:
    enable: true
    rollback: true
```

### Production: Canary Deployment

1. Deploy new version to 10% of tasks
2. Monitor for 5 minutes
3. If healthy, proceed to full rollout
4. If errors, automatic rollback

## Blue/Green Canary Deployment

### Overview

Production deployments use weighted target groups for progressive traffic shifting:

```
┌─────────────┐     ┌─────────────┐
│   Blue TG   │────▶│   Green TG  │
│ (Primary)   │     │  (Canary)   │
│   100%      │     │    0%       │
└─────────────┘     └─────────────┘
       │                   │
       ▼                   ▼
┌─────────────────────────────────┐
│         ALB Listener            │
│   Weighted Forwarding Rules     │
└─────────────────────────────────┘
```

### Canary Progression Phases

| Phase | Blue Weight | Green Weight | Duration | Validation      |
| ----- | ----------- | ------------ | -------- | --------------- |
| 1     | 90%         | 10%          | 60s      | Health + PromQL |
| 2     | 75%         | 25%          | 60s      | Health + PromQL |
| 3     | 50%         | 50%          | 60s      | Health + PromQL |
| 4     | 0%          | 100%         | -        | Complete        |

### Validation Between Phases

Each phase runs PromQL checks:

```bash
# p95 latency check
histogram_quantile(0.95,
  sum(rate(http_request_duration_seconds_bucket{deployment="green"}[2m])) by (le)
) < 2.5

# Error rate check
rate(http_requests_total{status=~"5..",deployment="green"}[2m])
/ rate(http_requests_total{deployment="green"}[2m]) < 0.01
```

### Automatic Rollback Triggers

Rollback is triggered if any of these conditions are met:

- Health check failures (2+ consecutive)
- p95 latency > 2.5s for green target group
- 5xx error rate > 1%
- MLflow evaluation metrics breach (hallucination > 2%)

### Traffic Shift Commands

```bash
# Shift traffic to canary (10%)
aws elbv2 modify-listener \
  --listener-arn $LISTENER_ARN \
  --default-actions '[{
    "Type": "forward",
    "ForwardConfig": {
      "TargetGroups": [
        {"TargetGroupArn": "'$BLUE_TG_ARN'", "Weight": 90},
        {"TargetGroupArn": "'$GREEN_TG_ARN'", "Weight": 10}
      ],
      "TargetGroupStickinessConfig": {"Enabled": true, "DurationSeconds": 300}
    }
  }]'

# Full rollout (100% green)
aws elbv2 modify-listener \
  --listener-arn $LISTENER_ARN \
  --default-actions '[{
    "Type": "forward",
    "ForwardConfig": {
      "TargetGroups": [
        {"TargetGroupArn": "'$BLUE_TG_ARN'", "Weight": 0},
        {"TargetGroupArn": "'$GREEN_TG_ARN'", "Weight": 100}
      ]
    }
  }]'
```

## Rollback Procedures

### Automatic Rollback (CI/CD)

The deployment pipeline automatically rolls back on health breach:

```yaml
# In deploy-prod.yml
- name: Rollback on failure
  if: failure()
  run: |
    aws elbv2 modify-listener \
      --listener-arn ${{ env.LISTENER_ARN }} \
      --default-actions '[{
        "Type": "forward",
        "ForwardConfig": {
          "TargetGroups": [
            {"TargetGroupArn": "${{ env.BLUE_TG_ARN }}", "Weight": 100},
            {"TargetGroupArn": "${{ env.GREEN_TG_ARN }}", "Weight": 0}
          ]
        }
      }]'
```

### Manual Rollback Commands

**Immediate Traffic Rollback (ALB):**

```bash
# Rollback all traffic to blue (previous stable version)
aws elbv2 modify-listener \
  --listener-arn $LISTENER_ARN \
  --default-actions '[{
    "Type": "forward",
    "ForwardConfig": {
      "TargetGroups": [
        {"TargetGroupArn": "'$BLUE_TG_ARN'", "Weight": 100},
        {"TargetGroupArn": "'$GREEN_TG_ARN'", "Weight": 0}
      ]
    }
  }]'
```

**ECS Service Rollback (Task Definition):**

```bash
# List previous task definitions
aws ecs list-task-definitions \
  --family-prefix vesper-api-gateway \
  --sort DESC \
  --max-items 5

# Rollback to specific task definition
aws ecs update-service \
  --cluster vesper-prod \
  --service vesper-api-gateway \
  --task-definition vesper-api-gateway:PREVIOUS_VERSION \
  --force-new-deployment
```

**Terraform Rollback (Blue/Green Weights):**

```bash
# Rollback via Terraform
cd infrastructure/terraform/environments/prod

# Set blue weight to 100, green to 0
terraform apply \
  -var="blue_weight=100" \
  -var="green_weight=0" \
  -target=module.compute.aws_lb_listener.http
```

### Rollback Verification

After rollback, verify:

```bash
# Check target group health
aws elbv2 describe-target-health \
  --target-group-arn $BLUE_TG_ARN

# Check ECS service status
aws ecs describe-services \
  --cluster vesper-prod \
  --services vesper-api-gateway \
  --query 'services[0].deployments'

# Verify traffic distribution
aws elbv2 describe-listeners \
  --listener-arns $LISTENER_ARN \
  --query 'Listeners[0].DefaultActions[0].ForwardConfig.TargetGroups'
```

### Grafana Annotations

Deployments are annotated in Grafana:

```bash
curl -X POST "$GRAFANA_URL/api/annotations" \
  -H "Authorization: Bearer $GRAFANA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "dashboardUID": "vesper-main",
    "time": '$(date +%s000)',
    "tags": ["deployment", "staging"],
    "text": "Deployed version '"$VERSION"'"
  }'
```

### Slack Notifications

```yaml
- name: Notify Slack
  uses: slackapi/slack-github-action@v1
  with:
    payload: |
      {
        "text": "${{ job.status == 'success' && '✅' || '❌' }} Deployment to ${{ inputs.environment }}",
        "blocks": [
          {
            "type": "section",
            "text": {
              "type": "mrkdwn",
              "text": "*Deployment ${{ job.status }}*\nVersion: `${{ github.sha }}`\nEnvironment: `${{ inputs.environment }}`"
            }
          }
        ]
      }
```

## Rollback Procedures

### Automatic Rollback

ECS Circuit Breaker handles automatic rollback:

- Deployment fails if tasks don't become healthy
- Previous task definition is restored

### Manual Rollback

```bash
# Rollback to previous task definition
aws ecs update-service \
  --cluster vesper-prod \
  --service vesper-api-gateway \
  --task-definition vesper-api-gateway:PREVIOUS_VERSION \
  --force-new-deployment
```

## Troubleshooting

### Pipeline Failures

1. **Lint Failures**

   - Run `ruff check .` locally
   - Fix issues or add to ignore list

2. **Test Failures**

   - Check test output in workflow logs
   - Run tests locally: `pytest -v`

3. **Deployment Failures**
   - Check ECS service events
   - Review CloudWatch logs
   - Check security group rules

### Health Check Failures

1. Verify container is starting correctly
2. Check application logs in CloudWatch
3. Verify environment variables are set
4. Check database connectivity

## Security

### Secrets Management

- Secrets stored in GitHub Secrets
- Never logged or printed
- Rotated regularly

### Image Scanning

```yaml
- name: Scan Docker image
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: ${{ env.ECR_REGISTRY }}/${{ env.ECR_REPOSITORY }}:${{ github.sha }}
    format: "sarif"
    severity: "CRITICAL,HIGH"
```

### OIDC for AWS

Prefer OIDC over long-lived credentials:

```yaml
- name: Configure AWS credentials
  uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: arn:aws:iam::123456789:role/github-actions-vesper
    aws-region: us-east-1
```
