# Contributing to VESPER

Thank you for your interest in contributing to VESPER! This document provides guidelines and instructions for contributing.

## Development Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/<username>/vesper.git
   cd vesper
   ```

2. **Set up the environment**

   ```bash
   make setup
   ```

3. **Start local services**
   ```bash
   make start
   ```

## Code Standards

### Python Code Style

We follow PEP 8 with some modifications:

- Line length: 120 characters
- Use Black for formatting
- Use isort for import sorting
- Type hints where applicable

**Format your code before committing:**

```bash
black services/ apps/ scripts/ orchestration/dags/
isort services/ apps/ scripts/ orchestration/dags/
```

### Git Commit Messages

Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks
- `perf`: Performance improvements
- `ci`: CI/CD changes

**Examples:**

```
feat(ingestion): add support for 10-K filings
fix(api-gateway): resolve RAG streaming segfault
docs(readme): update installation instructions
```

## Pull Request Process

1. **Create a feature branch**

   ```bash
   git checkout -b feat/your-feature-name
   ```

2. **Make your changes**

   - Write clear, documented code
   - Add tests for new functionality
   - Update documentation if needed

3. **Test locally**

   ```bash
   # Run tests
   pytest services/your-service/tests/

   # Check formatting
   black --check services/
   isort --check services/

   # Lint code
   flake8 services/
   ```

4. **Commit your changes**

   ```bash
   git add .
   git commit -m "feat(service): description of changes"
   ```

5. **Push and create PR**

   ```bash
   git push origin feat/your-feature-name
   ```

   Then create a Pull Request on GitHub with:

   - Clear title following commit message convention
   - Detailed description of changes
   - Link to related issues
   - Screenshots/videos if applicable

6. **CI Checks**

   - All CI checks must pass
   - Code review required
   - Address review comments

7. **Merge**
   - Squash and merge is preferred
   - Delete branch after merge

## Testing

### Unit Tests

```bash
# Run all tests
pytest

# Run specific service tests
pytest services/ingestion/tests/

# Run with coverage
pytest --cov=services/ingestion --cov-report=html
```

### Integration Tests

```bash
# Start test environment
docker-compose -f docker-compose.test.yml up -d

# Run integration tests
pytest tests/integration/

# Cleanup
docker-compose -f docker-compose.test.yml down
```

### Manual Testing

```bash
# Start all services
make start

# Test specific endpoints
curl http://localhost:8000/health
curl -X POST http://localhost:8000/v1/ask -d '{"query": "test"}'
```

## Documentation

- Update README.md for user-facing changes
- Update docstrings for API changes
- Add ADRs (Architecture Decision Records) for architectural changes
- Update API documentation in `docs/`

## Project Structure

```
vesper/
├── apps/               # Application services (API Gateway)
├── services/           # Core services (ingestion, processing)
├── orchestration/      # Airflow DAGs
├── infrastructure/     # Terraform IaC
├── monitoring/         # Grafana, Prometheus configs
├── scripts/           # Utility scripts
├── docs/              # Documentation
└── .github/           # CI/CD workflows
```

## Code Review Guidelines

### As a Reviewer

- Be respectful and constructive
- Check for:
  - Code correctness and logic
  - Test coverage
  - Documentation
  - Security vulnerabilities
  - Performance implications
- Approve when ready or request changes with clear feedback

### As an Author

- Respond to feedback professionally
- Make requested changes or explain reasoning
- Keep PRs focused and reasonably sized
- Be patient during review process

## Security

- Never commit secrets, API keys, or credentials
- Use environment variables for sensitive data
- Report security vulnerabilities privately via GitHub Security tab
- Follow security best practices

## Getting Help

- Check existing issues and documentation
- Ask questions in GitHub Discussions
- Join community chat (if available)
- Tag maintainers for urgent issues

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (see LICENSE file).

## Recognition

Contributors will be recognized in:

- CONTRIBUTORS.md file
- Release notes
- Project documentation

Thank you for contributing to VESPER! 🚀
