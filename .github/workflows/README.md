# CI/CD Pipeline Documentation

This directory contains GitHub Actions workflows for the VESPER project's CI/CD pipeline.

## Workflows

### 1. CI Pipeline (`ci.yml`)

Runs on every push and pull request to `main` and `develop` branches.

**Jobs:**

- **Python Lint** - Code formatting and style checks (Black, isort, flake8, mypy)
- **Python Tests** - Unit tests for all services (pytest with coverage)
- **Security Scan** - Trivy vulnerability scanning
- **Docker Build** - Build and test Docker images for all services
- **Airflow DAG Validation** - Syntax validation for Airflow DAGs

**Status:** ✅ Required for merge

### 2. CD Pipeline (`cd.yml`)

Runs on:

- Push to `main` branch
- New version tags (`v*.*.*`)
- Manual workflow dispatch

**Jobs:**

- **Build and Push** - Build Docker images and push to GitHub Container Registry (ghcr.io)
- **Create Release Notes** - Auto-generate changelog for tagged releases
- **Notify Deployment** - Deployment status notification

**Container Registry:** `ghcr.io/<owner>/vesper-<service>:<tag>`

### 3. Code Quality (`code-quality.yml`)

Runs on:

- Push/PR to `main` and `develop`
- Weekly schedule (Mondays at 9 AM UTC)

**Jobs:**

- **Format Check** - Black and isort formatting validation
- **Complexity Check** - Code complexity analysis (radon)
- **Dependency Check** - Security vulnerability scanning (safety)
- **Dockerfile Lint** - Dockerfile best practices (hadolint)
- **YAML Lint** - YAML file validation (yamllint)

## Setup

### Prerequisites

1. **GitHub Container Registry (GHCR)**

   - Enabled by default for public/private repos
   - Uses `GITHUB_TOKEN` for authentication (automatic)

2. **Repository Secrets** (if needed for external registries)
   ```
   Settings → Secrets and variables → Actions → New repository secret
   ```

### Enabling CI/CD

1. Push the `.github/workflows/` directory to your repository
2. GitHub Actions will automatically detect and run workflows
3. View workflow runs: `Actions` tab in GitHub repository

## Docker Images

All Docker images are published to GitHub Container Registry with the following naming convention:

```
ghcr.io/<github-username>/vesper-<service>:<tag>
```

**Services:**

- `vesper-ingestion`
- `vesper-processing`
- `vesper-api-gateway`

**Tags:**

- `latest` - Latest build from `main` branch
- `<branch>` - Branch name (e.g., `develop`)
- `<branch>-<sha>` - Branch + commit SHA
- `v1.0.0` - Semantic version tags
- `v1.0` - Major.minor version

## Usage Examples

### Pull Published Image

```bash
# Pull latest image
docker pull ghcr.io/<username>/vesper-api-gateway:latest

# Pull specific version
docker pull ghcr.io/<username>/vesper-api-gateway:v1.0.0

# Pull commit-specific image
docker pull ghcr.io/<username>/vesper-api-gateway:main-abc1234
```

### Manual Workflow Trigger

1. Go to **Actions** tab
2. Select **CD Pipeline - Docker Registry**
3. Click **Run workflow**
4. Select environment (dev/staging/prod)
5. Click **Run workflow**

### Creating a Release

```bash
# Tag a release
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0

# This will:
# 1. Build and push Docker images with v1.0.0 tag
# 2. Generate changelog
# 3. Create GitHub Release
```

## Workflow Status Badges

Add to your README.md:

```markdown
[![CI Pipeline](https://github.com/<username>/vesper/actions/workflows/ci.yml/badge.svg)](https://github.com/<username>/vesper/actions/workflows/ci.yml)
[![CD Pipeline](https://github.com/<username>/vesper/actions/workflows/cd.yml/badge.svg)](https://github.com/<username>/vesper/actions/workflows/cd.yml)
[![Code Quality](https://github.com/<username>/vesper/actions/workflows/code-quality.yml/badge.svg)](https://github.com/<username>/vesper/actions/workflows/code-quality.yml)
```

## Troubleshooting

### CI Failing - Formatting Issues

```bash
# Auto-fix formatting issues locally
make format

# Or manually:
black services/ apps/ scripts/ orchestration/dags/
isort services/ apps/ scripts/ orchestration/dags/
```

### Docker Build Failing

```bash
# Test build locally
cd services/ingestion
docker build -t vesper-ingestion:test .

# Check Dockerfile for issues
hadolint services/ingestion/Dockerfile
```

### GHCR Push Permission Denied

1. Enable package write permissions:
   - Settings → Actions → General
   - Workflow permissions → Read and write permissions
2. Make repository public or authenticate for private images

### Security Vulnerabilities Detected

```bash
# Check locally
pip install safety
safety check -r requirements.txt

# Fix vulnerabilities
pip install --upgrade <package>
```

## Best Practices

1. **Branch Protection**

   - Require CI checks to pass before merge
   - Settings → Branches → Add rule
   - Enable "Require status checks to pass"

2. **Code Review**

   - Require at least 1 reviewer for PRs
   - Enable "Require pull request reviews"

3. **Semantic Versioning**

   - Use `vX.Y.Z` format for releases
   - Major.Minor.Patch versioning

4. **Dependency Updates**
   - Enable Dependabot for automated dependency PRs
   - Settings → Security & analysis → Dependabot

## Monitoring

- **Workflow Runs**: Actions tab → Select workflow
- **Failed Jobs**: Click on job → View logs
- **Security Alerts**: Security tab → Dependabot/Code scanning

## Performance

- **Build Cache**: Uses GitHub Actions cache for faster builds
- **Matrix Builds**: Parallel execution for multiple services
- **Incremental Builds**: Docker BuildKit layer caching

## Future Enhancements

- [ ] Integration tests with test database
- [ ] E2E tests for API endpoints
- [ ] Performance/load testing
- [ ] Kubernetes deployment manifests
- [ ] Terraform plan/apply automation
- [ ] Slack/Discord notifications
- [ ] Deployment to AWS ECS/EKS
