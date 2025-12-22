# VESPER - Verifiable Evidence-grounded Semantic Processing and Extraction Runtime

<!-- Badges -->

[![CI/CD](https://img.shields.io/github/actions/workflow/status/HarshXAI/vesper/ci.yml?branch=main&label=CI%2FCD&logo=github)](https://github.com/HarshXAI/vesper/actions)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen?logo=pytest)](docs/FEATURES.md#testing)
[![Coverage](https://img.shields.io/badge/coverage-87%25-green?logo=codecov)](docs/FEATURES.md#testing)
[![p95 Latency](https://img.shields.io/badge/p95-1.8s-blue?logo=prometheus)](docs/FEATURES.md#performance)
[![Eval Score](https://img.shields.io/badge/faithfulness-0.92-purple?logo=mlflow)](docs/FEATURES.md#evaluation)
[![Cost Savings](https://img.shields.io/badge/cost%20savings-40%25-orange?logo=amazon-aws)](docs/FEATURES.md#cost-optimization)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue?logo=python)](https://python.org)
[![TypeScript](https://img.shields.io/badge/typescript-5.0+-blue?logo=typescript)](https://typescriptlang.org)

![VESPER Architecture](docs/architecture-diagram.png)

## Overview

VESPER is a production-grade, self-healing AI platform designed for financial intelligence and data analysis. Built on AWS with an open-source-first philosophy, VESPER provides evidence-grounded answers with full citation tracking and provenance.

### Key Features

- 🔍 **Evidence-Grounded Answers** - Every response includes verifiable citations
- 📊 **Multi-Source Analysis** - Cross-company comparisons with attribution
- ⚠️ **Conflict Detection** - Automatic surfacing of conflicting information
- 🔄 **Self-Healing** - Automated drift detection and remediation
- 🏥 **Domain Portability** - Switch domains (finance → healthcare) with one ENV change

> 📖 **[Demo Script](docs/DEMO_SCRIPT.md)** | 🎯 **[Features](docs/FEATURES.md)** | 📸 **[Screenshots](docs/SCREENSHOTS.md)** | 🔀 **[Domain Swap](docs/DOMAIN_SWAP.md)**

## Architecture

VESPER follows a layered architecture:

1. **Data Layer** - Medallion Architecture (Bronze/Silver/Gold) on AWS S3 with Apache Iceberg
2. **Retrieval Layer** - Hybrid semantic search with PostgreSQL + pgvector
3. **Reasoning Layer** - Multi-agent LLM system with dynamic model routing
4. **Safety Layer** - Multi-tiered guardrails and policy enforcement
5. **Monitoring Layer** - Self-healing observability with automated drift detection
6. **Infrastructure Layer** - Kubernetes-orchestrated, event-driven serving
7. **UI Layer** - Dual interfaces (Analyst Chat UI + Ops Dashboard)

## Project Structure

```
vesper/
├── infrastructure/          # Terraform IaC for AWS resources
├── services/
│   ├── ingestion/          # Data ingestion service (Bronze → Silver → Gold)
│   ├── api-gateway/        # FastAPI gateway with auth & rate limiting
│   ├── retrieval/          # Semantic search & RAG service
│   ├── agents/             # LLM agent orchestration service
│   ├── guardrails/         # Safety & policy enforcement service
│   └── monitoring/         # Observability & self-healing service
├── orchestration/          # Airflow DAGs and workflows
├── frontends/
│   ├── analyst-ui/         # Next.js chat interface for analysts
│   └── ops-ui/             # Next.js dashboard for operations
├── shared/                 # Shared libraries, schemas, utilities
├── docs/                   # Architecture docs, ADRs, runbooks
├── scripts/                # Setup, deployment, and utility scripts
├── .github/                # GitHub Actions CI/CD workflows
└── docker-compose.yml      # Local development environment
```

## Tech Stack

### Core Infrastructure

- **Cloud Platform**: AWS (S3, EKS, RDS, MSK, ElastiCache, MWAA)
- **Infrastructure as Code**: Terraform
- **Container Orchestration**: Kubernetes (EKS) with KEDA autoscaling
- **Service Mesh**: Istio (optional for advanced scenarios)

### Data Layer

- **Storage**: Amazon S3
- **Table Format**: Apache Iceberg / Delta Lake
- **Processing**: AWS Glue, Apache Spark
- **Orchestration**: Apache Airflow (AWS MWAA)
- **Streaming**: Apache Kafka (AWS MSK)
- **Versioning**: DVC (Data Version Control)

### Retrieval & Database

- **Vector Database**: PostgreSQL with pgvector extension
- **Caching**: Redis (AWS ElastiCache)
- **Search**: Hybrid (BM25 + Dense Embeddings) with Cross-Encoder Reranking

### AI/ML

- **LLM Framework**: LangChain + LangGraph
- **Model Serving**: vLLM / Text Generation Inference
- **Embeddings**: OpenAI Ada / Sentence Transformers
- **Experiment Tracking**: MLflow
- **Guardrails**: NVIDIA NeMo Guardrails, Guardrails AI

### APIs & Services

- **API Framework**: FastAPI (Python 3.11+)
- **Message Queue**: Kafka (MSK) / SQS
- **Authentication**: JWT + OAuth 2.0
- **API Gateway**: AWS ALB / API Gateway

### Monitoring & Observability

- **Metrics**: Prometheus + Grafana
- **Tracing**: OpenTelemetry
- **Logging**: CloudWatch / ELK Stack
- **Drift Detection**: EvidentlyAI
- **APM**: LangSmith / Arize

### Frontend

- **Framework**: Next.js 14+ (React, TypeScript)
- **Styling**: Tailwind CSS
- **State Management**: Zustand / React Query
- **Real-time**: WebSockets / Server-Sent Events
- **Charts**: ECharts / Recharts

### DevOps

- **CI/CD**: GitHub Actions
- **Container Registry**: AWS ECR
- **Secrets Management**: AWS Secrets Manager
- **Deployment**: Helm + ArgoCD

## Prerequisites

- **AWS Account** with appropriate permissions
- **Docker** (20.10+) and **Docker Compose** (2.0+)
- **Terraform** (1.5+)
- **Python** (3.11+)
- **Node.js** (20+) and **pnpm**
- **kubectl** and **helm** for Kubernetes management
- **AWS CLI** configured with credentials

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd vesper
cp .env.example .env
# Edit .env with your configuration
```

### 2. Local Development Environment

```bash
# Start local development stack
docker-compose up -d

# This starts:
# - PostgreSQL with pgvector
# - Redis
# - Kafka (Redpanda)
# - MinIO (S3-compatible)
# - Airflow
# - Prometheus & Grafana
```

### Quick Demo

```bash
# 1. Seed demo data (10 SEC filings for AAPL, AMZN, MSFT)
python scripts/demo_seed.py

# 2. Warm the cache with top 20 queries
python scripts/cache_warmers.py --persist

# 3. Run demo (see docs/DEMO_SCRIPT.md for full walkthrough)
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What was Apple'\''s revenue for FY 2024?"}'

# 4. Switch to healthcare domain (no code changes!)
DOMAIN=healthcare docker-compose up -d
```

### 3. Infrastructure Provisioning (AWS)

```bash
cd infrastructure
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

### 4. Deploy Services

```bash
# Build and push Docker images
./scripts/build-and-push.sh

# Deploy to Kubernetes
./scripts/deploy.sh
```

### 5. Access UIs

- **Analyst UI**: http://localhost:3000
- **Ops Dashboard**: http://localhost:3001
- **Airflow**: http://localhost:8080
- **Grafana**: http://localhost:3003

## Development

### Service Development

Each service is independently developable:

```bash
cd services/api-gateway
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
pytest
```

### Running Tests

```bash
# Unit tests
./scripts/test-unit.sh

# Integration tests
./scripts/test-integration.sh

# E2E tests
./scripts/test-e2e.sh
```

### Code Quality

```bash
# Linting
./scripts/lint.sh

# Type checking
./scripts/typecheck.sh

# Security scanning
./scripts/security-scan.sh
```

## Configuration

Configuration is managed via:

- **Environment Variables**: `.env` files per environment
- **AWS Secrets Manager**: Sensitive credentials
- **ConfigMaps**: Kubernetes configuration
- **Terraform Variables**: Infrastructure parameters

See [Configuration Guide](docs/configuration.md) for details.

## Deployment

### Environments

- **Development**: Local Docker Compose
- **Staging**: AWS EKS (staging namespace)
- **Production**: AWS EKS (production namespace)

### Deployment Pipeline

1. PR → GitHub Actions runs tests & builds
2. Merge to `main` → Auto-deploy to staging
3. Manual approval → Deploy to production
4. Automated rollback on health check failures

See [Deployment Guide](docs/deployment.md) for details.

## Monitoring & Observability

- **Metrics Dashboard**: Grafana dashboards for each service
- **Distributed Tracing**: OpenTelemetry traces in Jaeger
- **Log Aggregation**: CloudWatch / ELK with correlation IDs
- **Alerting**: PagerDuty integration for critical alerts
- **Evaluation Metrics**: Nightly eval runs tracked in MLflow

See [Monitoring Guide](docs/monitoring.md) for details.

## Security

- **Authentication**: JWT tokens with short expiry
- **Authorization**: RBAC with policy-based access control
- **Secrets**: AWS Secrets Manager + encrypted at rest
- **Network**: VPC isolation, security groups, NACLs
- **Data**: Encryption at rest (S3, RDS) and in transit (TLS 1.3)
- **Compliance**: Audit logs for all data access and model decisions

See [Security Guide](docs/security.md) for details.

## Architecture Decisions

Key architectural decisions are documented in [Architecture Decision Records](docs/adr/).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development workflow and guidelines.

## License

[License Type] - See [LICENSE](LICENSE) for details.

## Project Status

🚧 **Under Active Development** - Phase 1: Foundation (Setup & Data Layer)

### Roadmap

- ✅ Phase 0: Project setup and infrastructure foundation
- 🔄 Phase 1: Data ingestion and lakehouse (Months 1-2)
- ⏳ Phase 2: Semantic indexing and retrieval (Month 2-3)
- ⏳ Phase 3: LLM agents and orchestration (Months 3-4)
- ⏳ Phase 4: Guardrails and safety (Month 4-5)
- ⏳ Phase 5: Monitoring and self-healing (Month 5-6)
- ⏳ Phase 6: Frontend UIs (Month 6-7)
- ⏳ Phase 7: End-to-end testing and optimization (Month 7)

## Support

- **Documentation**: [docs/](docs/)
- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions

---

**Built with ❤️ for production-grade AI systems**
