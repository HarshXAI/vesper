# VESPER - Quick Start

## 🚀 Get Started in 3 Minutes

### 1. Prerequisites Check

```bash
docker --version    # Need 20.10+
python --version    # Need 3.11+
```

### 2. Setup & Start

```bash
# Clone (if not already)
cd vesper

# Setup environment
make setup

# Start all services
make start

# Verify everything is running
make health
```

### 3. Access Services

Open these in your browser:

| Service           | URL                   | Credentials             |
| ----------------- | --------------------- | ----------------------- |
| **Airflow**       | http://localhost:8080 | admin / admin           |
| **Grafana**       | http://localhost:3003 | admin / admin           |
| **MinIO Console** | http://localhost:9001 | minioadmin / minioadmin |
| **MLflow**        | http://localhost:5000 | -                       |
| **Prometheus**    | http://localhost:9090 | -                       |

## 📋 Common Commands

```bash
make help           # Show all commands
make start          # Start services
make stop           # Stop services
make logs           # View all logs
make logs-postgres  # View specific service logs
make test           # Run tests
make clean          # Clean everything
```

## 🏗️ Project Structure

```
vesper/
├── services/           # Microservices (Python)
├── frontends/          # UIs (Next.js)
├── infrastructure/     # Terraform (AWS)
├── orchestration/      # Airflow DAGs
├── shared/             # Common libraries
├── docs/               # Documentation
├── scripts/            # Automation scripts
└── docker-compose.yml  # Local development
```

## 🎯 Current Phase

**Phase 0: Foundation Setup** ✅ COMPLETE

**Next: Phase 1 - Data Ingestion** (Weeks 1-8)

- Build SEC EDGAR connector
- Implement Bronze → Silver → Gold pipeline
- Set up Airflow orchestration

## 📚 Documentation

- [SETUP.md](SETUP.md) - Detailed setup guide
- [CONTRIBUTING.md](CONTRIBUTING.md) - Development guidelines
- [PROJECT_STATUS.md](PROJECT_STATUS.md) - Current status
- [docs/](docs/) - Full documentation

## 🆘 Troubleshooting

### Services won't start?

```bash
docker-compose down -v
docker system prune -f
make start
```

### Port conflicts?

```bash
# Check what's using port 5432 (example)
lsof -i :5432
```

### Need to reset database?

```bash
make clean
make start
```

## 🎓 Learning Path

1. ✅ **Foundation** (You are here)

   - Docker & orchestration
   - Infrastructure as code
   - DevOps best practices

2. ⏳ **Data Engineering** (Next)

   - Medallion architecture
   - Data pipelines
   - Airflow orchestration

3. ⏳ **AI/ML**

   - RAG implementation
   - Vector databases
   - LLM integration

4. ⏳ **Production Systems**
   - Monitoring & observability
   - Self-healing systems
   - Production deployment

## 🔗 Key Technologies

| Layer             | Technology              |
| ----------------- | ----------------------- |
| **Cloud**         | AWS (EKS, S3, RDS, MSK) |
| **Container**     | Docker, Kubernetes      |
| **IaC**           | Terraform               |
| **Backend**       | Python, FastAPI         |
| **Database**      | PostgreSQL + pgvector   |
| **Queue**         | Kafka (Redpanda)        |
| **Orchestration** | Airflow                 |
| **Monitoring**    | Prometheus + Grafana    |
| **ML**            | LangChain, MLflow       |
| **Frontend**      | Next.js, React          |

## 💡 Pro Tips

- Use `make` commands for convenience
- Check `make help` for all available commands
- Review `.env` for configuration options
- Services run in Docker - no local Python env needed for services
- All scripts are in `scripts/` directory
- Documentation is in `docs/` directory

## 🎯 Success Checklist

Phase 0 (Foundation):

- [x] Project structure created
- [x] Docker Compose configured
- [x] All services starting successfully
- [x] Documentation comprehensive
- [x] CI/CD pipeline configured
- [x] Infrastructure code ready

**Status**: 🟢 Ready for Phase 1!

---

**Questions?** See [SETUP.md](SETUP.md) for detailed instructions or [docs/](docs/) for architecture details.

**Ready to code?**

```bash
make start && make health
```

Let's build VESPER! 🚀
