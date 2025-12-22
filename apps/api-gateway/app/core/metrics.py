"""
Prometheus metrics instrumentation for VESPER API Gateway.

Provides comprehensive metrics for:
- API requests (latency, throughput, errors)
- Retrieval pipeline (hits, latency, quality)
- Reranking (latency, NDCG improvement)
- Model routing (distribution, latency)
- Guardrails (blocks, latency by stage)
- Cost tracking (tokens, USD spend, budgets)
- Streaming (TTFT, tokens/sec)
- Database and cache performance
"""

from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST
from typing import Dict, Any
import time


# =============================================================================
# Service Info
# =============================================================================
service_info = Info(
    "vesper_api_gateway",
    "API Gateway service information"
)
service_info.info({
    "version": "1.0.0",
    "service": "api-gateway",
    "framework": "fastapi"
})


# =============================================================================
# API Request Metrics
# =============================================================================
api_requests_total = Counter(
    "vesper_api_requests_total",
    "Total API requests",
    ["route", "status", "method"]
)

api_requests_in_flight = Gauge(
    "vesper_api_requests_in_flight",
    "Current number of requests being processed",
    ["route"]
)

api_latency_seconds = Histogram(
    "vesper_api_latency_seconds",
    "API request latency in seconds",
    ["route", "method"],
    buckets=[0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 5.0, 10.0]
)

api_errors_total = Counter(
    "vesper_api_errors_total",
    "Total API errors",
    ["route", "error_type", "status_code"]
)

api_active_requests = Gauge(
    "api_active_requests",
    "Number of active API requests (legacy)",
    ["route"]
)


# =============================================================================
# Token Metrics (Input/Output)
# =============================================================================
tokens_input_total = Counter(
    "vesper_tokens_input_total",
    "Total input tokens processed",
    ["model", "tenant"]
)

tokens_output_total = Counter(
    "vesper_tokens_output_total",
    "Total output tokens generated",
    ["model", "tenant"]
)

tokens_per_request = Histogram(
    "vesper_tokens_per_request",
    "Tokens per request",
    ["type"],  # input or output
    buckets=[10, 50, 100, 250, 500, 1000, 2000, 4000]
)


# =============================================================================
# Retrieval Metrics
# =============================================================================
retrieval_requests_total = Counter(
    "vesper_retrieval_requests_total",
    "Total retrieval requests",
    ["tenant", "search_type"]  # search_type: hybrid, vector, bm25
)

retrieval_hits = Gauge(
    "retrieval_hits",
    "Number of retrieval hits",
    ["tenant"]
)

retrieval_docs_returned = Histogram(
    "vesper_retrieval_docs_returned",
    "Number of documents returned per retrieval",
    buckets=[0, 1, 3, 5, 10, 20, 50]
)

retrieval_latency_ms = Histogram(
    "retrieval_latency_ms",
    "Retrieval latency in milliseconds",
    ["search_type"],
    buckets=[10, 25, 50, 100, 200, 500, 1000, 2000]
)

retrieval_ndcg = Gauge(
    "retrieval_ndcg",
    "NDCG@10 score for retrieval quality",
    ["tenant"]
)

retrieval_recall_at_k = Gauge(
    "vesper_retrieval_recall_at_k",
    "Recall@K for retrieval quality",
    ["k", "tenant"]
)

retrieval_mrr = Gauge(
    "vesper_retrieval_mrr",
    "Mean Reciprocal Rank for retrieval",
    ["tenant"]
)


# =============================================================================
# Rerank Metrics
# =============================================================================
rerank_requests_total = Counter(
    "vesper_rerank_requests_total",
    "Total rerank requests",
    ["model"]
)

rerank_latency_ms = Histogram(
    "rerank_latency_ms",
    "Rerank latency in milliseconds",
    ["model"],
    buckets=[10, 25, 50, 100, 200, 500, 1000]
)

rerank_docs_processed = Histogram(
    "vesper_rerank_docs_processed",
    "Number of documents processed by reranker",
    buckets=[5, 10, 20, 50, 100]
)

