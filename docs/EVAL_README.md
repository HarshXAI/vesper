# VESPER Evaluation System

This document describes VESPER's nightly evaluation system, including metrics, procedures, and interpretation guidelines.

---

## Table of Contents

1. [Overview](#overview)
2. [Evaluation Metrics](#evaluation-metrics)
3. [Nightly Evaluation DAG](#nightly-evaluation-dag)
4. [Running Evaluations](#running-evaluations)
5. [Interpreting Results](#interpreting-results)
6. [Evaluation Queries](#evaluation-queries)
7. [Auto-Remediation](#auto-remediation)
8. [MLflow Integration](#mlflow-integration)

---

## Overview

VESPER's evaluation system continuously monitors retrieval and generation quality through:

1. **Nightly Evaluation DAG** - Runs at 2:00 AM UTC daily
2. **Real-time Metrics** - Live retrieval quality tracking
3. **MLflow Logging** - Historical tracking and experiment comparison
4. **Auto-Remediation** - Automatic quality recovery pipelines

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Nightly Evaluation                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────┐   ┌──────────────┐   ┌──────────────────┐    │
│  │ Airflow  │──▶│ Eval Runner  │──▶│ VESPER API       │    │
│  │ DAG      │   │              │   │ /v1/ask          │    │
│  └──────────┘   │              │   │ /v1/retrieve     │    │
│       │         └──────────────┘   └──────────────────┘    │
│       │               │                                     │
│       ▼               ▼                                     │
│  ┌──────────┐   ┌──────────────┐   ┌──────────────────┐    │
│  │ S3       │   │ MLflow       │   │ Prometheus       │    │
│  │ Archive  │   │ Tracking     │   │ Pushgateway      │    │
│  └──────────┘   └──────────────┘   └──────────────────┘    │
│                       │                    │                 │
│                       ▼                    ▼                 │
│                 ┌──────────────────────────────┐            │
│                 │ Grafana Dashboards           │            │
│                 │ + Alert Rules                │            │
│                 └──────────────────────────────┘            │
│                              │                               │
│                              ▼                               │
│                 ┌──────────────────────────────┐            │
│                 │ EventBridge                  │            │
│                 │ → reembed_subset DAG         │            │
│                 │ → rechunk_params DAG         │            │
│                 └──────────────────────────────┘            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Evaluation Metrics

### Retrieval Metrics

| Metric        | Description                                      | Target | Threshold    |
| ------------- | ------------------------------------------------ | ------ | ------------ |
| **NDCG@10**   | Normalized Discounted Cumulative Gain at rank 10 | ≥0.80  | 0.75 (alert) |
| **Recall@5**  | Fraction of relevant docs in top 5               | ≥0.90  | 0.85 (alert) |
| **Recall@10** | Fraction of relevant docs in top 10              | ≥0.95  | 0.90 (alert) |
| **MRR**       | Mean Reciprocal Rank                             | ≥0.70  | 0.60 (alert) |

#### NDCG@10

Measures ranking quality, giving higher weight to relevant documents appearing earlier.

```
NDCG = DCG / IDCG

DCG = Σ (rel_i / log2(i+1))  for i = 1 to 10
IDCG = ideal DCG (perfect ranking)
```

**Interpretation:**

- 1.0 = Perfect ranking
- 0.8+ = Excellent
- 0.7-0.8 = Good
- 0.6-0.7 = Needs improvement
- <0.6 = Poor

#### Recall@k

Measures coverage - how many relevant documents are in the top k results.

```
Recall@k = |Retrieved@k ∩ Relevant| / |Relevant|
```

**Interpretation:**

- 0.9+ = Excellent coverage
- 0.8-0.9 = Good
- 0.7-0.8 = Acceptable
- <0.7 = Poor

#### MRR

Average of reciprocal rank of first relevant document.

```
MRR = (1/|Q|) Σ (1/rank_i)  for each query
```

**Interpretation:**

- 1.0 = First result always relevant
- 0.5 = Relevant doc usually in top 2
- <0.5 = Relevant docs buried

### Generation Metrics

| Metric           | Description                  | Target  | Threshold    |
| ---------------- | ---------------------------- | ------- | ------------ |
| **Faithfulness** | Answer grounded in citations | ≥0.80   | 0.70 (alert) |
| **Relevance**    | Answer addresses the query   | ≥0.85   | 0.75 (alert) |
| **Latency**      | Response time                | <2s P95 | 2.5s (alert) |

#### Faithfulness

Measures how well the generated answer is supported by cited sources.

**Calculation:**

- Check if cited text appears in or supports the answer
- Higher = more grounded, less hallucination

**Interpretation:**

- 0.9+ = Highly grounded
- 0.7-0.9 = Acceptable
- <0.7 = Risk of hallucination

#### Relevance

Measures if the answer addresses the user's question.

**Calculation:**

- Keyword overlap between query and answer
- Answer completeness
- Semantic similarity (when available)

---

## Nightly Evaluation DAG

### Schedule

- **Time:** 2:00 AM UTC daily
- **SLA:** 2 hours
- **Retries:** 2
- **Timeout:** 2 hours

### Tasks

```
health_check
    │
    ▼
load_eval_queries
    │
    ├──────────────────┐
    ▼                  ▼
run_retrieval_eval   run_generation_eval
    │                  │
    └────────┬─────────┘
             ▼
        log_to_mlflow
             │
             ▼
        push_to_prometheus
             │
             ▼
        check_degradation
         /           \
        ▼             ▼
   send_slack    skip_alert
        \             /
         └─────┬─────┘
               ▼
           archive_results
```

### Task Details

| Task                | Duration  | Description                             |
| ------------------- | --------- | --------------------------------------- |
| health_check        | ~5s       | Verify API is healthy                   |
| load_eval_queries   | ~10s      | Load queries from JSONL                 |
| run_retrieval_eval  | ~30-60min | Evaluate retrieval for all queries      |
| run_generation_eval | ~30-60min | Evaluate generation (subset of queries) |
| log_to_mlflow       | ~10s      | Log metrics to MLflow                   |
| push_to_prometheus  | ~5s       | Push to Pushgateway                     |
| check_degradation   | ~5s       | Compare against thresholds              |
| archive_results     | ~30s      | Save to S3                              |

---

## Running Evaluations

### Automatic (Nightly)

The DAG runs automatically. No action needed.

### Manual Trigger (Airflow)

```bash
# Via Airflow CLI
airflow dags trigger nightly_evaluation

# With custom config
airflow dags trigger nightly_evaluation --conf '{
  "sample_size": 100,
  "skip_generation": true
}'
```

### Manual Trigger (Standalone)

```bash
cd services/evaluator

# Run full evaluation
python runner.py --eval-type all --output-dir ./results

# Run retrieval only
python runner.py --eval-type retrieval --sample-size 50

# Run with MLflow logging
python runner.py --eval-type all --mlflow

# Use custom queries
python runner.py --queries ./custom_queries.jsonl
```

### CLI Options

| Option                | Default                 | Description                      |
| --------------------- | ----------------------- | -------------------------------- |
| `--eval-type`         | all                     | Type: all, retrieval, generation |
| `--queries`           | data/eval/queries.jsonl | Path to queries file             |
| `--output-dir`        | ./results               | Where to save results            |
| `--sample-size`       | 50                      | Max queries to evaluate          |
| `--api-url`           | http://localhost:8000   | VESPER API URL                   |
| `--mlflow`            | false                   | Log to MLflow                    |
| `--skip-health-check` | false                   | Skip API health check            |

---

## Interpreting Results

### Sample Output

```
============================================================
VESPER EVALUATION REPORT
============================================================
Timestamp: 2024-01-15T02:45:23.456789
Duration: 1847.32s

Retrieval Metrics:
  NDCG@10:  0.8234
  Recall@5: 0.8912
  MRR:      0.7156
  Avg Latency: 245ms

Generation Metrics:
  Faithfulness: 0.7823
  Relevance:    0.8567
  Avg Latency:  1234ms

✅ No alerts - all metrics within thresholds
============================================================
```

### Understanding Degradation

When metrics degrade:

1. **Check trend** - Is it gradual or sudden?

   - Gradual: Data quality issue, model drift
   - Sudden: Code change, infrastructure issue

2. **Check by category** - Which query categories degraded?

   - Single category: Data issue in that domain
   - All categories: Systemic issue

3. **Check correlations** - What else changed?
   - Recent deployments
   - New data ingestion
   - Model changes

### Common Issues

| Symptom              | Possible Cause    | Action                      |
| -------------------- | ----------------- | --------------------------- |
| NDCG drop, recall ok | Ranking issue     | Check reranking model       |
| Recall drop          | Missing documents | Check ingestion pipeline    |
| Faithfulness drop    | Citation issues   | Check retrieval context     |
| All metrics drop     | Systemic issue    | Check API, database, models |

---

## Evaluation Queries

### Query Format

Queries are stored in JSONL format:

```json
{
  "id": "q001",
  "query": "What are the key risk factors?",
  "expected_doc_ids": ["doc-001", "doc-002"],
  "category": "risk_factors"
}
```

### Fields

| Field              | Required | Description                     |
| ------------------ | -------- | ------------------------------- |
| `id`               | Yes      | Unique query identifier         |
| `query`            | Yes      | The question to ask             |
| `expected_doc_ids` | Yes      | Ground truth relevant documents |
| `category`         | No       | Category for analysis grouping  |
| `metadata`         | No       | Additional context              |

### Query Categories

| Category            | Description                     | Count |
| ------------------- | ------------------------------- | ----- |
| risk_factors        | SEC risk disclosures            | ~50   |
| financials          | Revenue, margins, growth        | ~30   |
| business_strategy   | Strategy and outlook            | ~25   |
| compensation        | Executive compensation          | ~20   |
| esg                 | Environmental/social/governance | ~20   |
| legal               | Legal proceedings               | ~15   |
| accounting_policies | Accounting methods              | ~15   |
| other               | Miscellaneous                   | ~25   |

### Adding New Queries

1. Create queries with ground truth document IDs
2. Add to `data/eval/queries.jsonl`
3. Test with standalone runner
4. Commit and deploy

```bash
# Add new query
echo '{"id": "q100", "query": "New question?", "expected_doc_ids": ["doc-x"], "category": "other"}' >> data/eval/queries.jsonl
```

---

## Auto-Remediation

When evaluation detects quality degradation, auto-remediation DAGs can be triggered.

### Trigger Conditions

| Condition            | DAG Triggered    |
| -------------------- | ---------------- |
| NDCG@10 < 0.75       | `reembed_subset` |
| Recall@5 < 0.85      | `reembed_subset` |
| Chunk quality issues | `rechunk_params` |

### Remediation Flow

```
Quality Drop Detected
        │
        ▼
EventBridge Rule Fires
        │
        ▼
Lambda Triggers Airflow
        │
        ├── reembed_subset ──► Re-embed problematic docs
        │
        └── rechunk_params ──► Re-chunk with better params
                                    │
                                    ▼
                              A/B Test New Chunks
                                    │
                                    ▼
                              Swap if Improved
```

### Manual Remediation

```bash
# Trigger re-embedding for specific docs
airflow dags trigger reembed_subset --conf '{
  "doc_ids": ["doc-001", "doc-002", "doc-003"],
  "embedding_model": "text-embedding-3-large"
}'

# Trigger re-chunking with new parameters
airflow dags trigger rechunk_params --conf '{
  "categories": ["risk_factors"],
  "target_preset": "semantic"
}'
```

---

## MLflow Integration

### Accessing MLflow

- **URL:** http://mlflow:5000
- **Experiment:** vesper-nightly-eval

### Logged Metrics

| Metric         | Type      | Description          |
| -------------- | --------- | -------------------- |
| ndcg10         | Metric    | NDCG@10 score        |
| recall5        | Metric    | Recall@5 score       |
| mrr            | Metric    | Mean Reciprocal Rank |
| faithfulness   | Metric    | Faithfulness score   |
| relevance      | Metric    | Relevance score      |
| avg_latency_ms | Metric    | Average latency      |
| num_queries    | Parameter | Queries evaluated    |
| eval_date      | Parameter | Evaluation timestamp |

### Comparing Runs

1. Go to MLflow UI
2. Select `vesper-nightly-eval` experiment
3. Select runs to compare
4. Click "Compare" button
5. View metric charts

### Registering Models

When a new embedding or reranking model shows improvement:

```python
import mlflow

with mlflow.start_run():
    mlflow.log_param("model_name", "text-embedding-3-large")
    mlflow.log_metric("ndcg10", 0.85)

    # Register if better than current
    mlflow.register_model(
        "runs:/<run_id>/model",
        "vesper-embedding-model"
    )
```

---

## Troubleshooting

### DAG Failures

| Error               | Cause            | Fix                               |
| ------------------- | ---------------- | --------------------------------- |
| Health check failed | API down         | Check API status                  |
| No queries loaded   | Missing file     | Check queries.jsonl path          |
| Timeout             | Slow API         | Increase timeout or reduce sample |
| MLflow error        | Connection issue | Check MLflow connectivity         |

### Low Scores

| Issue             | Investigation                          |
| ----------------- | -------------------------------------- |
| Sudden drop       | Check recent deployments, data changes |
| Gradual decline   | Check data quality, model drift        |
| Category-specific | Check that category's documents        |
| Random variation  | May need more evaluation queries       |

### Debugging

```bash
# Check DAG logs
airflow logs -t run_retrieval_eval nightly_evaluation <run_id>

# Run single query manually
curl -X POST http://vesper-api:8000/v1/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query": "test query", "top_k": 10}'

# Check Prometheus metrics
curl http://prometheus:9090/api/v1/query?query=vesper_eval_ndcg10
```

---

## Best Practices

1. **Maintain diverse queries** - Cover all document types and categories
2. **Update ground truth** - Keep expected_doc_ids current as data changes
3. **Monitor trends** - Focus on trends, not single-day variations
4. **Calibrate thresholds** - Adjust based on your quality requirements
5. **Test remediation** - Dry-run remediation DAGs before production
6. **Archive results** - Keep historical data for trend analysis
