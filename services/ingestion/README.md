# VESPER Data Ingestion Service

The data ingestion service is responsible for fetching financial documents from SEC EDGAR and storing them in the Bronze layer (MinIO/S3).

## Features

- **SEC EDGAR Connector**: Fetch 10-K, 10-Q, and other financial filings
- **Bronze Layer Storage**: Store raw documents in MinIO/S3
- **Rate Limiting**: Respect SEC EDGAR API rate limits
- **Retry Logic**: Automatic retry with exponential backoff
- **Monitoring**: Prometheus metrics for tracking ingestion

## Installation

```bash
# Install in development mode
pip install -e ".[dev]"
```

## Configuration

Set the following environment variables:

```bash
# SEC EDGAR
SEC_EDGAR_USER_AGENT="Your Name your@email.com"

# Storage
S3_ENDPOINT_URL=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET_BRONZE=vesper-bronze-dev

# Database
DATABASE_URL=postgresql://vesper:vesper@localhost:5434/vesper
```

## Usage

### Command Line

```bash
# Ingest a specific company's 10-K filings
vesper-ingest sec-edgar --cik 0000320193 --form-type 10-K --count 5

# Ingest multiple companies
vesper-ingest sec-edgar --ciks-file companies.txt --form-type 10-Q
```

### Python API

```python
from vesper_ingestion.connectors.sec_edgar import SECEdgarConnector
from vesper_ingestion.storage.s3_storage import S3Storage

# Initialize connector
connector = SECEdgarConnector(
    user_agent="Your Name your@email.com"
)

# Fetch filings
filings = connector.fetch_company_filings(
    cik="0000320193",
    form_type="10-K",
    count=5
)

# Store in Bronze layer
storage = S3Storage(
    endpoint_url="http://localhost:9000",
    bucket_name="vesper-bronze-dev"
)

for filing in filings:
    storage.upload_filing(filing)
```

## Development

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=vesper_ingestion --cov-report=html

# Format code
black src/ tests/

# Lint code
ruff check src/ tests/

# Type check
mypy src/
```

## Architecture

```
services/ingestion/
├── src/vesper_ingestion/
│   ├── connectors/          # Data source connectors
│   │   ├── sec_edgar.py     # SEC EDGAR API connector
│   │   └── base.py          # Base connector interface
│   ├── storage/             # Storage backends
│   │   ├── s3_storage.py    # S3/MinIO storage
│   │   └── base.py          # Base storage interface
│   ├── models/              # Data models
│   │   └── filing.py        # Filing data model
│   ├── cli.py               # CLI interface
│   └── __init__.py
├── tests/
│   ├── unit/                # Unit tests
│   └── integration/         # Integration tests
├── config/                  # Configuration files
├── setup.py                 # Package setup
└── requirements.txt         # Dependencies
```

## Bronze Layer Structure

Documents are stored in MinIO/S3 with the following structure:

```
vesper-bronze-dev/
└── sec-edgar/
    └── {cik}/
        └── {form_type}/
            └── {accession_number}/
                ├── metadata.json
                └── document.html
```

## Monitoring

Metrics exposed on `/metrics` endpoint:

- `ingestion_filings_fetched_total` - Total filings fetched
- `ingestion_filings_stored_total` - Total filings stored
- `ingestion_errors_total` - Total errors encountered
- `ingestion_duration_seconds` - Duration of ingestion operations
