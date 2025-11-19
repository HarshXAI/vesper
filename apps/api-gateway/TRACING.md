# OpenTelemetry Tracing - Developer Guide

## Overview

Vesper API Gateway is instrumented with OpenTelemetry for distributed tracing. Traces capture the complete lifecycle of requests from ingress through retrieval, reranking, routing, and generation.

## Architecture

```
Request → API Gateway → Guardrails → LangGraph Agent → Retrieval → Rerank → Router → LLM
    ↓           ↓            ↓              ↓             ↓          ↓        ↓       ↓
  Trace ID propagates through entire pipeline via W3C Trace Context headers
```

## Span Hierarchy

```
POST /v1/ask                          [Root span, auto-instrumented by FastAPI]
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
```

## Accessing Traces

### Jaeger UI

1. **Start services**: `docker-compose up -d`
2. **Open Jaeger**: http://localhost:16686
3. **Select service**: `api-gateway`
4. **Find traces**: Search by operation, tags, or time range

### Key Features

- **Service map**: Visualize dependencies between services
- **Latency distribution**: P50/P95/P99 by operation
- **Error traces**: Filter by `error=true` tag
- **Trace comparison**: Compare slow vs fast requests

## Using Tracing in Code

### Automatic Instrumentation

FastAPI routes are automatically instrumented:

```python
@app.post("/v1/ask")  # Root span created automatically
async def ask(request: AskRequest):
    # Current span is active
    pass
```

### Creating Child Spans

```python
from opentelemetry import trace

tracer = trace.get_tracer("api-gateway")

with tracer.start_as_current_span("operation_name") as span:
    # Add attributes
    span.set_attribute("user_id", "user-123")
    span.set_attribute("query_length", 45)

    # Do work
    result = await some_operation()

    # Add events
    span.add_event("cache_miss", {"key": "user-123"})
```

### Helper Functions

```python
from app.core import (
    get_trace_headers,      # Get W3C headers for downstream calls
    get_current_trace_id,   # Get trace ID as hex string
    add_span_attributes,    # Add attributes to current span
    add_span_event          # Add event to current span
)

# Propagate trace to downstream service
headers = get_trace_headers()
response = await httpx.get(agents_url, headers=headers)

# Add custom attributes
add_span_attributes({
    "tenant_id": "acme-corp",
    "cache_hit": True,
    "doc_count": 5
})

# Add events for key milestones
add_span_event("retrieval_completed", {"ndcg": 0.85})
```

## Trace Context Propagation

### HTTP Headers

Traces propagate via W3C Trace Context headers:

```
traceparent: 00-{trace-id}-{span-id}-{flags}
tracestate: key1=value1,key2=value2
```

Example:

```
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
```

### Async Operations

Trace context automatically propagates through async/await:

```python
async def parent():
    with tracer.start_as_current_span("parent"):
        result = await child()  # Trace context preserved

async def child():
    # Same trace ID, new span ID
    trace_id = get_current_trace_id()
    add_span_attributes({"operation": "child"})
```

## Best Practices

### 1. Meaningful Span Names

✅ Good:

```python
with tracer.start_as_current_span("retrieval.pgvector_search"):
with tracer.start_as_current_span("rerank.cross_encoder"):
```

❌ Bad:

```python
with tracer.start_as_current_span("function1"):
with tracer.start_as_current_span("step"):
```

### 2. Rich Attributes

✅ Good:

```python
span.set_attribute("query_length", len(query))
span.set_attribute("tenant_id", tenant_id)
span.set_attribute("cache_hit", True)
span.set_attribute("doc_count", len(docs))
span.set_attribute("ndcg_score", 0.85)
```

❌ Bad:

```python
span.set_attribute("data", str(data))  # Too much data
span.set_attribute("result", "success")  # Not specific
```

### 3. Events for Milestones

Use events to mark important points in time:

