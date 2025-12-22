# VESPER Operational Runbooks

This document contains operational runbooks for VESPER's monitoring, alerting, and incident response procedures.

---

## Table of Contents

1. [Alert Response Runbooks](#alert-response-runbooks)
   - [API Latency Alerts](#api-latency-alerts)
   - [Error Rate Alerts](#error-rate-alerts)
   - [Retrieval Quality Alerts](#retrieval-quality-alerts)
   - [Cost Budget Alerts](#cost-budget-alerts)
   - [Infrastructure Alerts](#infrastructure-alerts)
2. [Nightly Evaluation Procedures](#nightly-evaluation-procedures)
3. [Auto-Remediation Procedures](#auto-remediation-procedures)
4. [Incident Response](#incident-response)
5. [Escalation Matrix](#escalation-matrix)

---

## Alert Response Runbooks

### API Latency Alerts

#### VesperAPILatencyP95High

**Severity:** Warning  
**Threshold:** P95 latency > 2.5s for 5 minutes

**Investigation Steps:**

1. Check Grafana dashboard: `VESPER API Overview`

   - Look at latency distribution by route
   - Identify which endpoints are slow

2. Check dependent services:

   ```bash
   # Check database connection pool
   curl -s http://vesper-api:8000/health | jq '.dependencies'

   # Check Redis latency
   redis-cli -h redis-host INFO stats | grep latency
   ```

3. Check for traffic spikes:

   ```promql
   rate(vesper_api_requests_total[5m])
   ```

4. Check for slow queries:
   - Review Jaeger traces for /v1/ask endpoint
   - Look for spans > 1s

**Resolution:**

- If database-related: Scale RDS or check query plans
- If retrieval-related: Check vector search latency, consider index optimization
- If LLM-related: Check provider status, enable model fallback
- If traffic-related: Scale ECS tasks

**Escalation:** If not resolved in 15 minutes, page on-call engineer.

---

#### VesperAPILatencyP99Critical

**Severity:** Critical  
**Threshold:** P99 latency > 5s for 5 minutes

**Immediate Actions:**

1. Enable circuit breaker for slow routes
2. Scale ECS service to minimum 3 tasks
3. Check ALB target health

**Investigation:**

Same as P95 alert, but prioritize:

- Checking for database deadlocks
- Checking LLM provider rate limits
- Reviewing recent deployments

**Escalation:** Immediate page to on-call + notify #incidents channel.

---

### Error Rate Alerts

#### VesperAPIErrorRateHigh

**Severity:** Critical  
**Threshold:** 5xx error rate > 5% for 5 minutes

**Investigation Steps:**

1. Check error breakdown by type:

   ```promql
   sum(rate(vesper_api_errors_total[5m])) by (error_type)
   ```

2. Check application logs:

   ```bash
   aws logs tail /aws/ecs/vesper-api-gateway --since 5m --filter-pattern "ERROR"
   ```

3. Check for external service failures:

   - OpenAI API status
   - Database connectivity
   - Redis connectivity

4. Review recent code changes in last 2 hours

**Resolution:**

- If auth-related: Check JWT/API key validation
- If database-related: Verify connection pool settings
- If LLM-related: Switch to fallback model
- If recent deployment: Initiate rollback

**Rollback Command:**

```bash
aws ecs update-service --cluster vesper-cluster \
  --service vesper-api-gateway \
  --task-definition vesper-api-gateway:PREVIOUS_VERSION
```

---

### Retrieval Quality Alerts

#### VesperRetrievalNDCGDrop

**Severity:** Warning  
**Threshold:** NDCG@10 < 0.75 (from nightly eval)

**Investigation Steps:**

1. Check nightly eval report in MLflow:

   - Compare with previous 7 days trend
   - Identify which query categories degraded

2. Check embedding quality:

   ```promql
   vesper_eval_ndcg10
   vesper_eval_recall5
   vesper_eval_mrr
   ```

3. Check for recent changes:

   - New document ingestion
   - Embedding model changes
   - Index updates

4. Run ad-hoc evaluation:
   ```bash
   python services/evaluator/runner.py --eval-type retrieval --sample-size 100
   ```

**Resolution:**

- If localized to category: Trigger `reembed_subset` DAG for that category
- If widespread: Review embedding model, consider rolling back
- If data quality: Check ingestion pipeline for errors

**Auto-Remediation:** EventBridge will automatically trigger `reembed_subset` DAG.

---

#### VesperRetrievalRecallDrop

**Severity:** Warning  
**Threshold:** Recall@5 < 0.85

**Investigation:** Same as NDCG drop.

**Additional Checks:**

- Verify vector index is not corrupted
- Check if new documents are properly indexed
- Review chunking parameters

---

### Cost Budget Alerts

#### VesperCostBudgetWarning

**Severity:** Warning  
**Threshold:** Budget utilization > 80%

**Investigation:**

1. Check cost breakdown in Grafana: `VESPER Costs & Budget`
2. Identify high-cost tenants/operations
3. Review token usage trends

**Resolution:**

- Notify tenant if approaching limit
- Review for cost optimization opportunities
- Consider enabling model fallback for non-critical requests

---

#### VesperCostBudgetCritical

**Severity:** Critical  
**Threshold:** Budget utilization > 90%

**Immediate Actions:**

1. Enable model fallback to cheaper models
2. Notify tenant immediately
3. Consider rate limiting

**Cost Governor Actions:**

The cost governor middleware will automatically:

- Switch to fallback models (GPT-4 → GPT-3.5-turbo)
- Add warnings to API responses
- Block requests if budget exhausted

---

### Infrastructure Alerts

#### VesperPGConnectionsHigh

**Severity:** Warning  
**Threshold:** PostgreSQL connections > 80% of max

**Investigation:**

```bash
# Check active connections
psql -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';"

# Check long-running queries
psql -c "SELECT pid, now() - pg_stat_activity.query_start AS duration, query
         FROM pg_stat_activity
         WHERE state = 'active' AND now() - pg_stat_activity.query_start > interval '1 minute';"
```

**Resolution:**

- Terminate long-running queries
- Scale connection pool
- Review application connection management

---

#### VesperRedisHitRatioLow

**Severity:** Warning  
**Threshold:** Redis hit ratio < 0.7

**Investigation:**

- Check memory usage
- Review key expiration patterns
- Check for cache bypass in code

**Resolution:**

- Increase cache TTL if appropriate
- Scale Redis instance
- Review caching strategy

---

## Nightly Evaluation Procedures

### Standard Procedure

The nightly evaluation DAG runs at 2:00 AM UTC daily.

**Tasks:**

1. Health check API
2. Load evaluation queries
3. Run retrieval evaluation (NDCG@10, Recall@5, MRR)
4. Run generation evaluation (faithfulness, relevance)
5. Log to MLflow
6. Push to Prometheus
7. Check for degradation → Slack alert if needed
8. Archive to S3

### Manual Trigger

```bash
# Trigger via Airflow CLI
airflow dags trigger nightly_evaluation

# Trigger via API
curl -X POST "http://airflow:8080/api/v1/dags/nightly_evaluation/dagRuns" \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Viewing Results

- **MLflow:** http://mlflow:5000/#/experiments/vesper-nightly-eval
- **Grafana:** VESPER Retrieval Quality dashboard
- **S3:** s3://vesper-eval-results/nightly/YYYY/MM/DD/

### Handling Failures

1. Check Airflow logs for failed task
2. If health check fails: Check API status
3. If evaluation fails: Check API responses
4. If logging fails: Check MLflow/Prometheus connectivity

---

## Auto-Remediation Procedures

### Re-embed Subset DAG

**Trigger:** NDCG or Recall drops below threshold

**Automatic Actions:**

1. Identify problematic documents
2. Fetch document content
3. Generate new embeddings
4. Validate embeddings
5. Swap in production

**Manual Override:**

```bash
# Trigger with specific documents
airflow dags trigger reembed_subset --conf '{
  "doc_ids": ["doc-001", "doc-002"],
  "embedding_model": "text-embedding-3-large",
  "dry_run": false
}'
```

### Rechunk Parameters DAG

**Trigger:** Chunk quality issues detected

**Automatic Actions:**

1. Analyze chunk quality
2. Select new chunking preset
3. Re-chunk documents
4. Generate embeddings
5. Set up A/B test
6. Store in staging

**Available Presets:**

| Preset   | Chunk Size | Overlap | Split By  |
| -------- | ---------- | ------- | --------- |
| default  | 512        | 50      | sentence  |
| small    | 256        | 25      | sentence  |
| large    | 1024       | 100     | paragraph |
| semantic | 512        | 50      | semantic  |

---

## Incident Response

### Severity Levels

| Level | Description       | Response Time     | Examples                              |
| ----- | ----------------- | ----------------- | ------------------------------------- |
| P1    | Service down      | 15 minutes        | API returning 500s, database down     |
| P2    | Major degradation | 30 minutes        | >50% latency increase, 5%+ error rate |
| P3    | Minor degradation | 2 hours           | Quality metrics drop, budget warnings |
| P4    | Informational     | Next business day | Optimization opportunities            |

### Incident Communication

1. **Acknowledge** alert in PagerDuty/Slack
2. **Assess** impact and severity
3. **Communicate** in #incidents channel
4. **Mitigate** with immediate actions
5. **Resolve** root cause
6. **Post-mortem** within 48 hours for P1/P2

### Post-Incident Template

```markdown
## Incident Report: [Title]

**Date:** YYYY-MM-DD
**Duration:** X hours
**Severity:** P1/P2/P3
**Impact:** Description of user impact

### Timeline

- HH:MM - Alert triggered
- HH:MM - Investigation started
- HH:MM - Root cause identified
- HH:MM - Mitigation applied
- HH:MM - Resolved

### Root Cause

Description of what caused the incident

### Resolution

Steps taken to resolve

### Action Items

- [ ] Action item 1
- [ ] Action item 2

### Lessons Learned

What we learned and how to prevent recurrence
```

---

## Escalation Matrix

| Issue Type     | Primary          | Secondary         | Tertiary      |
| -------------- | ---------------- | ----------------- | ------------- |
| API Issues     | Backend On-Call  | Platform Lead     | CTO           |
| Database       | DBA On-Call      | Backend On-Call   | Platform Lead |
| ML/Quality     | ML On-Call       | Data Science Lead | Platform Lead |
| Infrastructure | DevOps On-Call   | Platform Lead     | CTO           |
| Security       | Security On-Call | Security Lead     | CTO           |

### Contact Information

- **PagerDuty:** vesper-oncall
- **Slack:** #incidents, #vesper-alerts
- **Email:** oncall@vesper.ai

---

## Appendix

### Useful Commands

```bash
# Check API health
curl http://vesper-api:8000/health | jq

# Check ECS service status
aws ecs describe-services --cluster vesper-cluster --services vesper-api-gateway

# Tail logs
aws logs tail /aws/ecs/vesper-api-gateway --follow

# Check Prometheus targets
curl http://prometheus:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'

# Trigger Airflow DAG
airflow dags trigger <dag_id> --conf '{"key": "value"}'
```

### Dashboard Links

- [API Overview](http://grafana:3000/d/vesper-api-overview)
- [Retrieval Quality](http://grafana:3000/d/vesper-retrieval-quality)
- [Costs & Budget](http://grafana:3000/d/vesper-costs)
- [Airflow SLA](http://grafana:3000/d/vesper-airflow-sla)
- [Jaeger Traces](http://jaeger:16686)
- [MLflow](http://mlflow:5000)
