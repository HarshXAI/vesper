"""
OpenTelemetry tracing utilities for VESPER API Gateway.

Provides:
- Trace context propagation (W3C format)
- Span management utilities
- Tracer provider configuration
- Integration with Jaeger/OTLP exporters

Trace Hierarchy:
    POST /v1/ask                          [Root span]
    ├── guardrails.pre_process            [Pre-request validation]
    │   ├── input_validation
    │   ├── jailbreak_detection
    │   └── policy_check
    ├── stream_response.generate          [Response generation]
    │   ├── retrieval.search              [Vector + BM25 search]
    │   ├── rerank.score                  [Cross-encoder reranking]
    │   ├── router.route                  [Model routing decision]
    │   ├── llm.generate                  [LLM inference]
    │   └── guardrails.post_process       [Post-response checks]
    │       ├── pii_redaction
    │       ├── moderation
    │       └── citation_verification
"""

from typing import Dict, Any, Optional, Callable
from functools import wraps
from contextlib import contextmanager
import time

from opentelemetry import trace
from opentelemetry.propagate import inject, extract
from opentelemetry.trace import Status, StatusCode, SpanKind
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes

# Default tracer instance
_tracer: Optional[trace.Tracer] = None


def init_tracer(
    service_name: str = "api-gateway",
    service_version: str = "1.0.0",
    otel_endpoint: Optional[str] = None,
    environment: str = "development"
) -> trace.Tracer:
    """
    Initialize the OpenTelemetry tracer provider.
    
    Args:
        service_name: Name of the service
        service_version: Version of the service
        otel_endpoint: OTLP endpoint URL (None for console export)
        environment: Deployment environment
    
    Returns:
        Configured tracer instance
    """
    global _tracer
    
    resource = Resource.create({
        ResourceAttributes.SERVICE_NAME: service_name,
        ResourceAttributes.SERVICE_VERSION: service_version,
        ResourceAttributes.DEPLOYMENT_ENVIRONMENT: environment,
        "service.namespace": "vesper",
    })
    
    provider = TracerProvider(resource=resource)
    
    if otel_endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        exporter = OTLPSpanExporter(endpoint=otel_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    else:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    
    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(service_name, service_version)
    
    return _tracer


def get_tracer() -> trace.Tracer:
    """
    Get the global tracer instance.
    
    Returns:
        Tracer instance (creates default if not initialized)
    """
    global _tracer
    if _tracer is None:
        _tracer = trace.get_tracer("api-gateway", "1.0.0")
    return _tracer


def get_trace_headers() -> Dict[str, str]:
    """
    Get trace propagation headers for downstream service calls.
    
    Returns a dict of HTTP headers containing the current trace context
    in W3C Trace Context format (traceparent, tracestate).
    
    Usage:
        headers = get_trace_headers()
        response = await httpx.get(url, headers=headers)
    """
    headers = {}
    inject(headers)  # Injects traceparent, tracestate
    return headers


def extract_trace_context(headers: Dict[str, str]):
    """
    Extract trace context from incoming request headers.
    
    Args:
        headers: HTTP headers dict
    
    Returns:
        Extracted context for span creation
    """
    return extract(headers)


def get_current_trace_id() -> str:
    """
    Get the current trace ID as a hex string.
    
    Returns:
        Trace ID in lowercase hex format (32 characters).
        Returns "00000000000000000000000000000000" if no active span.
    """
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        return format(span.get_span_context().trace_id, "032x")
    return "0" * 32


def get_current_span_id() -> str:
    """
    Get the current span ID as a hex string.
    
    Returns:
        Span ID in lowercase hex format (16 characters).
        Returns "0000000000000000" if no active span.
    """
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        return format(span.get_span_context().span_id, "016x")
    return "0" * 16


def add_span_attributes(attributes: Dict[str, Any]) -> None:
    """
    Add attributes to the current active span.
    
    Args:
        attributes: Dictionary of attribute name-value pairs.
                   Values should be str, bool, int, float, or lists thereof.
    
    Usage:
        add_span_attributes({
            "user_id": "user-123",
            "query_length": 45,
            "cache_hit": True
        })
    """
    span = trace.get_current_span()
    if span and span.is_recording():
        for key, value in attributes.items():
            if value is not None:
                span.set_attribute(key, value)


def add_span_event(name: str, attributes: Dict[str, Any] = None) -> None:
    """
    Add an event to the current active span.
    
    Events are timestamped messages that provide additional context
    about what happened during the span's lifetime.
    
    Args:
        name: Event name (e.g., "cache_miss", "retry_attempted")
        attributes: Optional dict of event attributes
    
    Usage:
        add_span_event("retrieval_completed", {"doc_count": 5, "ndcg": 0.85})
    """
    span = trace.get_current_span()
    if span and span.is_recording():
        span.add_event(name, attributes=attributes or {})


def set_span_error(exception: Exception, message: str = None) -> None:
    """
    Mark the current span as errored.
    
    Args:
        exception: The exception that occurred
        message: Optional error message
    """
    span = trace.get_current_span()
    if span and span.is_recording():
        span.set_status(Status(StatusCode.ERROR, message or str(exception)))
        span.record_exception(exception)


@contextmanager
def create_span(
    name: str,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: Dict[str, Any] = None
):
    """
    Context manager for creating a child span.
    
    Args:
        name: Span name
        kind: Span kind (INTERNAL, SERVER, CLIENT, PRODUCER, CONSUMER)
        attributes: Initial attributes
    
    Usage:
        with create_span("retrieval.search", attributes={"query": query}):
            # ... do work
            add_span_event("search_completed", {"doc_count": 5})
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(
        name,
        kind=kind,
        attributes=attributes or {}
    ) as span:
        try:
            yield span
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


def traced(
    name: str = None,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: Dict[str, Any] = None
):
    """
    Decorator for tracing async functions.
    
    Args:
        name: Span name (defaults to function name)
        kind: Span kind
        attributes: Static attributes to add
    
    Usage:
        @traced("retrieval.search")
        async def search_documents(query: str):
            ...
    """
    def decorator(func: Callable):
        span_name = name or f"{func.__module__}.{func.__name__}"
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(
                span_name,
                kind=kind,
                attributes=attributes or {}
            ) as span:
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    span.set_attribute("duration_ms", (time.time() - start_time) * 1000)
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    span.set_attribute("error.type", type(e).__name__)
                    raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(
                span_name,
                kind=kind,
                attributes=attributes or {}
            ) as span:
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    span.set_attribute("duration_ms", (time.time() - start_time) * 1000)
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    span.set_attribute("error.type", type(e).__name__)
                    raise
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# =============================================================================
# Pre-defined span helpers for VESPER pipeline stages
# =============================================================================

@contextmanager
def trace_retrieval(query: str, tenant_id: str, search_type: str = "hybrid"):
    """Trace retrieval stage."""
    with create_span(
        "retrieval.search",
        attributes={
            "vesper.query": query[:100],  # Truncate for privacy
            "vesper.tenant_id": tenant_id,
            "vesper.search_type": search_type,
        }
    ) as span:
        yield span


@contextmanager
def trace_rerank(model: str, doc_count: int):
    """Trace reranking stage."""
    with create_span(
        "rerank.score",
        attributes={
            "vesper.rerank_model": model,
            "vesper.doc_count": doc_count,
        }
    ) as span:
        yield span


@contextmanager
def trace_router(query_complexity: str = "medium"):
    """Trace model routing stage."""
    with create_span(
        "router.route",
        attributes={
            "vesper.query_complexity": query_complexity,
        }
    ) as span:
        yield span


@contextmanager
def trace_llm_generate(model: str, max_tokens: int, temperature: float):
    """Trace LLM generation stage."""
    with create_span(
        "llm.generate",
        kind=SpanKind.CLIENT,
        attributes={
            "vesper.model": model,
            "vesper.max_tokens": max_tokens,
            "vesper.temperature": temperature,
        }
    ) as span:
        yield span


@contextmanager
def trace_guardrails(stage: str, checks: list):
    """Trace guardrails stage."""
    with create_span(
        f"guardrails.{stage}_process",
        attributes={
            "vesper.guardrails_stage": stage,
            "vesper.guardrails_checks": ",".join(checks),
        }
    ) as span:
        yield span