```python
add_span_event("cache_miss", {"key": cache_key})
add_span_event("retry_attempted", {"attempt": 2, "reason": "timeout"})
add_span_event("fallback_triggered", {"original_model": "gpt-4", "fallback": "gpt-3.5"})
```

### 4. Error Recording

```python
try:
    result = await operation()
except Exception as e:
    span = trace.get_current_span()
    span.record_exception(e)
    span.set_status(Status(StatusCode.ERROR, str(e)))
    raise
```

## Configuration

### Environment Variables

```bash
# OTLP gRPC endpoint (Jaeger)
OTEL_EXPORTER_ENDPOINT=http://jaeger:4317

# Console exporter for local dev (if not set)
# OTEL_EXPORTER_ENDPOINT=  # Empty = console output
```

### Sampling

All traces are sampled at 100% by default. For production with high volume:

```python
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

# Sample 10% of traces
sampler = TraceIdRatioBased(0.1)
provider = TracerProvider(sampler=sampler)
```

## Querying Traces

### Common Queries

**Find slow requests:**

```
service=api-gateway AND duration > 2s
```

**Find errors:**

```
service=api-gateway AND error=true
```

**Find specific tenant:**

```
service=api-gateway AND tenant_id=acme-corp
```

**Find guardrails blocks:**

```
service=api-gateway AND guardrails.blocked=true
```

**Find cache misses:**

```
service=api-gateway AND cache_hit=false
```

## Metrics vs Traces vs Logs

| Feature         | Metrics            | Traces                        | Logs                           |
| --------------- | ------------------ | ----------------------------- | ------------------------------ |
| **Purpose**     | Aggregated stats   | Request flow                  | Discrete events                |
| **Cost**        | Low                | Medium                        | High                           |
| **Cardinality** | Low                | High                          | Highest                        |
| **Use Case**    | Dashboards, alerts | Debugging, profiling          | Debugging, audit               |
| **Example**     | P95 latency: 1.2s  | Trace shows rerank took 800ms | "User X query failed: timeout" |

**Rule of thumb:**

- **Metrics**: Monitor overall health (dashboards, alerts)
- **Traces**: Debug specific slow/failed requests
- **Logs**: Understand individual events

## Performance Impact

- **Overhead**: ~1-2% latency overhead
- **Sampling**: Use sampling in production to reduce costs
- **Storage**: Traces stored in Jaeger (in-memory by default)

## Troubleshooting

### Traces not appearing in Jaeger

1. Check Jaeger is running: `docker ps | grep jaeger`
2. Check endpoint: `curl http://localhost:16686`
3. Verify OTEL_EXPORTER_ENDPOINT env var
4. Check API Gateway logs for trace exports

### Missing spans

1. Ensure spans are started within parent span context
2. Check span isn't closed before child spans finish
3. Verify trace context propagated via `get_trace_headers()`

### High cardinality attributes

Avoid high-cardinality values in span attributes:

- ❌ User IDs (millions of unique values)
- ❌ Request IDs
- ❌ Timestamps
- ✅ Tenant IDs (hundreds of values)
- ✅ Model names (10-20 values)
- ✅ Boolean flags

## Production Deployment

For production with OTLP collector:

```yaml
# docker-compose.prod.yml
services:
  otel-collector:
    image: otel/opentelemetry-collector:latest
    command: ["--config=/etc/otel-collector-config.yaml"]
    volumes:
      - ./otel-collector-config.yaml:/etc/otel-collector-config.yaml
    ports:
      - "4317:4317" # OTLP gRPC
      - "4318:4318" # OTLP HTTP

  api-gateway:
    environment:
      OTEL_EXPORTER_ENDPOINT: http://otel-collector:4317
```

## Resources

- [OpenTelemetry Python Docs](https://opentelemetry.io/docs/instrumentation/python/)
- [W3C Trace Context](https://www.w3.org/TR/trace-context/)
- [Jaeger Documentation](https://www.jaegertracing.io/docs/)
- [FastAPI Instrumentation](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/fastapi/fastapi.html)
