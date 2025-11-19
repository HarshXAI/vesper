"""OpenTelemetry tracing utilities for context propagation."""

from typing import Dict
from opentelemetry import trace
from opentelemetry.propagate import inject


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


def add_span_attributes(attributes: Dict[str, any]) -> None:
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
            span.set_attribute(key, value)


def add_span_event(name: str, attributes: Dict[str, any] = None) -> None:
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
