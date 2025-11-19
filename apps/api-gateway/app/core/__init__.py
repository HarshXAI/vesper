"""Core package."""

from .config import settings
from .metrics import MetricsCollector, get_metrics, get_metrics_content_type
from .tracing import (
    get_trace_headers,
    get_current_trace_id,
    get_current_span_id,
    add_span_attributes,
    add_span_event
)

__all__ = [
    "settings",
    "MetricsCollector",
    "get_metrics",
    "get_metrics_content_type",
    "get_trace_headers",
    "get_current_trace_id",
    "get_current_span_id",
    "add_span_attributes",
    "add_span_event"
]
