# VESPER Dashboards Guide

This document describes all Grafana dashboards available for VESPER monitoring and provides guidance on interpreting the visualizations.

---

## Table of Contents

1. [Dashboard Overview](#dashboard-overview)
2. [API Overview Dashboard](#api-overview-dashboard)
3. [Retrieval Quality Dashboard](#retrieval-quality-dashboard)
4. [Costs & Budget Dashboard](#costs--budget-dashboard)
5. [Airflow SLA Dashboard](#airflow-sla-dashboard)
6. [Setting Up Dashboards](#setting-up-dashboards)
7. [Custom Queries](#custom-queries)

---

## Dashboard Overview

| Dashboard                | UID                      | Purpose                        | Refresh |
| ------------------------ | ------------------------ | ------------------------------ | ------- |
| VESPER API Overview      | vesper-api-overview      | Request rates, latency, errors | 30s     |
| VESPER Retrieval Quality | vesper-retrieval-quality | NDCG, recall, reranking        | 30s     |
| VESPER Costs & Budget    | vesper-costs             | Token usage, spend, budgets    | 30s     |
| VESPER Airflow SLA       | vesper-airflow-sla       | DAG runs, task status, SLAs    | 30s     |

All dashboards are tagged with `vesper` for easy filtering.

---

## API Overview Dashboard

**Location:** `monitoring/grafana/dashboards/vesper-api-overview.json`

### Panels

#### Overview Row

| Panel           | Metric                                | Description                   | Thresholds                              |
| --------------- | ------------------------------------- | ----------------------------- | --------------------------------------- |
| Request Rate    | `rate(vesper_api_requests_total[5m])` | Current requests per second   | Green: <100, Yellow: 100-500, Red: >500 |
| P95 Latency     | `histogram_quantile(0.95, ...)`       | 95th percentile response time | Green: <2.5s, Yellow: 2.5-5s, Red: >5s  |
| Error Rate      | `5xx / total`                         | Percentage of 5xx errors      | Green: <1%, Yellow: 1-5%, Red: >5%      |
| Active Requests | `vesper_api_requests_in_flight`       | Currently processing          | Info only                               |

#### Request Metrics Row

| Panel                   | Description                                                        |
| ----------------------- | ------------------------------------------------------------------ |
| Request Rate by Route   | Breakdown of traffic by endpoint (`/v1/ask`, `/v1/retrieve`, etc.) |
| Latency Percentiles     | P50, P95, P99 for `/v1/ask` endpoint                               |
| Requests by Status Code | Stacked bar chart of 2xx, 4xx, 5xx responses                       |
| Stream Startup Latency  | Time-to-first-token for streaming responses                        |

#### Guardrails Row

| Panel              | Description                              |
| ------------------ | ---------------------------------------- |
| Guardrails Checks  | Pass/block rate by stage (input, output) |
| Guardrails Latency | P95 latency added by guardrail checks    |

### Key Queries

```promql
# Request rate per route
sum(rate(vesper_api_requests_total[5m])) by (route)

# P95 latency for /v1/ask
histogram_quantile(0.95, sum(rate(vesper_api_latency_seconds_bucket{route="/v1/ask"}[5m])) by (le))

# Error rate
sum(rate(vesper_api_requests_total{status=~"5.."}[5m])) / sum(rate(vesper_api_requests_total[5m]))
```

---

## Retrieval Quality Dashboard

**Location:** `monitoring/grafana/dashboards/vesper-retrieval-quality.json`

### Panels

#### Quality Metrics Row

| Panel            | Metric                     | Description                           | Thresholds                                |
| ---------------- | -------------------------- | ------------------------------------- | ----------------------------------------- |
| NDCG@10          | `vesper_eval_ndcg10`       | Normalized Discounted Cumulative Gain | Red: <0.6, Yellow: 0.6-0.75, Green: >0.75 |
| Recall@5         | `vesper_eval_recall5`      | % of relevant docs in top 5           | Red: <0.7, Yellow: 0.7-0.85, Green: >0.85 |
| Faithfulness     | `vesper_eval_faithfulness` | Answer grounded in citations          | Red: >0.75, Yellow: 0.6-0.75, Green: <0.6 |
| Pipeline Latency | Retrieval + Rerank P95     | End-to-end retrieval time             | Green: <500ms, Yellow: 500ms-1s, Red: >1s |

#### Retrieval Metrics Over Time

| Panel                      | Description                                 |
| -------------------------- | ------------------------------------------- |
| Quality Metrics Over Time  | NDCG, Recall, MRR trend over time           |
| Retrieval & Rerank Latency | P50, P95 for retrieval and reranking stages |

#### Retrieval Operations Row

| Panel                            | Description                       |
| -------------------------------- | --------------------------------- |
| Retrieval Requests by Index Type | Vector vs hybrid vs keyword       |
| Rerank Requests by Model         | Which reranking models are used   |
| Recall@k by Index Type           | Compare recall across index types |

#### Reranking Impact Row

| Panel                  | Description                    |
| ---------------------- | ------------------------------ |
| Rerank Volume by Model | Daily rerank request volume    |
| Rerank Document Counts | Avg docs in vs out of reranker |

### Understanding Quality Metrics

**NDCG@10** (Normalized Discounted Cumulative Gain):

- Measures ranking quality
- Gives higher weight to relevant docs appearing earlier
- Range: 0-1, higher is better
- Target: ≥0.75

**Recall@5**:

- Fraction of relevant docs in top 5 results
- Range: 0-1, higher is better
- Target: ≥0.85

**MRR** (Mean Reciprocal Rank):

- Average of 1/rank of first relevant result
- Range: 0-1, higher is better
- Target: ≥0.6

**Faithfulness**:

- How well the answer is grounded in citations
- Measured via citation reference checking
- Range: 0-1, higher is better
- Target: ≥0.7

---

## Costs & Budget Dashboard

**Location:** `monitoring/grafana/dashboards/vesper-costs.json`

### Panels

#### Cost Overview Row

| Panel              | Metric                                 | Description                    | Thresholds                                     |
| ------------------ | -------------------------------------- | ------------------------------ | ---------------------------------------------- |
| Total Spend (24h)  | `increase(vesper_cost_usd_total[24h])` | Daily spend in USD             | Green: <$100, Yellow: $100-500, Red: >$500     |
| Avg Cost Per Query | Cost / request count                   | Average spend per /v1/ask call | Green: <$0.01, Yellow: $0.01-0.05, Red: >$0.05 |
| Budget Utilization | Current spend / monthly budget         | % of budget consumed           | Green: <80%, Yellow: 80-90%, Red: >90%         |
| Budget Remaining   | `vesper_cost_budget_remaining`         | USD remaining this month       | Red: <$100, Yellow: $100-500, Green: >$500     |

#### Cost Breakdown Row

| Panel              | Description                       |
| ------------------ | --------------------------------- |
| Spend by Cost Type | Breakdown: llm, embedding, rerank |
| Spend by Model     | Which models cost the most        |

#### Token Usage Row

| Panel                 | Description                     |
| --------------------- | ------------------------------- |
| Token Rate by Model   | Tokens/sec for input and output |
| Token Volume by Model | Total tokens consumed (1h)      |

#### Per-Tenant Budget Row

| Panel                        | Description                |
| ---------------------------- | -------------------------- |
| Budget Utilization by Tenant | Each tenant's budget usage |
| Budget Remaining by Tenant   | USD remaining per tenant   |
| Spend by Tenant              | Hourly spend per tenant    |

### Cost Optimization Tips

1. **High LLM costs?**

   - Consider enabling model fallback to GPT-3.5-turbo
   - Review average context length - shorter contexts = lower costs

2. **High embedding costs?**

   - Check for unnecessary re-embedding
   - Consider caching embeddings for repeated queries

3. **Budget approaching limit?**
   - Cost governor will automatically apply fallbacks
   - Review tenant usage patterns

---

## Airflow SLA Dashboard

**Location:** `monitoring/grafana/dashboards/vesper-airflow-sla.json`

### Panels

#### DAG Overview Row

| Panel                 | Metric                     | Description                     |
| --------------------- | -------------------------- | ------------------------------- |
| Nightly Eval Status   | Last run success/failure   | Green = success, Red = failed   |
| Nightly Eval Duration | `airflow_dag_run_duration` | How long the DAG took           |
| SLA Status            | SLA miss count             | Green = on time, Red = SLA miss |
| DAG Runs (7d)         | Total successful runs      | Activity indicator              |

#### DAG Run History Row

| Panel                  | Description                    |
| ---------------------- | ------------------------------ |
| DAG Runs by Status     | Daily success vs failure count |
| DAG Duration Over Time | Duration trend for key DAGs    |

#### Task-Level Metrics Row

| Panel                       | Description               |
| --------------------------- | ------------------------- |
| Nightly Eval Task Durations | Time per task in the DAG  |
| Nightly Eval Task Status    | Success/fail by task (7d) |

#### SLA Tracking Row

| Panel             | Description                 |
| ----------------- | --------------------------- |
| SLA Misses by DAG | Which DAGs are missing SLAs |
| DAG Success Rate  | Gauge showing reliability % |

#### Auto-Remediation Row

| Panel                    | Description                   |
| ------------------------ | ----------------------------- |
| Remediation DAG Runs     | Count of reembed/rechunk runs |
| Remediation DAG Duration | How long remediation takes    |

### DAG SLAs

| DAG                  | SLA     | Schedule          |
| -------------------- | ------- | ----------------- |
| nightly_evaluation   | 2 hours | Daily 2:00 AM UTC |
| sec_filing_ingestion | 4 hours | Daily 6:00 AM UTC |
| embedding_backfill   | 6 hours | On-demand         |

---

## Setting Up Dashboards

### Prerequisites

1. Prometheus data source configured in Grafana
2. Prometheus scraping VESPER metrics
3. Airflow statsd exporter running (for Airflow metrics)

### Import Dashboards

**Via Grafana UI:**

1. Go to Dashboards → Import
2. Upload JSON file or paste JSON
3. Select Prometheus data source
4. Click Import

**Via Provisioning:**

1. Copy JSON files to `monitoring/grafana/dashboards/`
2. Ensure dashboard provider is configured:

```yaml
# monitoring/grafana/dashboards/dashboard-provider.yml
apiVersion: 1
providers:
  - name: "VESPER Dashboards"
    orgId: 1
    folder: "VESPER"
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    options:
      path: /etc/grafana/provisioning/dashboards
```

3. Restart Grafana

### Data Source Configuration

```yaml
# monitoring/grafana/datasources/prometheus.yml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    jsonData:
      timeInterval: "15s"
```

---

## Custom Queries

### Request Analysis

```promql
# Requests by tenant
sum(rate(vesper_api_requests_total[5m])) by (tenant_id)

# Slow requests (>2s)
histogram_quantile(0.99, sum(rate(vesper_api_latency_seconds_bucket[5m])) by (le, route))

# Error rate by route
sum(rate(vesper_api_errors_total[5m])) by (route, error_type)
```

### Quality Analysis

```promql
# Retrieval recall trend
avg_over_time(vesper_retrieval_recall_at_k{k="5"}[1h])

# Rerank impact (latency added)
histogram_quantile(0.95, rate(vesper_rerank_latency_ms_bucket[5m]))

# Router fallback rate
sum(rate(vesper_router_fallback_total[5m])) / sum(rate(vesper_router_requests_total[5m]))
```

### Cost Analysis

```promql
# Daily cost projection
sum(increase(vesper_cost_usd_total[1h])) * 24

# Cost per 1K tokens
sum(rate(vesper_cost_usd_total[1h])) / (sum(rate(vesper_tokens_input_total[1h])) + sum(rate(vesper_tokens_output_total[1h]))) * 1000

# Top spending tenants
topk(5, sum(increase(vesper_cost_usd_total[24h])) by (tenant_id))
```

### Infrastructure

```promql
# Database connection utilization
pg_stat_activity_count / pg_settings_max_connections

# Redis memory usage
redis_memory_used_bytes / redis_memory_max_bytes

# ECS task CPU
aws_ecs_service_cpu_utilization
```

---

## Alerting from Dashboards

Grafana can create alerts directly from dashboard panels. For VESPER, we recommend using Prometheus alerting rules (defined in `monitoring/prometheus/alerts/vesper-alerts.yml`) for:

- More reliable alerting
- Integration with Alertmanager
- EventBridge integration for auto-remediation

However, dashboard alerts are useful for:

- Ad-hoc monitoring during incidents
- Testing alert thresholds
- Quick visibility during deployments

To create a dashboard alert:

1. Edit a panel
2. Go to Alert tab
3. Define conditions
4. Set notification channels

---

## Best Practices

1. **Use consistent time ranges** - Default to "Last 1 hour" for real-time, "Last 7 days" for trends

2. **Set appropriate refresh rates** - 30s for operational dashboards, 5m for analytical

3. **Use annotations** - Mark deployments and incidents on dashboards

4. **Create focused dashboards** - Don't overcrowd; create separate dashboards for different audiences

5. **Export and version control** - All dashboards should be in JSON in version control