rerank_ndcg_improvement = Gauge(
    "rerank_ndcg_improvement",
    "NDCG improvement from reranking",
    ["tenant"]
)

rerank_position_change = Histogram(
    "vesper_rerank_position_change",
    "Average position change from reranking",
    buckets=[0, 1, 2, 3, 5, 10, 20]
)


# =============================================================================
# Router Metrics
# =============================================================================
router_requests_total = Counter(
    "vesper_router_requests_total",
    "Total routing decisions",
    ["model", "tenant", "reason"]  # reason: cost, quality, speed, default
)

router_route_total = Counter(
    "router_route_total",
    "Total routing decisions by model (legacy)",
    ["model", "tenant"]
)

router_latency_ms = Histogram(
    "router_latency_ms",
    "Router decision latency in milliseconds",
    buckets=[1, 5, 10, 25, 50, 100]
)

router_model_distribution = Gauge(
    "vesper_router_model_distribution",
    "Distribution of model selection",
    ["model", "tenant"]
)

router_fallback_total = Counter(
    "vesper_router_fallback_total",
    "Total times router fell back to cheaper model",
    ["from_model", "to_model", "reason"]
)


# =============================================================================
# Guardrails Metrics
# =============================================================================
guardrails_checks_total = Counter(
    "vesper_guardrails_checks_total",
    "Total guardrails checks",
    ["stage", "check_type", "result"]  # stage: pre/post, result: passed/blocked
)

guardrails_block_total = Counter(
    "vesper_guardrails_block_total",
    "Total requests blocked by guardrails",
    ["reason", "stage"]
)

guardrails_latency_ms = Histogram(
    "vesper_guardrails_latency_ms",
    "Guardrails processing latency in milliseconds",
    ["stage", "check_type"],
    buckets=[1, 5, 10, 25, 50, 100, 250]
)

guardrails_pii_detected_total = Counter(
    "vesper_guardrails_pii_detected_total",
    "Total PII instances detected",
    ["pii_type"]  # email, phone, ssn, etc.
)

guardrails_toxicity_score = Histogram(
    "vesper_guardrails_toxicity_score",
    "Toxicity scores from moderation",
    buckets=[0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 1.0]
)

guardrails_eval_faithfulness = Gauge(
    "guardrails_eval_faithfulness",
    "Faithfulness score from evaluation",
    ["tenant"]
)

