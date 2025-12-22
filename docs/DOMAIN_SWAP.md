# Domain Swap Guide

VESPER supports multiple domains through a simple environment variable toggle. This guide shows how to switch between domains with zero code changes.

## Quick Start

```bash
# Default: Finance domain (SEC filings)
DOMAIN=finance docker-compose up -d

# Switch to: Healthcare domain (hospital operations)
DOMAIN=healthcare docker-compose up -d
```

## Supported Domains

| Domain     | ENV Value    | Data Sources                            | Use Cases                             |
| ---------- | ------------ | --------------------------------------- | ------------------------------------- |
| Finance    | `finance`    | SEC EDGAR filings, 10-K/10-Q/8-K        | Financial analysis, earnings research |
| Healthcare | `healthcare` | Quality reports, performance dashboards | Hospital ops, clinical quality        |

## Domain Toggle

### Environment Variable

Set the `DOMAIN` environment variable before starting services:

```bash
# Option 1: Export variable
export DOMAIN=healthcare
python scripts/demo_seed.py
docker-compose up -d

# Option 2: Inline
DOMAIN=healthcare docker-compose up -d

# Option 3: .env file
echo "DOMAIN=healthcare" >> .env
docker-compose up -d
```

### Airflow Variable

For production, set via Airflow UI or CLI:

```bash
# Via Airflow CLI
airflow variables set domain healthcare

# Via Python
from airflow.models import Variable
Variable.set("domain", "healthcare")
```

---

## Finance Domain (Default)

### Data Sources

- SEC EDGAR API
- 10-K Annual Reports
- 10-Q Quarterly Reports
- 8-K Current Reports

### NER Entity Types

| Entity        | Pattern               | Example          |
| ------------- | --------------------- | ---------------- |
| COMPANY       | Inc., Corp., LLC      | "Apple Inc."     |
| TICKER        | 1-5 uppercase letters | "AAPL", "MSFT"   |
| CURRENCY      | Dollar amounts        | "$394.3 billion" |
| PERCENTAGE    | Number with %         | "8% growth"      |
| FISCAL_PERIOD | Q1-Q4, FY             | "FY 2024", "Q3"  |
| FILING_TYPE   | SEC form types        | "10-K", "8-K"    |

### Sample Query

```
What was Apple's total revenue for fiscal year 2024?
```

### Screenshot: Finance Domain

```
┌─────────────────────────────────────────────────────────────┐
│ VESPER - Financial Intelligence                             │
├─────────────────────────────────────────────────────────────┤
│ 🔍 Query: "What was Apple's revenue for FY 2024?"           │
│                                                             │
│ 📊 Answer:                                                  │
│ Apple Inc. reported total revenue of $394.3 billion for    │
│ fiscal year 2024, representing an 8% increase YoY.         │
│                                                             │
│ 📎 Citations:                                               │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ [1] AAPL-10-K-2024 • Financial Performance • 0.95       │ │
│ │     "Total Revenue: $394.3B (up 8% YoY)"               │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ 🏢 Entities: AAPL, Apple Inc., $394.3B, FY 2024, 10-K      │
└─────────────────────────────────────────────────────────────┘
```

---

## Healthcare Domain

### Data Sources

- Hospital quality reports
- Performance dashboards
- Clinical metrics
- Compliance audits

### NER Entity Types

| Entity     | Pattern                  | Example                     |
| ---------- | ------------------------ | --------------------------- |
| FACILITY   | Hospital, Medical Center | "Metro General Hospital"    |
| DEPARTMENT | ER, ICU, Cardiology      | "Emergency", "ICU"          |
| METRIC     | Quality measures         | "readmission rate"          |
| COMPLIANCE | Regulatory standards     | "HIPAA", "Joint Commission" |
| RATE_VALUE | Percentages              | "12.5%", "87%"              |
| TIME_VALUE | Time measurements        | "28 minutes", "4.2 days"    |

### Sample Query

```
What is the patient satisfaction score at Metro General Hospital?
```

### Screenshot: Healthcare Domain

```
┌─────────────────────────────────────────────────────────────┐
│ VESPER - Healthcare Operations                               │
├─────────────────────────────────────────────────────────────┤
│ 🔍 Query: "Patient satisfaction at Metro General?"          │
│                                                             │
│ 📊 Answer:                                                  │
│ Metro General Hospital achieved a patient satisfaction     │
│ score of 87% for the reporting period. Key drivers         │
│ include nurse communication and staff responsiveness.      │
│                                                             │
│ 📎 Citations:                                               │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ [1] METRO_GENERAL-QR-202412 • Patient Experience • 0.94│ │
│ │     "Patient Satisfaction Score: 87%"                  │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ 🏥 Entities: Metro General Hospital, 87%, Emergency, ICU   │
└─────────────────────────────────────────────────────────────┘
```

---

## Architecture Comparison

### Before (Finance Only)

