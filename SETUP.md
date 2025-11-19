# VESPER Setup Guide

Welcome to VESPER! This guide will help you get the development environment up and running.

## Prerequisites

Before you begin, ensure you have the following installed:

### Required

- **Docker** (20.10+): [Install Docker](https://docs.docker.com/get-docker/)
- **Docker Compose** (2.0+): Usually included with Docker Desktop
- **Python** (3.11+): [Install Python](https://www.python.org/downloads/)
- **Git**: [Install Git](https://git-scm.com/downloads)

### Recommended

- **Make**: For convenient command shortcuts (usually pre-installed on macOS/Linux)
- **Node.js** (20+): For frontend development [Install Node.js](https://nodejs.org/)
- **AWS CLI**: For infrastructure management [Install AWS CLI](https://aws.amazon.com/cli/)
- **Terraform** (1.5+): For infrastructure as code [Install Terraform](https://www.terraform.io/downloads)

### Verification

Run these commands to verify your setup:

```bash
docker --version          # Should show 20.10 or higher
docker-compose --version  # Should show 2.0 or higher
python --version          # Should show 3.11 or higher
git --version
make --version            # Optional but recommended
```

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd vesper
```

### 2. Initial Setup

Run the setup script:

```bash
make setup
# OR
./scripts/setup-local.sh
```

This will:

- Create `.env` file from template
- Set up directory structure
- Create database initialization scripts
- Configure Prometheus
- Pull Docker images

### 3. Configure Environment

Edit the `.env` file with your settings:

```bash
# Essential settings to review:
ENVIRONMENT=development
DEBUG=true

# If using OpenAI (optional for now):
OPENAI_API_KEY=your-key-here

# AWS (only needed for cloud deployment):
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=your-account-id
```

### 4. Start Services

```bash
make start
# OR
docker-compose up -d
```

This starts:

- PostgreSQL with pgvector (port 5432)
- Redis cache (port 6379)
- Redpanda/Kafka (port 19092)
- MinIO S3 (port 9000, console 9001)
- Airflow (port 8080)
- Prometheus (port 9090)
- Grafana (port 3003)
- MLflow (port 5000)

### 5. Verify Services

Check that all services are running:

```bash
make health
# OR
docker-compose ps
```

All services should show "Up" status.

### 6. Access UIs

Open these URLs in your browser:

- **Airflow**: http://localhost:8080

  - Username: `admin`
  - Password: `admin`

- **Grafana**: http://localhost:3003

  - Username: `admin`
  - Password: `admin`

- **MinIO Console**: http://localhost:9001

  - Username: `minioadmin`
  - Password: `minioadmin`

- **MLflow**: http://localhost:5000

- **Prometheus**: http://localhost:9090

## Development Workflow

### Working on a Service

1. Navigate to the service directory:

```bash
cd services/ingestion  # Example
```

2. Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
pip install -e ".[dev]"
```

4. Run tests:

```bash
pytest
```

5. Start developing!

### Common Commands

```bash
# Start all services
make start

# Stop all services
make stop

# View logs
make logs
make logs-postgres  # Specific service

# Run tests
make test

# Format code
make format

# Lint code
make lint

# Database access
make db-shell

# Redis access
make redis-cli

# Clean everything
make clean
```

### Making Changes

1. Create a feature branch:

```bash
git checkout -b feature/your-feature-name
```

2. Make your changes and test:

```bash
make test
make lint
```

3. Commit with conventional commit format:

```bash
git commit -m "feat: add new feature"
```

4. Push and create PR:

```bash
git push origin feature/your-feature-name
```

## Troubleshooting

### Port Conflicts

If you get port conflict errors, check what's using the ports:

```bash
# macOS/Linux
lsof -i :5432  # PostgreSQL
lsof -i :6379  # Redis
lsof -i :8080  # Airflow

# Windows
netstat -ano | findstr :5432
```

Kill the conflicting process or change ports in `docker-compose.yml`.

### Docker Issues

If services fail to start:

```bash
# Clean up and restart
docker-compose down -v
docker system prune -f
make start
```

### Permission Issues

If you get permission errors:

```bash
# Make scripts executable
chmod +x scripts/*.sh

# Fix directory permissions
sudo chown -R $USER:$USER .
```

### Database Connection Issues

```bash
# Restart PostgreSQL
docker-compose restart postgres

# Check logs
docker-compose logs postgres

# Verify it's running
docker-compose exec postgres pg_isready -U vesper
```

### Service Won't Start

Check the logs for the specific service:

```bash
docker-compose logs <service-name>
```

Common issues:

- Missing environment variables
- Port conflicts
- Insufficient memory (Docker Desktop settings)

## Next Steps

### Phase 1: Data Ingestion

- [ ] Implement SEC EDGAR connector
- [ ] Set up Bronze layer in S3/MinIO
- [ ] Create Airflow DAG for ingestion
- [ ] Add data validation

### Phase 2: Semantic Indexing

- [ ] Set up pgvector schemas
- [ ] Implement document chunking
- [ ] Add embedding generation
- [ ] Create hybrid search

### Phase 3: LLM Integration

- [ ] Set up model serving
- [ ] Implement retrieval agent
- [ ] Add guardrails
- [ ] Build API gateway

### Phase 4: Frontend

- [ ] Create Analyst UI
- [ ] Build Ops Dashboard
- [ ] Add WebSocket streaming

### Phase 5: Production

- [ ] Set up monitoring
- [ ] Configure CI/CD
- [ ] Deploy to AWS
- [ ] Load testing

## Getting Help

- 📖 **Documentation**: See `docs/` directory
- 💬 **Discussions**: GitHub Discussions
- 🐛 **Issues**: GitHub Issues
- 📝 **Contributing**: See `CONTRIBUTING.md`

## Useful Resources

### Learning Resources

- [LangChain Documentation](https://python.langchain.com/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [PostgreSQL pgvector](https://github.com/pgvector/pgvector)
- [Apache Airflow](https://airflow.apache.org/)

### AWS Resources

- [AWS EKS Best Practices](https://aws.github.io/aws-eks-best-practices/)
- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)

### Architecture References

- See `docs/architecture/` for detailed design docs
- See `docs/adr/` for architecture decisions

---

**Ready to build? Start with:**

```bash
make setup
make start
make health
```

Happy coding! 🚀