guardrails_eval_groundedness = Gauge(
    "vesper_guardrails_eval_groundedness",
    "Groundedness score from evaluation",
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


# =============================================================================
# Cost Metrics
# =============================================================================
cost_usd_total = Counter(
    "vesper_cost_usd_total",
    "Total cost in USD",
    ["model", "tenant", "operation"]  # operation: embedding, completion, rerank
)

token_spend_total = Counter(
    "token_spend_total",
    "Total token spend in USD (legacy)",
    ["model", "tenant"]
)

token_count_total = Counter(
    "token_count_total",
    "Total tokens consumed (legacy)",
    ["model", "type"]  # type = input or output
)

cost_per_request = Histogram(
    "vesper_cost_per_request_usd",
    "Cost per request in USD",
    ["model"],
    buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
)

cost_budget_total = Gauge(
    "vesper_cost_budget_total_usd",
    "Total budget in USD",
    ["tenant"]
)

cost_budget_used = Gauge(
    "vesper_cost_budget_used_usd",
    "Budget used in USD",
    ["tenant"]
)

cost_budget_remaining = Gauge(
    "vesper_cost_budget_remaining_usd",
    "Budget remaining in USD",
    ["tenant"]
)

cost_budget_utilization = Gauge(
    "vesper_cost_budget_utilization_ratio",
    "Budget utilization ratio (0-1)",
    ["tenant"]
)


# =============================================================================
# Citation Metrics
# =============================================================================
citation_count_per_response = Histogram(
    "vesper_citations_per_response",
    "Number of citations per response",
    buckets=[0, 1, 2, 3, 5, 10, 20]
)

citation_coverage_ratio = Gauge(
    "vesper_citation_coverage_ratio",
    "Ratio of response covered by citations",
    ["tenant"]
)

citation_verification_total = Counter(
    "vesper_citation_verification_total",
    "Total citation verifications",
    ["result"]  # verified, unverified, partial
)


# =============================================================================
# Streaming Metrics
# =============================================================================
stream_startup_latency_ms = Histogram(
    "vesper_stream_startup_latency_ms",
    "Time to first token in milliseconds",
    buckets=[25, 50, 100, 200, 300, 500, 750, 1000, 2000]
)

stream_tokens_per_second = Gauge(
    "vesper_stream_tokens_per_second",
    "Token streaming rate",
    ["tenant"]
)

stream_duration_seconds = Histogram(
    "vesper_stream_duration_seconds",
    "Total streaming duration in seconds",
    buckets=[0.5, 1, 2, 3, 5, 10, 20, 30, 60]
)

stream_interruptions_total = Counter(
    "vesper_stream_interruptions_total",
    "Total stream interruptions",
    ["reason"]  # client_disconnect, timeout, error
)


# =============================================================================
# Evaluation Metrics (populated by nightly eval)
# =============================================================================
eval_faithfulness = Gauge(
    "vesper_eval_faithfulness",
    "Faithfulness score from nightly evaluation",
    ["eval_date"]
)

eval_groundedness = Gauge(
    "vesper_eval_groundedness",
    "Groundedness score from nightly evaluation",
    ["eval_date"]
)

eval_answer_relevance = Gauge(
    "vesper_eval_answer_relevance",
    "Answer relevance score from nightly evaluation",
    ["eval_date"]
)

eval_context_precision = Gauge(
    "vesper_eval_context_precision",
    "Context precision score from nightly evaluation",
    ["eval_date"]
)

eval_latency_p50 = Gauge(
    "vesper_eval_latency_p50_ms",
    "P50 latency from nightly evaluation",
    ["eval_date"]
)

eval_latency_p95 = Gauge(
    "vesper_eval_latency_p95_ms",
    "P95 latency from nightly evaluation",
    ["eval_date"]
)

eval_pass_rate = Gauge(
    "vesper_eval_pass_rate",
    "Pass rate from nightly evaluation",
    ["eval_date"]
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
    """
    Helper class for collecting and recording metrics.
    
    Provides high-level methods for recording metrics across the API Gateway,
    ensuring consistent labeling and proper metric collection.
    """
    
    @staticmethod
    def record_request(
        route: str,
        method: str,
        status_code: int,
        latency_seconds: float,
        error_type: str = None
    ):
        """
        Record API request metrics.
        
        Args:
            route: API route (e.g., "/v1/ask")
            method: HTTP method (GET, POST, etc.)
            status_code: HTTP status code
            latency_seconds: Request latency in seconds
            error_type: Optional error type for failed requests
        """
        status = f"{status_code // 100}xx"
        api_requests_total.labels(route=route, status=status, method=method).inc()
        api_latency_seconds.labels(route=route, method=method).observe(latency_seconds)
        
        if error_type and status_code >= 400:
            api_errors_total.labels(
                route=route,
                error_type=error_type,
                status_code=str(status_code)
            ).inc()
    
    @staticmethod
    def record_retrieval(
        tenant: str,
        search_type: str,
        latency_ms: float,
        docs_returned: int,
        ndcg: float = None,
        recall_at_k: dict = None,
        mrr: float = None
    ):
        """
        Record retrieval metrics.
        
        Args:
            tenant: Tenant ID
            search_type: Type of search (hybrid, vector, bm25)
            latency_ms: Retrieval latency in milliseconds
            docs_returned: Number of documents returned
            ndcg: NDCG@10 score (optional)
            recall_at_k: Dict of recall@k values (optional)
            mrr: Mean Reciprocal Rank (optional)
        """
        retrieval_requests_total.labels(tenant=tenant, search_type=search_type).inc()
        retrieval_latency_ms.labels(search_type=search_type).observe(latency_ms)
        retrieval_docs_returned.observe(docs_returned)
        retrieval_hits.labels(tenant=tenant).set(docs_returned)
        
        if ndcg is not None:
            retrieval_ndcg.labels(tenant=tenant).set(ndcg)
        
        if recall_at_k:
            for k, recall in recall_at_k.items():
                retrieval_recall_at_k.labels(k=str(k), tenant=tenant).set(recall)
        
        if mrr is not None:
            retrieval_mrr.labels(tenant=tenant).set(mrr)
    
    @staticmethod
    def record_rerank(
        model: str,
        latency_ms: float,
        docs_processed: int,
        ndcg_improvement: float = None,
        avg_position_change: float = None,
        tenant: str = "default"
    ):
        """
        Record reranking metrics.
        
        Args:
            model: Reranker model name
            latency_ms: Reranking latency in milliseconds
            docs_processed: Number of documents reranked
            ndcg_improvement: NDCG improvement from reranking
            avg_position_change: Average position change
            tenant: Tenant ID
        """
        rerank_requests_total.labels(model=model).inc()
        rerank_latency_ms.labels(model=model).observe(latency_ms)
        rerank_docs_processed.observe(docs_processed)
        
        if ndcg_improvement is not None:
            rerank_ndcg_improvement.labels(tenant=tenant).set(ndcg_improvement)
        
        if avg_position_change is not None:
            rerank_position_change.observe(avg_position_change)
    
    @staticmethod
    def record_router(
        model: str,
        tenant: str,
        reason: str,
        latency_ms: float
    ):
        """
        Record router metrics.
        
        Args:
            model: Selected model
            tenant: Tenant ID
            reason: Routing reason (cost, quality, speed, default)
            latency_ms: Routing decision latency
        """
        router_requests_total.labels(model=model, tenant=tenant, reason=reason).inc()
        router_route_total.labels(model=model, tenant=tenant).inc()
        router_latency_ms.observe(latency_ms)
    
    @staticmethod
    def record_router_fallback(from_model: str, to_model: str, reason: str):
        """Record router fallback event."""
        router_fallback_total.labels(
            from_model=from_model,
            to_model=to_model,
            reason=reason
        ).inc()
    
    @staticmethod
    def record_guardrails(
        stage: str,
        check_type: str,
        latency_ms: float,
        passed: bool,
        reason: str = None
    ):
        """
        Record guardrails metrics.
        
        Args:
            stage: "pre" or "post"
            check_type: Type of check (input_validation, jailbreak, pii, etc.)
            latency_ms: Check latency in milliseconds
            passed: Whether the check passed
            reason: Block reason (if not passed)
        """
        result = "passed" if passed else "blocked"
        guardrails_checks_total.labels(
            stage=stage,
            check_type=check_type,
            result=result
        ).inc()
        guardrails_latency_ms.labels(stage=stage, check_type=check_type).observe(latency_ms)
        
        if not passed and reason:
            guardrails_block_total.labels(reason=reason, stage=stage).inc()
    
    @staticmethod
    def record_pii_detection(pii_type: str, count: int = 1):
        """Record PII detection event."""
        for _ in range(count):
            guardrails_pii_detected_total.labels(pii_type=pii_type).inc()
    
    @staticmethod
    def record_toxicity(score: float):
        """Record toxicity score."""
        guardrails_toxicity_score.observe(score)
    
    @staticmethod
    def record_cost(
        model: str,
        tenant: str,
        cost_usd: float,
        input_tokens: int,
        output_tokens: int,
        operation: str = "completion"
    ):
        """
        Record cost metrics.
        
        Args:
            model: Model name
            tenant: Tenant ID
            cost_usd: Cost in USD
            input_tokens: Input token count
            output_tokens: Output token count
            operation: Type of operation (embedding, completion, rerank)
        """
        cost_usd_total.labels(model=model, tenant=tenant, operation=operation).inc(cost_usd)
        token_spend_total.labels(model=model, tenant=tenant).inc(cost_usd)
        token_count_total.labels(model=model, type="input").inc(input_tokens)
        token_count_total.labels(model=model, type="output").inc(output_tokens)
        tokens_input_total.labels(model=model, tenant=tenant).inc(input_tokens)
        tokens_output_total.labels(model=model, tenant=tenant).inc(output_tokens)
        tokens_per_request.labels(type="input").observe(input_tokens)
        tokens_per_request.labels(type="output").observe(output_tokens)
        cost_per_request.labels(model=model).observe(cost_usd)
    
    @staticmethod
    def update_budget(
        tenant: str,
        budget_total: float,
        budget_used: float
    ):
        """
        Update budget metrics.
        
        Args:
            tenant: Tenant ID
            budget_total: Total budget in USD
            budget_used: Used budget in USD
        """
        remaining = max(0, budget_total - budget_used)
        utilization = budget_used / budget_total if budget_total > 0 else 0
        
        cost_budget_total.labels(tenant=tenant).set(budget_total)
        cost_budget_used.labels(tenant=tenant).set(budget_used)
        cost_budget_remaining.labels(tenant=tenant).set(remaining)
        cost_budget_utilization.labels(tenant=tenant).set(utilization)
    
    @staticmethod
    def record_stream(
        startup_latency_ms: float,
        tokens_per_second: float,
        duration_seconds: float = None,
        tenant: str = "default"
    ):
        """
        Record streaming metrics.
        
        Args:
            startup_latency_ms: Time to first token in milliseconds
            tokens_per_second: Streaming rate
            duration_seconds: Total streaming duration
            tenant: Tenant ID
        """
        stream_startup_latency_ms.observe(startup_latency_ms)
        stream_tokens_per_second.labels(tenant=tenant).set(tokens_per_second)
        if duration_seconds is not None:
            stream_duration_seconds.observe(duration_seconds)
    
    @staticmethod
    def record_stream_interruption(reason: str):
        """Record stream interruption."""
        stream_interruptions_total.labels(reason=reason).inc()
    
    @staticmethod
    def record_citations(
        count: int,
        coverage_ratio: float,
        verification_result: str = None,
        tenant: str = "default"
    ):
        """
        Record citation metrics.
        
        Args:
            count: Number of citations
            coverage_ratio: Ratio of response covered by citations
            verification_result: Verification result (verified, unverified, partial)
            tenant: Tenant ID
        """
        citation_count_per_response.observe(count)
        citation_coverage_ratio.labels(tenant=tenant).set(coverage_ratio)
        if verification_result:
            citation_verification_total.labels(result=verification_result).inc()
    
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
    
    @staticmethod
    def record_eval_results(
        eval_date: str,
        faithfulness: float,
        groundedness: float,
        answer_relevance: float,
        context_precision: float,
        latency_p50_ms: float,
        latency_p95_ms: float,
        pass_rate: float
    ):
        """
        Record nightly evaluation results.
        
        Args:
            eval_date: Evaluation date (YYYY-MM-DD)
            faithfulness: Faithfulness score
            groundedness: Groundedness score
            answer_relevance: Answer relevance score
            context_precision: Context precision score
            latency_p50_ms: P50 latency in milliseconds
            latency_p95_ms: P95 latency in milliseconds
            pass_rate: Overall pass rate
        """
        eval_faithfulness.labels(eval_date=eval_date).set(faithfulness)
        eval_groundedness.labels(eval_date=eval_date).set(groundedness)
        eval_answer_relevance.labels(eval_date=eval_date).set(answer_relevance)
        eval_context_precision.labels(eval_date=eval_date).set(context_precision)
        eval_latency_p50.labels(eval_date=eval_date).set(latency_p50_ms)
        eval_latency_p95.labels(eval_date=eval_date).set(latency_p95_ms)
        eval_pass_rate.labels(eval_date=eval_date).set(pass_rate)
