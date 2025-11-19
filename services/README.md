# VESPER Services

This directory contains all microservices that make up the VESPER platform.

## Service Architecture

```
services/
├── ingestion/          # Data ingestion service (Bronze layer)
├── api-gateway/        # FastAPI gateway with auth & routing
├── retrieval/          # Semantic search & RAG service
├── agents/             # LLM agent orchestration
├── guardrails/         # Safety & policy enforcement
└── monitoring/         # Self-healing & observability
```

## Service Communication

Services communicate via:

- **Synchronous**: REST APIs (internal service-to-service)
- **Asynchronous**: Kafka topics for event streaming
- **State Management**: PostgreSQL for persistence
- **Caching**: Redis for performance

## Development

Each service is independently developable:

```bash
cd services/<service-name>
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
pytest
```

## Service Standards

All services follow these standards:

### Structure

```
service-name/
├── src/
│   └── vesper_{service}/
│       ├── __init__.py
│       ├── main.py           # Entry point
│       ├── api/              # API endpoints (if applicable)
│       ├── core/             # Business logic
│       ├── models/           # Data models
│       └── config.py         # Configuration
├── tests/
│   ├── unit/
│   ├── integration/
│   └── conftest.py
├── Dockerfile
├── requirements.txt
├── pyproject.toml
├── pytest.ini
└── README.md
```

### Configuration

- Environment-based configuration
- Pydantic settings for validation
- Secrets from AWS Secrets Manager (production)

### Logging

- Structured JSON logging
- Correlation IDs for tracing
- OpenTelemetry instrumentation

### Health Checks

- `/health` - Liveness probe
- `/ready` - Readiness probe
- `/metrics` - Prometheus metrics

### Error Handling

- Consistent error response format
- Appropriate HTTP status codes
- Error tracking and alerting

### Testing

- Unit tests: >80% coverage
- Integration tests for external dependencies
- Contract tests for APIs

## Deployment

Services are deployed as:

- **Development**: Docker Compose
- **Staging/Production**: Kubernetes (EKS)

Deployment process:

1. Build Docker image
2. Push to ECR
3. Update Kubernetes manifests
4. Rolling update with health checks

## Monitoring

All services emit:

- **Metrics**: Prometheus format at `/metrics`
- **Logs**: JSON to stdout (CloudWatch)
- **Traces**: OpenTelemetry to Jaeger/X-Ray
- **Custom Events**: To Kafka for analytics
