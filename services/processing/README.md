# VESPER Document Processing Service

Extract and parse SEC filings for semantic search and RAG.

## Features

- **HTML Parsing**: Extract clean text from SEC HTML filings
- **Section Detection**: Identify and extract key sections (Item 1, Item 7, MD&A, etc.)
- **Text Cleaning**: Remove HTML artifacts, normalize whitespace, handle XBRL tags
- **Table Extraction**: Parse HTML tables and financial statements
- **Metadata Extraction**: Extract dates, entities, amounts, and other key information
- **Chunking**: Intelligent document chunking with semantic boundaries

## Installation

```bash
# Using uv (recommended)
uv pip install -e .

# Using pip
pip install -e .
```

## Usage

### CLI

```bash
# Process a single filing
vesper-process parse --filing-id 0000320193-24-000123

# Process filings from S3
vesper-process batch --date 2024-11-01

# Extract tables
vesper-process tables --filing-id 0000320193-24-000123
```

### Python API

```python
from vesper_processing.parsers import HTMLParser
from vesper_processing.extractors import SectionExtractor

# Parse HTML content
parser = HTMLParser()
document = parser.parse(html_content)

# Extract sections
extractor = SectionExtractor()
sections = extractor.extract(document)
```

## Architecture

```
services/processing/
├── src/vesper_processing/
│   ├── parsers/          # HTML and document parsing
│   ├── extractors/       # Section and metadata extraction
│   ├── cleaners/         # Text cleaning and normalization
│   ├── chunkers/         # Document chunking strategies
│   ├── models/           # Data models
│   ├── storage/          # S3 integration
│   └── cli.py           # Command-line interface
└── tests/               # Test suite
```

## Development

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/ tests/
ruff check src/ tests/

# Type checking
mypy src/
```

## Configuration

Configuration via environment variables or `.env` file:

```env
# S3/MinIO
S3_ENDPOINT_URL=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BRONZE_BUCKET=vesper-bronze
S3_SILVER_BUCKET=vesper-silver

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5434
POSTGRES_USER=vesper
POSTGRES_PASSWORD=vesper
POSTGRES_DB=vesper

# Processing
MAX_CHUNK_SIZE=1000
CHUNK_OVERLAP=200
```

## License

MIT
