-- Initialize VESPER Ingestion Database
-- Creates the bronze schema and tables

CREATE SCHEMA IF NOT EXISTS bronze;

-- Filings table
CREATE TABLE IF NOT EXISTS bronze.filings (
    id SERIAL PRIMARY KEY,
    cik VARCHAR(10) NOT NULL,
    company_name VARCHAR(255) NOT NULL,
    accession_number VARCHAR(20) NOT NULL UNIQUE,
    form_type VARCHAR(10) NOT NULL,
    filing_date TIMESTAMP NOT NULL,
    report_date TIMESTAMP,
    s3_key VARCHAR(500) NOT NULL,
    document_url TEXT NOT NULL,
    file_size INTEGER,
    content_length INTEGER,
    filing_metadata JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for filings
CREATE INDEX IF NOT EXISTS idx_filings_cik ON bronze.filings(cik);
CREATE INDEX IF NOT EXISTS idx_filings_form_type ON bronze.filings(form_type);
CREATE INDEX IF NOT EXISTS idx_filings_filing_date ON bronze.filings(filing_date);
CREATE UNIQUE INDEX IF NOT EXISTS idx_filings_accession ON bronze.filings(accession_number);

-- Ingestion jobs table
CREATE TABLE IF NOT EXISTS bronze.ingestion_jobs (
    id SERIAL PRIMARY KEY,
    source VARCHAR(50) NOT NULL,
    cik_list TEXT,
    form_types TEXT,
    start_date DATE,
    end_date DATE,
    status VARCHAR(20) NOT NULL,
    total_filings INTEGER DEFAULT 0,
    successful_filings INTEGER DEFAULT 0,
    failed_filings INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    duration_seconds FLOAT
);

-- Indexes for ingestion jobs
CREATE INDEX IF NOT EXISTS idx_jobs_source ON bronze.ingestion_jobs(source);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON bronze.ingestion_jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON bronze.ingestion_jobs(created_at);

-- Grant permissions
GRANT ALL PRIVILEGES ON SCHEMA bronze TO vesper;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA bronze TO vesper;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA bronze TO vesper;
