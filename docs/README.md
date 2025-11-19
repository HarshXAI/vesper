# VESPER Documentation

Comprehensive documentation for the VESPER platform.

## Contents

- [Architecture](architecture/) - System design and architecture decisions
- [API Reference](api/) - API documentation
- [Deployment](deployment/) - Deployment guides
- [Operations](operations/) - Runbooks and operational procedures
- [Development](development/) - Development guides
- [ADRs](adr/) - Architecture Decision Records

## Quick Links

### For Developers

- [Getting Started](development/getting-started.md)
- [Contributing Guide](../CONTRIBUTING.md)
- [Code Style Guide](development/code-style.md)
- [Testing Guide](development/testing.md)

### For Operators

- [Deployment Guide](deployment/README.md)
- [Monitoring Guide](operations/monitoring.md)
- [Troubleshooting](operations/troubleshooting.md)
- [Incident Response](operations/incident-response.md)

### For Architects

- [System Architecture](architecture/system-overview.md)
- [Data Flow](architecture/data-flow.md)
- [Security Architecture](architecture/security.md)
- [ADRs](adr/)

## Architecture Overview

VESPER is a production-grade AI platform built on AWS with seven core layers:

1. **Data Layer** - Medallion architecture (Bronze/Silver/Gold) on S3
2. **Retrieval Layer** - Hybrid semantic search with PostgreSQL + pgvector
3. **Reasoning Layer** - Multi-agent LLM system with model routing
4. **Safety Layer** - Guardrails and policy enforcement
5. **Monitoring Layer** - Self-healing observability
6. **Infrastructure Layer** - Event-driven serving on Kubernetes
7. **UI Layer** - Analyst chat interface and Ops dashboard

## Key Features

- **Evidence-First**: Every answer includes citations and provenance
- **Self-Healing**: Automated drift detection and remediation
- **Hybrid Search**: Combines semantic and keyword search with reranking
- **Multi-Agent**: Specialized agents with controlled orchestration
- **Production-Ready**: Monitoring, logging, tracing, and alerting
- **Open Source First**: Built on open-source tools and frameworks

## Technology Stack

### Infrastructure

- **Cloud**: AWS (EKS, S3, RDS, MSK, ElastiCache)
- **IaC**: Terraform
- **Orchestration**: Kubernetes + Airflow

### Backend

- **Languages**: Python 3.11+
- **Frameworks**: FastAPI, LangChain, LangGraph
- **Database**: PostgreSQL 15 with pgvector
- **Cache**: Redis
- **Streaming**: Kafka (MSK)

### Frontend

- **Framework**: Next.js 14+ (React, TypeScript)
- **Styling**: Tailwind CSS

### ML/AI

- **LLMs**: OpenAI GPT-4, Llama 2/3, Mistral
- **Embeddings**: OpenAI Ada, Sentence Transformers
- **Tracking**: MLflow
- **Guardrails**: NeMo Guardrails

### Monitoring

- **Metrics**: Prometheus + Grafana
- **Tracing**: OpenTelemetry + Jaeger
- **Logging**: CloudWatch / ELK

## Support

- GitHub Issues for bugs and feature requests
- GitHub Discussions for questions
- See [CONTRIBUTING.md](../CONTRIBUTING.md) for contribution guidelines
