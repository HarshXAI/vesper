# Vesper API Gateway

Production FastAPI service for financial document Q&A with streaming responses and citations.

## Project Structure

```
api-gateway/
├── app/
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py          # API route handlers
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py          # Settings and configuration
│   ├── middleware/
│   │   ├── __init__.py
│   │   └── guardrails.py      # Guardrails middleware
│   └── models/
│       ├── __init__.py
│       └── __init__.py        # Pydantic models
├── tests/
│   ├── __init__.py
│   ├── test_guardrails.py     # Guardrails tests
│   └── test_integration.py    # Integration tests
├── main.py                     # Application entry point
├── Dockerfile                  # Container definition
├── pyproject.toml             # Project metadata
├── requirements.txt           # Dependencies
└── README.md                  # This file
```

## Features

- **POST /v1/ask**: Query endpoint with Server-Sent Events (SSE) streaming
- **GET /v1/evals**: List evaluation runs from MLflow
- **GET /v1/evals/metrics**: Aggregated eval metrics (faithfulness, latency, error rates)
- **GET /health**: Health checks for DB, Redis, and Agents worker
- **GET /metrics**: Prometheus metrics export
- **Guardrails**: Pre/post-processing for safety and compliance
- **Modular Architecture**: Clean separation of concerns

## Quick Start

### Installation

```bash
cd apps/api-gateway

# Using uv (recommended - 10-100x faster)
uv pip install -r requirements.txt

# Or using pip
pip install -r requirements.txt
```

### Run Locally

```bash
python main.py
```

Server starts at http://localhost:8000

### Run with Docker

```bash
docker-compose up api-gateway
```

## API Usage

### Query with Streaming

```bash
curl -X POST http://localhost:8000/v1/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What was Apple revenue in Q3 2023?",
    "tenant_id": "demo",
    "stream": true
  }'
```

Response (SSE format):

```
data: {"type": "token", "content": "Apple"}
data: {"type": "token", "content": "'s"}
data: {"type": "token", "content": " revenue"}
data: {"type": "citation", "citations": [{"source_uri": "s3://...", "page": 12, "span": {...}, "sha256": "..."}]}
data: {"type": "done", "latency_ms": 850, "cost_usd": 0.012}
```

### Health Check

```bash
curl http://localhost:8000/health
```

Response:

```json
{
  "status": "healthy",
  "checks": {
    "database": { "status": "healthy", "latency_ms": 5.2 },
    "redis": { "status": "healthy", "latency_ms": 1.1 },
    "agents": { "status": "healthy", "latency_ms": 12.3 }
  },
  "timestamp": "2025-10-31T12:34:56"
}
```

### Metrics

```bash
curl http://localhost:8000/metrics
```

### Evaluation Endpoints

List evaluation runs:

```bash
curl http://localhost:8000/v1/evals
```

Response:

```json
{
  "runs": [
    {
      "run_id": "abc123",
      "run_name": "nightly-2024-01-15",
      "status": "FINISHED",
      "metrics": { "faithfulness": 0.92, "hallucination_rate": 0.03 }
    }
  ],
  "total": 1,
  "experiment_name": "vesper-nightly-eval"
}
```

Get aggregated metrics:

```bash
curl http://localhost:8000/v1/evals/metrics
```

Response:

```json
{
  "faithfulness": 0.92,
  "hallucination_rate": 0.03,
  "p95_latency_ms": 250.5,
  "p99_latency_ms": 450.2,
  "error_rate_5xx": 0.001,
  "total_runs": 10
}
```

### SSE Stream with curl

For proper SSE streaming, use `-N` to disable buffering:

```bash
curl -N -X POST http://localhost:8000/v1/ask \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{"query": "What is Apple revenue?", "tenant_id": "demo", "stream": true}'
```

### SSE Stream with Python

```python
import httpx

async def stream_query():
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            "http://localhost:8000/v1/ask",
            json={"query": "What is Apple revenue?", "tenant_id": "demo", "stream": True}
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    print(line[5:])
```

### SSE Stream with JavaScript

```javascript
const response = await fetch("http://localhost:8000/v1/ask", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    query: "What is Apple revenue?",
    tenant_id: "demo",
    stream: true,
  }),
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  console.log(decoder.decode(value));
}
```

## Architecture

```
Request → Guardrails (pre) → LangGraph Agents → Guardrails (post) → Stream Response
```

### Request Flow

1. **Input Validation**: Check query length, format, detect jailbreaks
2. **Policy Check**: Verify tenant permissions, rate limits
3. **Agent Execution**:
   - Retrieve relevant documents (hybrid search)
   - Rerank results
   - Route to appropriate LLM
   - Generate response with citations
4. **Output Moderation**: PII redaction, toxicity filtering
5. **Citation Verification**: Validate hashes, check coverage
6. **Stream Response**: Send tokens + citations via SSE

## Configuration

Environment variables:

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/vesper

# Redis
REDIS_URL=redis://localhost:6379/0

# Agents Worker
AGENTS_WORKER_URL=http://localhost:8001

# API
API_PORT=8000
API_WORKERS=4

# Limits
MAX_QUERY_LENGTH=500
STREAM_TIMEOUT_SEC=120
```

## Development Status

**Current**: PR#201 - API Gateway Skeleton ✅

**Next Steps**:

- PR#202: Guardrails integration middleware
- PR#203: Prometheus metrics instrumentation
- PR#205: OpenTelemetry tracing

## Testing

```bash
# Unit tests
pytest tests/

# Integration test
python test_integration.py

# Load test
locust -f locustfile.py
```

## Deployment

See `infrastructure/terraform/modules/api-gateway/` for AWS ECS deployment.

Target metrics:

- P95 latency: <1200ms (cached), <2500ms (cold)
- Stream startup: <300ms
- Guardrails overhead: <50ms
- Availability: 99.9%
