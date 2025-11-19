"""Prometheus metrics instrumentation."""

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from typing import Dict, Any


# API Metrics
api_requests_total = Counter(
    "vesper_api_requests_total",
    "Total API requests",
    ["route", "status", "method"]
)

api_latency_seconds = Histogram(
    "vesper_api_latency_seconds",
    "API request latency in seconds",
    ["route"],
    buckets=[0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 5.0, 10.0]
)

api_active_requests = Gauge(
    "api_active_requests",
    "Number of active API requests",
    ["route"]
)

# Retrieval Metrics
retrieval_hits = Gauge(
    "retrieval_hits",
    "Number of retrieval hits",
    ["tenant"]
)

retrieval_latency_ms = Histogram(
    "retrieval_latency_ms",
    "Retrieval latency in milliseconds",
    buckets=[10, 25, 50, 100, 200, 500, 1000, 2000]
)

retrieval_ndcg = Gauge(
    "retrieval_ndcg",
    "NDCG@10 score for retrieval quality"
)

# Rerank Metrics
rerank_latency_ms = Histogram(
    "rerank_latency_ms",
    "Rerank latency in milliseconds",
    buckets=[10, 25, 50, 100, 200, 500]
)

rerank_ndcg_improvement = Gauge(
    "rerank_ndcg_improvement",
    "NDCG improvement from reranking"
)

# Router Metrics
router_route_total = Counter(
    "router_route_total",
    "Total routing decisions by model",
    ["model", "tenant"]
)

router_latency_ms = Histogram(
    "router_latency_ms",
    "Router decision latency in milliseconds",
    buckets=[1, 5, 10, 25, 50, 100]
)

# Guardrails Metrics
guardrails_block_total = Counter(
    "vesper_guardrails_checks_total",
    "Total requests blocked by guardrails",
    ["reason", "stage", "result"]  # stage = pre or post, result = passed or blocked
)

guardrails_latency_ms = Histogram(
    "vesper_guardrails_latency_ms",
    "Guardrails processing latency in milliseconds",
    ["stage"],
    buckets=[1, 5, 10, 25, 50, 100]
)

guardrails_eval_faithfulness = Gauge(
    "guardrails_eval_faithfulness",
    "Faithfulness score from evaluation",
    ["tenant"]
)

guardrails_eval_hallucination_rate = Gauge(
    "guardrails_eval_hallucination_rate",
    "Hallucination rate from evaluation",
    ["tenant"]
)

# Database Metrics
pg_qps = Gauge(
    "pg_qps",
    "PostgreSQL queries per second"
)

pg_wait_ms = Histogram(
    "pg_wait_ms",
    "PostgreSQL query wait time in milliseconds",
    buckets=[1, 5, 10, 25, 50, 100, 250, 500]
)

pg_connections_active = Gauge(
    "pg_connections_active",
    "Active PostgreSQL connections"
)

pg_connections_idle = Gauge(
    "pg_connections_idle",
    "Idle PostgreSQL connections"
)

# Redis Metrics
redis_hit_ratio = Gauge(
    "redis_hit_ratio",
    "Redis cache hit ratio"
)

redis_latency_ms = Histogram(
    "redis_latency_ms",
    "Redis operation latency in milliseconds",
    buckets=[1, 5, 10, 25, 50, 100]
)

redis_keys_total = Gauge(
    "redis_keys_total",
    "Total keys in Redis cache"
)

# Cost Metrics
token_spend_total = Counter(
    "token_spend_total",
    "Total token spend in USD",
    ["model", "tenant"]
)

token_count_total = Counter(
    "token_count_total",
    "Total tokens consumed",
    ["model", "type"]  # type = input or output
)

cost_per_request = Histogram(
    "cost_per_request",
    "Cost per request in USD",
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5]
)

# Citation Metrics
citation_count_per_response = Histogram(
    "vesper_citations_extracted_total",
    "Number of citations per response",
    buckets=[0, 1, 2, 3, 5, 10, 20]
)

citation_coverage_ratio = Gauge(
    "vesper_citation_coverage_ratio",
    "Ratio of response covered by citations"
)

# Stream Metrics
stream_startup_latency_ms = Histogram(
    "stream_startup_latency_ms",
    "Time to first token in milliseconds",
    buckets=[50, 100, 200, 300, 500, 1000]
)

stream_tokens_per_second = Gauge(
    "stream_tokens_per_second",
    "Token streaming rate"
)


def get_metrics() -> str:
    """
    Get all metrics in Prometheus format.
    
    Returns:
        Prometheus-formatted metrics string
    """
    return generate_latest()


def get_metrics_content_type() -> str:
    """
    Get the content type for Prometheus metrics.
    
    Returns:
        Content type string
    """
    return CONTENT_TYPE_LATEST


class MetricsCollector:
    """Helper class for collecting and recording metrics."""
    
    @staticmethod
    def record_request(route: str, method: str, status_code: int, latency_seconds: float):
        """Record API request metrics."""
        status = f"{status_code // 100}xx"
        api_requests_total.labels(route=route, status=status, method=method).inc()
        api_latency_seconds.labels(route=route).observe(latency_seconds)
    
    @staticmethod
    def record_guardrails(stage: str, latency_ms: float, blocked: bool = False, reason: str = None):
        """Record guardrails metrics."""
        guardrails_latency_ms.labels(stage=stage).observe(latency_ms)
        result = "blocked" if blocked else "passed"
        guardrails_block_total.labels(
            reason=reason or "none",
            stage=stage,
            result=result
        ).inc()
    
    @staticmethod
    def record_cost(model: str, tenant: str, cost_usd: float, input_tokens: int, output_tokens: int):
        """Record cost metrics."""
        token_spend_total.labels(model=model, tenant=tenant).inc(cost_usd)
        token_count_total.labels(model=model, type="input").inc(input_tokens)
        token_count_total.labels(model=model, type="output").inc(output_tokens)
        cost_per_request.observe(cost_usd)
    
    @staticmethod
    def record_stream(startup_latency_ms: float, tokens_per_second: float):
        """Record streaming metrics."""
        stream_startup_latency_ms.observe(startup_latency_ms)
        stream_tokens_per_second.set(tokens_per_second)
    
    @staticmethod
    def record_citations(count: int, coverage_ratio: float):
        """Record citation metrics."""
        citation_count_per_response.observe(count)
        citation_coverage_ratio.set(coverage_ratio)
    
    @staticmethod
    def update_database_metrics(qps: float, wait_ms: float, active: int, idle: int):
        """Update database metrics."""
        pg_qps.set(qps)
        pg_wait_ms.observe(wait_ms)
        pg_connections_active.set(active)
        pg_connections_idle.set(idle)
    
    @staticmethod
    def update_redis_metrics(hit_ratio: float, latency_ms: float, keys: int):
        """Update Redis metrics."""
        redis_hit_ratio.set(hit_ratio)
        redis_latency_ms.observe(latency_ms)
        redis_keys_total.set(keys)