```
┌──────────────┐     ┌───────────────────┐
│  SEC EDGAR   │────▶│ Finance Connector │
│    API       │     │  (hardcoded)      │
└──────────────┘     └─────────┬─────────┘
                               │
                     ┌─────────▼─────────┐
                     │ Finance NER       │
                     │ Patterns          │
                     └─────────┬─────────┘
                               │
                     ┌─────────▼─────────┐
                     │ Vector Store      │
                     └───────────────────┘
```

### After (Domain-Agnostic)

```
                     ┌───────────────────┐
           ┌────────▶│ Finance Connector │
           │         └─────────┬─────────┘
           │                   │
┌──────────┴───┐     ┌─────────▼─────────┐
│ DOMAIN ENV   │────▶│ Domain Transformer│
│ finance|     │     │ (pluggable NER)   │
│ healthcare   │     └─────────┬─────────┘
└──────────┬───┘               │
           │         ┌─────────▼─────────┐
           │         │ Vector Store      │
           │         └───────────────────┘
           │
           │         ┌───────────────────┐
           └────────▶│Healthcare Connector│
                     └───────────────────┘
```

---

## Switching Domains

### Step-by-Step Process

```bash
# 1. Stop current services
docker-compose down

# 2. Set new domain
export DOMAIN=healthcare

# 3. Seed demo data for new domain
python scripts/demo_seed.py --domain healthcare

# 4. Start services
docker-compose up -d

# 5. Warm cache with domain-specific queries
python scripts/cache_warmers.py

# 6. Verify with smoke test
curl http://localhost:8000/health
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the readmission rate?"}'
```

### Validation Checklist

| Check              | Finance             | Healthcare            |
| ------------------ | ------------------- | --------------------- |
| Data ingested      | ✅ SEC filings      | ✅ Quality reports    |
| NER patterns       | ✅ TICKER, CURRENCY | ✅ FACILITY, METRIC   |
| Sample query works | ✅ Revenue query    | ✅ Satisfaction query |
| Citations present  | ✅ Filing refs      | ✅ Report refs        |
| Smoke test passes  | ✅ 200 OK           | ✅ 200 OK             |

---

## Adding New Domains

To add a new domain (e.g., Legal):

### 1. Create Connector

```python
# services/processing/src/vesper_processing/transformers/legal_connector.py

class LegalConnector:
    def __init__(self):
        self.domain = "legal"

    def ingest_documents(self):
        # Ingest legal documents (contracts, cases, regulations)
        pass
```

### 2. Define NER Patterns

```python
LEGAL_NER_PATTERNS = {
    "PARTY": r"\b(?:Plaintiff|Defendant|Petitioner|Respondent)\b",
    "COURT": r"\b(?:Supreme Court|District Court|Circuit Court)\b",
    "STATUTE": r"\b(?:U\.S\.C\.|CFR|Act of \d{4})\b",
    "CASE_NUMBER": r"\b\d{2}-\d{4,}\b",
    "DATE": r"\b(?:January|February|...) \d{1,2}, \d{4}\b",
}
```

### 3. Create Transformer

```python
# services/processing/src/vesper_processing/transformers/legal_transformer.py

class LegalTransformer:
    def __init__(self):
        self.ner_patterns = LEGAL_NER_PATTERNS

    def transform_to_silver(self, document):
        # Apply legal-specific transformations
        pass
```

### 4. Update **init**.py

```python
from .legal_connector import LegalConnector
from .legal_transformer import LegalTransformer
```

### 5. Update DAG

Add branch in `example_ingestion_dag.py`:

```python
def detect_domain(**context) -> str:
    domain = os.getenv("DOMAIN", "finance").lower()

    if domain == "healthcare":
        return "healthcare_bronze_ingestion"
    elif domain == "legal":
        return "legal_bronze_ingestion"
    else:
        return "finance_bronze_ingestion"
```

---

## Troubleshooting

### Domain Not Switching

```bash
# Check current domain
echo $DOMAIN

# Verify in container
docker exec vesper-api printenv DOMAIN

# Force restart with explicit domain
DOMAIN=healthcare docker-compose up -d --force-recreate
```

### NER Patterns Not Applied

```bash
# Debug entity extraction
python -c "
from vesper_processing.transformers import get_entity_filter
patterns = get_entity_filter()
print(f'Domain: {patterns}')
"
```

### Missing Healthcare Data

```bash
# Seed healthcare demo data
DOMAIN=healthcare python scripts/demo_seed.py

# Verify data
ls -la data/demo/
```

---

## Best Practices

1. **Environment Consistency**: Use the same `DOMAIN` value across all services
2. **Data Isolation**: Each domain has separate data directories
3. **Cache Invalidation**: Clear cache when switching domains
4. **Testing**: Run smoke tests after domain switch
5. **Monitoring**: Tag metrics with domain for observability

---

**Last Updated:** December 2025  
**Maintainer:** VESPER Team
